import logging
from collections.abc import Sequence
from enum import Enum

from app.indexer import Indexer, IndexerError, raw_address
from app.storage import Storage, TokenData, UserData

logger = logging.getLogger(__name__)


class Access(Enum):
    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN = "unknown"


async def user_is_holder(storage: Storage, user: UserData, tokens: Sequence[TokenData]) -> bool:
    if not user.wallet_address:
        return False
    owner = raw_address(user.wallet_address)
    for token in tokens:
        if await storage.balance(token.address, owner) < token.min_amount:
            return False
    return True


async def check_access(indexer: Indexer, storage: Storage, user: UserData, tokens: Sequence[TokenData]) -> Access:
    # Without a token the gate is not set up yet: nobody gets in
    if not user.wallet_address or not tokens:
        return Access.DENIED
    owner = raw_address(user.wallet_address)
    try:
        balances = await indexer.balances(tokens, [owner])
    except IndexerError as ex:
        logger.warning("Balances of user %s are unknown: %s", user.id, ex)
        return Access.UNKNOWN
    for token in tokens:
        await storage.set_balances(token.address, [owner], balances[token.address])
    # Decided by this answer: a member check running meanwhile may write an older one
    if all(balances[token.address].get(owner, 0) >= token.min_amount for token in tokens):
        return Access.GRANTED
    return Access.DENIED
