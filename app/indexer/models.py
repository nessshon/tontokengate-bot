from dataclasses import dataclass

from ton_core import Address

from app.storage import TokenType

# TEP-64: a jetton without `decimals` in its metadata has 9
DEFAULT_DECIMALS = 9


class IndexerError(Exception):
    pass


@dataclass(frozen=True)
class TokenMeta:
    type: TokenType
    name: str
    address: str
    decimals: int | None


def raw_address(address: str) -> str:
    return Address(address).to_str(is_user_friendly=False)
