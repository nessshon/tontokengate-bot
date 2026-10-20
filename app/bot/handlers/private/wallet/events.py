import logging
from contextlib import suppress

from ton_connect import Connector
from ton_connect.exceptions import TonConnectError
from ton_connect.models import Wallet

from app.bot.manager import Manager
from app.bot.states import UserState
from app.indexer import Indexer

from .. import windows
from .errors import ConnectError, connect_error
from .proof import check_proof

logger = logging.getLogger(__name__)


async def _accept_wallet(manager: Manager, wallet: Wallet, domain: str, indexer: Indexer) -> None:
    failure = await check_proof(wallet, domain, indexer)
    if failure is not None:
        await windows.connect_wallet_error(manager, failure)
        return
    address = wallet.account.address.to_str(is_bounceable=False)
    manager.user = await manager.storage.patch_user(manager.user.id, wallet_address=address) or manager.user
    await windows.main_menu(manager)


async def on_connect(connector: Connector, error: TonConnectError | None) -> None:
    try:
        dispatcher = connector["dispatcher"]
        manager = await Manager.from_user(dispatcher, connector["bot"], int(connector.session_key))
        if manager is None:
            return
        if error is None and connector.wallet is not None:
            try:
                await _accept_wallet(manager, connector.wallet, dispatcher["proof_domain"], dispatcher["indexer"])
            except Exception:
                # The error itself goes on to Event.ERROR; the user must not stay on a QR code that no longer works
                await windows.connect_wallet_error(manager, ConnectError.FAILED)
                raise
        # An attempt that expired or failed after the user left the screen shows nothing
        elif await manager.state.get_state() == UserState.CONNECT_WALLET:
            await windows.connect_wallet_error(manager, connect_error(error))
    finally:
        # Only the address is kept
        if connector.connected:
            with suppress(TonConnectError):
                await connector.disconnect()
        await connector.close()


async def on_error(connector: Connector, error: TonConnectError) -> None:
    logger.error("Wallet connection of user %s failed: %s", connector.session_key, error)
