from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram_tonconnect import TonConnectContext

from app.bot.keyboards import LanguageCallback
from app.bot.manager import Manager, SendMode, safe_delete
from app.bot.states import UserState
from app.gate import check_access
from app.indexer import Indexer

from . import windows

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


@router.message(CommandStart())
async def start_command(message: Message, manager: Manager, tc: TonConnectContext) -> None:
    # The new screen replaces the connect one, whose operation would show its end later out of nowhere
    await tc.cancel()
    await windows.main_menu(manager, send_mode=SendMode.SEND)
    await safe_delete(message)


@router.callback_query(StateFilter("*"), F.data == "main")
async def main_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.main_menu(manager)


@router.callback_query(UserState.SELECT_LANGUAGE, LanguageCallback.filter())
async def select_language_callback_query(
    _: CallbackQuery,
    callback_data: LanguageCallback,
    manager: Manager,
    tc: TonConnectContext,
) -> None:
    await manager.storage.patch_user(manager.user.id, language_code=callback_data.code)
    manager.set_language(callback_data.code)
    await manager.send_loader_message()
    await tc.connect()


@router.callback_query(UserState.MAIN_MENU, F.data == "get_access")
async def get_access_callback_query(_: CallbackQuery, manager: Manager, indexer: Indexer) -> None:
    await manager.send_loader_message()
    tokens = await manager.storage.tokens()
    await windows.show_access(manager, await check_access(indexer, manager.storage, manager.user, tokens))


@router.callback_query(UserState.MAIN_MENU, F.data == "disconnect_wallet")
async def disconnect_wallet_callback_query(_: CallbackQuery, manager: Manager) -> None:
    manager.user = await manager.storage.patch_user(manager.user.id, wallet_address=None) or manager.user
    await windows.select_language(manager)


@router.callback_query(UserState.MAIN_MENU, F.data == "change_language")
async def change_language_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.change_language(manager)


@router.callback_query(UserState.CHANGE_LANGUAGE, LanguageCallback.filter())
async def changed_language_callback_query(
    _: CallbackQuery,
    callback_data: LanguageCallback,
    manager: Manager,
) -> None:
    await manager.storage.patch_user(manager.user.id, language_code=callback_data.code)
    manager.set_language(callback_data.code)
    await windows.main_menu(manager)
