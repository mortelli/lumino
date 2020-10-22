import os
import sys
from typing import List

import click

from raiden.constants import PATH_FINDING_BROADCASTING_ROOM, MONITORING_BROADCASTING_ROOM
from raiden.exceptions import RaidenError
from raiden.network.transport import MatrixNode as MatrixTransportNode
from raiden.network.transport.matrix import MatrixLightClientNode as MatrixLightClientTransportNode
from raiden.network.transport.matrix.utils import get_available_servers_from_config, server_is_available
from raiden.settings import DEFAULT_MATRIX_KNOWN_SERVERS
from raiden.storage import sqlite, serialize
from raiden.utils import Address
from raiden.utils.cli import get_matrix_servers
from transport.layer import Layer as TransportLayer
from transport.node import Node as TransportNode


class MatrixLayer(TransportLayer[MatrixTransportNode]):

    def construct_full_node(self, config):
        self._prepare_config(config)
        return MatrixTransportNode(config["address"], config["transport"]["matrix"])

    def construct_light_clients_nodes(self, config):
        self._prepare_config(config)
        try:

            database_path = config["database_path"]

            database_dir = os.path.dirname(config["database_path"])
            os.makedirs(database_dir, exist_ok=True)

            storage = sqlite.SerializedSQLiteStorage(
                database_path=database_path, serializer=serialize.JSONSerializer()
            )

            light_clients = storage.get_all_light_clients()

            result: List[TransportNode] = []

            for light_client in light_clients:
                current_server_name = None

                if light_client["current_server_name"]:
                    current_server_name = light_client["current_server_name"]
                    available_servers = get_available_servers_from_config(config["transport"]["matrix"])
                    if not server_is_available(current_server_name, available_servers):
                        # we flag the light client as pending for deletion because it's associated to a server that
                        # is not available anymore so we need to force a new on-boarding, the next request from that LC will
                        # delete it and respond with an error to control the re-onboard
                        storage.flag_light_client_as_pending_for_deletion(light_client["address"])
                        log.info("No available server with name " + current_server_name +
                                 ", LC has been flagged for deletion from DB, on-boarding is needed for LC with address: " +
                                 light_client["address"])
                        continue

                config = config["transport"]["matrix"]
                config["current_server_name"] = current_server_name
                auth_params = {
                    "light_client_password": light_client["password"],
                    "light_client_display_name": light_client["display_name"],
                    "light_client_seed_retry": light_client["seed_retry"]
                }
                light_client_transport = MatrixLightClientTransportNode(
                    light_client['address'],
                    config,
                    auth_params,
                )

                result.append(light_client_transport)
            return result
        except RaidenError as ex:
            click.secho(f"FATAL: {ex}", fg="red")
            sys.exit(1)

    def _prepare_config(self, config):
        from raiden.ui.app import log

        if config["transport"]["matrix"].get("available_servers") is None:
            # fetch list of known servers from raiden-network/raiden-tranport repo
            available_servers_url = DEFAULT_MATRIX_KNOWN_SERVERS[config["environment_type"]]
            available_servers = get_matrix_servers(available_servers_url)
            log.debug("Fetching available matrix servers", available_servers=available_servers)
            config["transport"]["matrix"]["available_servers"] = available_servers

        # TODO: This needs to be adjusted once #3735 gets implemented
        # Add PFS broadcast room if enabled
        if config["services"]["pathfinding_service_address"] is not None:
            if PATH_FINDING_BROADCASTING_ROOM not in config["transport"]["matrix"]["global_rooms"]:
                config["transport"]["matrix"]["global_rooms"].append(PATH_FINDING_BROADCASTING_ROOM)

        # Add monitoring service broadcast room if enabled
        if config["services"]["monitoring_enabled"] is True:
            config["transport"]["matrix"]["global_rooms"].append(MONITORING_BROADCASTING_ROOM)

    @staticmethod
    def new_light_client(address: Address, config: dict, auth_params: dict) -> TransportNode:
        return MatrixLightClientTransportNode(address, config, auth_params)