from collections import Counter

from ton_core import Address
from toncenter.rest.v3.models import JettonMastersResponse, JettonWallet, Metadata, NFTItem, TokenInfo

from app.storage import TokenType

from .models import DEFAULT_DECIMALS, IndexerError, TokenMeta, raw_address

UNKNOWN_COLLECTION = "Unknown Collection"


def jetton_name(name: str | None, symbol: str | None) -> str:
    return " ".join(part for part in (name, f"${symbol}" if symbol else None) if part) or "Unknown Jetton"


def token_info(metadata: Metadata | None, address: str) -> TokenInfo:
    for key, item in (metadata.root if metadata else {}).items():
        if Address(key) == Address(address) and item.token_info:
            return item.token_info[0]
    return TokenInfo()


# Off-chain metadata keeps decimals in the indexed info, on-chain one in the jetton content
def jetton_meta(response: JettonMastersResponse, address: str) -> TokenMeta:
    content = (response.jetton_masters or [])[0].jetton_content or {}
    info = token_info(response.metadata, address)
    found = ((info.extra or {}).get("decimals"), content.get("decimals"))
    decimals = next((value for value in found if value is not None), DEFAULT_DECIMALS)
    name = jetton_name(info.name or content.get("name"), info.symbol or content.get("symbol"))
    try:
        return TokenMeta(TokenType.JETTON, name, address, int(decimals))
    except (TypeError, ValueError) as ex:
        raise IndexerError(f"Jetton {address} has decimals {decimals!r}") from ex


def jetton_balances(wallets: list[JettonWallet]) -> Counter[tuple[str, str]]:
    return Counter(
        {
            (raw_address(wallet.jetton), raw_address(wallet.owner)): int(wallet.balance)
            for wallet in wallets
            if wallet.jetton and wallet.owner and wallet.balance
        }
    )


def count_items(items: list[NFTItem]) -> Counter[tuple[str, str]]:
    pairs = ((item.collection_address, item.real_owner or item.owner_address) for item in items)
    return Counter((raw_address(collection), raw_address(owner)) for collection, owner in pairs if collection and owner)
