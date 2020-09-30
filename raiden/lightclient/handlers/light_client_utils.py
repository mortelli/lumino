from raiden.constants import EMPTY_PAYMENT_HASH_INVOICE
from raiden.messages import Lock, LockedTransfer
from raiden.transfer.channel import get_amount_locked, compute_merkletree_with, get_next_nonce
from raiden.transfer.mediated_transfer.initiator import get_initial_lock_expiration
from raiden.transfer.merkle_tree import merkleroot
from raiden.transfer.state import ChainState, NettingChannelState, message_identifier_from_prng, HashTimeLockState
from raiden.utils import random_secret, sha3, create_default_identifier
from raiden.utils.typing import MessageID, PaymentID, SecretHash, TokenAmount, TokenNetworkAddress, TargetAddress, \
    InitiatorAddress, Address


class LockedTransferAutogeneratedValues:
    def __init__(self, chain_state: ChainState, channel_state: NettingChannelState):
        self.secret = random_secret()
        self.secrethash = SecretHash(sha3(self.secret))
        self.lock_expiration = get_initial_lock_expiration(chain_state.block_number, channel_state.reveal_timeout)
        self.payment_identifier = PaymentID(create_default_identifier())
        self.message_identifier = MessageID(message_identifier_from_prng(chain_state.pseudo_random_generator))


class LightClientUtils:

    @classmethod
    def build_lt_autogen_values(cls, chain_state: ChainState,
                                channel_state: NettingChannelState) -> LockedTransferAutogeneratedValues:
        return LockedTransferAutogeneratedValues(chain_state, channel_state)

    @classmethod
    def create_locked_transfer(cls, chain_state: ChainState, channel_state: NettingChannelState, amount: int,
                               secrethash: SecretHash, creator_address: Address, partner_address: Address):
        # Build autogenerated values
        lt_autogenerated_values = LightClientUtils.build_lt_autogen_values(chain_state, channel_state)
        # Extract params for later create the LT
        our_balance_proof = channel_state.our_state.balance_proof
        if our_balance_proof:
            transferred_amount = our_balance_proof.transferred_amount
        else:
            transferred_amount = TokenAmount(0)
        locked_amount = TokenAmount(get_amount_locked(channel_state.our_state) + amount)
        lock_transfer = HashTimeLockState(
            amount=amount, expiration=lt_autogenerated_values.lock_expiration, secrethash=secrethash
        )
        lock = Lock(
            amount=lock_transfer.amount,
            expiration=lock_transfer.expiration,
            secrethash=lock_transfer.secrethash,
        )
        merkletree = compute_merkletree_with(channel_state.our_state.merkletree, lock.lockhash)
        locksroot = merkleroot(merkletree)
        locked_transfer = LockedTransfer(
            chain_id=channel_state.canonical_identifier.chain_identifier,
            message_identifier=lt_autogenerated_values.message_identifier,
            payment_identifier=lt_autogenerated_values.payment_identifier,
            payment_hash_invoice=EMPTY_PAYMENT_HASH_INVOICE,
            nonce=get_next_nonce(channel_state.our_state),
            token_network_address=TokenNetworkAddress(channel_state.canonical_identifier.token_network_address),
            token=channel_state.token_address,
            channel_identifier=channel_state.canonical_identifier.channel_identifier,
            transferred_amount=transferred_amount,
            locked_amount=locked_amount,
            recipient=channel_state.partner_state.address, # TODO is this ok? what happenswith mediated payments?
            locksroot=locksroot,
            lock=lock,
            target=TargetAddress(partner_address),
            initiator=InitiatorAddress(creator_address),
            fee=0,
        )
        return locked_transfer
