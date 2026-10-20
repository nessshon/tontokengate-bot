import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from functools import partial
from itertools import batched

from ton_core import Address, PublicKey
from toncenter.exceptions import ToncenterError
from toncenter.rest import ToncenterRestClient
from toncenter.rest.v3.models import JettonWallet, NFTItem, V2RunGetMethodRequest
from toncenter.types import Network

from app.storage import TokenData, TokenType

from .models import IndexerError, TokenMeta, raw_address
from .parsers import UNKNOWN_COLLECTION, count_items, jetton_balances, jetton_meta, token_info

PAGE = 1000
OWNERS_PER_REQUEST = 250
TIMEOUT = 10
TIMEOUT_RETRIES = 2


class Indexer:
    def __init__(self, key: str | None, rps: int | None, is_testnet: bool) -> None:
        network = Network.TESTNET if is_testnet else Network.MAINNET
        self.client = ToncenterRestClient(api_key=key or "", network=network, rps_limit=rps, timeout=TIMEOUT)

    async def start(self) -> None:
        await self.client.create_session()

    async def close(self) -> None:
        await self.client.close_session()

    # The client retries 429, 5xx and dropped connections itself; a request that runs out of time leaks out raw
    async def _call[T](self, request: Callable[[], Awaitable[T]]) -> T:
        try:
            for attempt in range(TIMEOUT_RETRIES):
                with suppress(TimeoutError):
                    return await request()
                await asyncio.sleep(attempt + 1)
            return await request()
        except TimeoutError as ex:
            raise IndexerError(f"Toncenter did not answer in {TIMEOUT} s") from ex
        except ToncenterError as ex:
            raise IndexerError(str(ex)) from ex

    async def resolve_token(self, address: str) -> TokenMeta | None:
        masters = await self._call(partial(self.client.v3.jettons.get_jetton_masters, address=[address]))
        if masters.jetton_masters:
            return jetton_meta(masters, address)
        collections = await self._call(partial(self.client.v3.nfts.get_nft_collections, collection_address=[address]))
        if collections.nft_collections:
            name = token_info(collections.metadata, address).name or UNKNOWN_COLLECTION
            return TokenMeta(TokenType.NFT, name, address, None)
        return None

    async def balances(self, tokens: Sequence[TokenData], owners: Sequence[str]) -> dict[str, dict[str, int]]:
        jettons = [token.address for token in tokens if token.type == TokenType.JETTON]
        collections = [token.address for token in tokens if token.type == TokenType.NFT]
        found: Counter[tuple[str, str]] = Counter()
        # A wallet shared by several bot users must not land in two batches and count twice
        for batch in batched(dict.fromkeys(owners), OWNERS_PER_REQUEST):
            if jettons:
                found += jetton_balances(await self._jetton_wallets(jettons, list(batch)))
            if collections:
                found += count_items(await self._nft_items(collections, list(batch)))

        result: dict[str, dict[str, int]] = {token.address: {} for token in tokens}
        token_by_raw = {raw_address(token.address): token.address for token in tokens}
        for (token, owner), amount in found.items():
            if token in token_by_raw:
                result[token_by_raw[token]][owner] = amount
        return result

    # Anyone on chain, not only the bot users: an empty answer here is an indexer gap
    async def has_holders(self, token: TokenData) -> bool:
        if token.type == TokenType.JETTON:
            wallets = await self._call(
                partial(
                    self.client.v3.jettons.get_jetton_wallets,
                    jetton_address=[token.address],
                    exclude_zero_balance=True,
                    limit=1,
                )
            )
            return bool(wallets.jetton_wallets)
        items = await self._call(
            partial(self.client.v3.nfts.get_nft_items, collection_address=[token.address], limit=1)
        )
        return bool(items.nft_items)

    # Offset pages are not a snapshot: a row moved between two reads comes twice, so rows are kept by address
    async def _jetton_wallets(self, jettons: list[str], owners: list[str]) -> list[JettonWallet]:
        wallets: dict[str, JettonWallet] = {}
        offset = 0
        while True:
            response = await self._call(
                partial(
                    self.client.v3.jettons.get_jetton_wallets,
                    owner_address=owners,
                    jetton_address=jettons,
                    exclude_zero_balance=True,
                    limit=PAGE,
                    offset=offset,
                )
            )
            page = response.jetton_wallets or []
            wallets |= {wallet.address or f"row {offset + n}": wallet for n, wallet in enumerate(page)}
            offset += len(page)
            if len(page) < PAGE:
                return list(wallets.values())

    async def _nft_items(self, collections: list[str], owners: list[str]) -> list[NFTItem]:
        items: dict[str, NFTItem] = {}
        offset = 0
        while True:
            # include_on_sale counts an item on sale for its owner, not for the sale contract
            response = await self._call(
                partial(
                    self.client.v3.nfts.get_nft_items,
                    owner_address=owners,
                    collection_address=collections,
                    include_on_sale=True,
                    limit=PAGE,
                    offset=offset,
                )
            )
            page = response.nft_items or []
            items |= {item.address or f"row {offset + n}": item for n, item in enumerate(page)}
            offset += len(page)
            if len(page) < PAGE:
                return list(items.values())

    async def public_key(self, address: Address) -> PublicKey | None:
        request = V2RunGetMethodRequest(
            address=address.to_str(is_user_friendly=False), method="get_public_key", stack=[]
        )
        result = await self._call(partial(self.client.v3.api_v2.run_get_method, request))
        # An undeployed wallet answers with a non-zero exit code
        if result.exit_code != 0 or not result.stack:
            return None
        return PublicKey(int(str(result.stack[0].value), 16).to_bytes(32, "big"))
