from aiogram_tonconnect import Status, TonConnectContext, TonConnectEvent, TonConnectRouter
from ton_connect.models import Wallet

from app.bot.manager import Manager

from .. import windows

router = TonConnectRouter()


@router.connect()
async def connected(event: TonConnectEvent, wallet: Wallet | None, manager: Manager, tc: TonConnectContext) -> None:
    if event.status is Status.DONE and wallet is not None:
        address = wallet.account.address.to_str(is_bounceable=False)
        manager.user = await manager.storage.patch_user(manager.user.id, wallet_address=address) or manager.user
        # Only the address is kept
        await tc.disconnect()
    # /admin or another command replaced the connect screen: its late end must not draw over the new one
    if event.message.message_id != (await manager.state.get_data()).get("message_id"):
        return
    if event.status is Status.DONE:
        await windows.main_menu(manager)
    else:
        # Back on the connect screen or on its error
        await windows.select_language(manager)
