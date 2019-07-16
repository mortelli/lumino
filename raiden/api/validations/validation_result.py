from typing import NamedTuple, Any

from raiden.network.proxies import Token


class TokenExists(NamedTuple):
    error: Any = None
    valid: bool = False
    token: Token = None


class EnoughBalance(NamedTuple):
    error: Any = None
    valid: bool = False
    balance: int = 0



