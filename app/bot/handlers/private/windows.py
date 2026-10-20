from collections.abc import Sequence

from aiogram.utils.markdown import hcode, hide_link, hlink
from ton_connect.models.app import AppWallet

from app.bot import keyboards
from app.bot.manager import Manager, SendMode
from app.bot.states import UserState
from app.bot.utils import buy_url, token_amount, tonviewer_link
from app.gate import Access


async def select_language(manager: Manager, send_mode: SendMode = SendMode.EDIT) -> None:
    text = manager.text_message.get("select_language")
    await manager.send_message(text, reply_markup=keyboards.select_language(), send_mode=send_mode)
    await manager.state.set_state(UserState.SELECT_LANGUAGE)


async def change_language(manager: Manager) -> None:
    text = manager.text_message.get("change_language")
    await manager.send_message(text, reply_markup=keyboards.select_language())
    await manager.state.set_state(UserState.CHANGE_LANGUAGE)


async def connect_wallet(
    manager: Manager,
    wallets: Sequence[AppWallet],
    wallet: AppWallet,
    qr_url: str,
    link: str,
) -> None:
    text = hide_link(qr_url) + manager.text_message.get("connect_wallet").format(wallet_name=wallet.name)
    reply_markup = keyboards.connect_wallet(manager.text_button, wallets, wallet, link)
    await manager.send_message(text, reply_markup=reply_markup)
    await manager.state.update_data(app_wallet=wallet.app_name)
    await manager.state.set_state(UserState.CONNECT_WALLET)


async def connect_wallet_error(manager: Manager, text_key: str) -> None:
    text = manager.text_message.get(text_key)
    await manager.send_message(text, reply_markup=keyboards.connect_wallet_error(manager.text_button))
    await manager.state.set_state(UserState.CONNECT_WALLET)


async def main_menu(manager: Manager, send_mode: SendMode = SendMode.EDIT) -> None:
    if not manager.user.wallet_address:
        await select_language(manager, send_mode=send_mode)
        return
    chats = await manager.storage.chats()
    tokens = await manager.storage.tokens()
    dex_name = manager.config.DEX_NAME

    text = manager.text_message.get("main_menu").format(
        wallet=tonviewer_link(manager.user.wallet_address),
        chats="\n".join(f"• {hcode(chat.name)}" for chat in chats),
        tokens="\n".join(
            f"• {hlink(token.name, buy_url(token, dex_name))} - {hcode(token_amount(token, token.min_amount))}"
            for token in tokens
        ),
    )
    await manager.send_message(text, reply_markup=keyboards.main_menu(manager.text_button), send_mode=send_mode)
    await manager.state.set_state(UserState.MAIN_MENU)


async def show_access(manager: Manager, access: Access, send_mode: SendMode = SendMode.EDIT) -> None:
    if access == Access.GRANTED:
        chats = await manager.storage.chats()
        text = manager.text_message.get("allow_access")
        reply_markup = keyboards.allow_access(manager.text_button, chats)
    elif access == Access.DENIED:
        tokens = await manager.storage.tokens()
        text = manager.text_message.get("deny_access" if tokens else "deny_access_no_tokens")
        reply_markup = keyboards.deny_access(manager.text_button, tokens, manager.config.DEX_NAME)
    else:
        text = manager.text_message.get("check_failed")
        reply_markup = keyboards.main(manager.text_button)
    await manager.send_message(text, reply_markup=reply_markup, send_mode=send_mode)
