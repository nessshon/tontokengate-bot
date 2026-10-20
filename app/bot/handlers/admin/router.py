import logging
from dataclasses import asdict, replace

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswer
from ton_core import Address, AddressError

from app.bot.commands import bot_admin_commands_delete, bot_admin_commands_setup
from app.bot.keyboards import AdminCallback, ChatCallback, PageCallback, TokenCallback
from app.bot.manager import Manager, SendMode, safe_delete
from app.bot.states import AdminState
from app.bot.utils import is_admin, missing_rights, parse_min_amount, rights_list
from app.indexer import Indexer, IndexerError
from app.storage import AdminData, ChatData, TokenData, now

from . import windows

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(F.chat.type == "private", is_admin)
router.callback_query.filter(F.message.chat.type == "private", is_admin)


def item_alert(callback_answer: CallbackAnswer, manager: Manager, text_key: str, item: str) -> None:
    # Telegram shows at most 200 characters in an alert, a token name from metadata can be longer
    callback_answer.text = manager.text_message.get(text_key).format(item=item)[:200]
    callback_answer.show_alert = True


@router.message(Command("admin"))
async def admin_command(message: Message, manager: Manager) -> None:
    await windows.admin_menu(manager, send_mode=SendMode.SEND)
    await safe_delete(message)


@router.callback_query(AdminState.ADMIN_MENU, F.data == "chats_menu")
async def chats_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.chats_menu(manager, page=1)


@router.callback_query(AdminState.ADMIN_MENU, F.data == "tokens_menu")
async def tokens_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.tokens_menu(manager, page=1)


@router.callback_query(AdminState.ADMIN_MENU, F.data == "admins_menu")
async def admins_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admins_menu(manager, page=1)


@router.callback_query(
    StateFilter(AdminState.CHATS_MENU, AdminState.TOKENS_MENU, AdminState.ADMINS_MENU), F.data == "back"
)
async def back_to_admin_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admin_menu(manager)


@router.callback_query(AdminState.CHATS_MENU, PageCallback.filter())
async def chats_page_callback_query(_: CallbackQuery, callback_data: PageCallback, manager: Manager) -> None:
    await windows.chats_menu(manager, page=callback_data.number)


@router.callback_query(AdminState.CHATS_MENU, ChatCallback.filter())
async def chat_callback_query(_: CallbackQuery, callback_data: ChatCallback, manager: Manager) -> None:
    await manager.state.update_data(chat_id=callback_data.id)
    await windows.chat_info(manager)


@router.callback_query(AdminState.CHAT_INFO, F.data == "back")
async def back_to_chats_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.chats_menu(manager)


@router.callback_query(AdminState.CHAT_INFO, F.data == "delete")
async def chat_delete_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.chat_confirm_delete(manager)


@router.callback_query(AdminState.CHAT_CONFIRM_DELETE, F.data == "back")
async def back_to_chat_info_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.chat_info(manager)


@router.callback_query(AdminState.CHAT_CONFIRM_DELETE, F.data == "confirm")
async def chat_confirm_delete_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    chat_id = (await manager.state.get_data()).get("chat_id")
    chat = None if chat_id is None else await manager.storage.delete_chat(chat_id)
    if chat is not None:
        item_alert(callback_answer, manager, "item_deleted", chat.name)
    await windows.chats_menu(manager, page=1)


@router.callback_query(AdminState.CHAT_CONFIRM_ADD, F.data == "back")
async def back_to_chats_first_page_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.chats_menu(manager, page=1)


@router.callback_query(AdminState.CHAT_CONFIRM_ADD, F.data == "confirm")
async def chat_confirm_add_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    chat_data = (await manager.state.get_data()).get("chat")
    if chat_data is None:
        await windows.chats_menu(manager, page=1)
        return
    await manager.send_loader_message()

    bot_user = await manager.bot.me()
    try:
        chat = await manager.bot.get_chat(chat_data["id"])
        missing = missing_rights(await manager.bot.get_chat_member(chat.id, bot_user.id))
        invite = None
        if not missing:
            invite = await manager.bot.create_chat_invite_link(
                chat.id,
                name=f"Generated by @{bot_user.username}",
                creates_join_request=True,
            )
    except (TelegramBadRequest, TelegramForbiddenError) as ex:
        logger.warning("Chat %s is not added: %s", chat_data["id"], ex.message)
        callback_answer.text = manager.text_message.get("chat_add_error")
        callback_answer.show_alert = True
        await windows.chat_confirm_add(manager)
        return
    if invite is None:
        rights = rights_list(manager.text_message, missing)
        callback_answer.text = manager.text_message.get("chat_add_rights").format(rights=rights)
        callback_answer.show_alert = True
        await windows.chat_confirm_add(manager)
        return
    stored = await manager.storage.get_chat(chat.id)
    title = chat.title or chat_data["name"]
    await manager.storage.save_chat(
        ChatData(
            id=chat.id,
            name=title,
            type=chat.type,
            invite_link=invite.invite_link,
            created_at=stored.created_at if stored else now(),
        )
    )
    item_alert(callback_answer, manager, "item_added", title)
    await windows.chats_menu(manager, page=1)


@router.callback_query(AdminState.TOKENS_MENU, PageCallback.filter())
async def tokens_page_callback_query(_: CallbackQuery, callback_data: PageCallback, manager: Manager) -> None:
    await windows.tokens_menu(manager, page=callback_data.number)


@router.callback_query(AdminState.TOKENS_MENU, TokenCallback.filter())
async def token_callback_query(_: CallbackQuery, callback_data: TokenCallback, manager: Manager) -> None:
    await manager.state.update_data(token_address=callback_data.address)
    await windows.token_info(manager)


@router.callback_query(AdminState.TOKENS_MENU, F.data == "add")
async def token_add_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_send_address(manager)


@router.callback_query(StateFilter(AdminState.TOKEN_INFO, AdminState.TOKEN_SEND_ADDRESS), F.data == "back")
async def back_to_tokens_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.tokens_menu(manager)


@router.callback_query(AdminState.TOKEN_INFO, F.data == "edit_min_amount")
async def token_edit_amount_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_edit_amount(manager)


@router.callback_query(AdminState.TOKEN_INFO, F.data == "delete")
async def token_delete_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_confirm_delete(manager)


@router.callback_query(StateFilter(AdminState.TOKEN_CONFIRM_DELETE, AdminState.TOKEN_EDIT_AMOUNT), F.data == "back")
async def back_to_token_info_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_info(manager)


@router.callback_query(AdminState.TOKEN_CONFIRM_DELETE, F.data == "confirm")
async def token_confirm_delete_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    address = (await manager.state.get_data()).get("token_address")
    token = None if address is None else await manager.storage.delete_token(address)
    if token is not None:
        item_alert(callback_answer, manager, "item_deleted", token.name)
    await windows.tokens_menu(manager, page=1)


@router.callback_query(AdminState.TOKEN_SEND_AMOUNT, F.data == "back")
async def back_to_token_send_address_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_send_address(manager)


@router.callback_query(AdminState.TOKEN_CONFIRM_ADD, F.data == "back")
async def back_to_token_send_amount_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.token_send_amount(manager)


@router.callback_query(AdminState.TOKEN_CONFIRM_ADD, F.data == "confirm")
async def token_confirm_add_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    state_data = await manager.state.get_data()
    token, min_amount = state_data.get("token"), state_data.get("token_min_amount")
    if token is None or min_amount is None:
        await windows.token_send_address(manager)
        return
    await manager.storage.save_token(
        TokenData(
            address=token["address"],
            name=token["name"],
            type=token["type"],
            min_amount=min_amount,
            created_at=now(),
            decimals=token["decimals"],
        )
    )
    item_alert(callback_answer, manager, "item_added", token["name"])
    await windows.tokens_menu(manager, page=1)


@router.callback_query(AdminState.ADMINS_MENU, PageCallback.filter())
async def admins_page_callback_query(_: CallbackQuery, callback_data: PageCallback, manager: Manager) -> None:
    await windows.admins_menu(manager, page=callback_data.number)


@router.callback_query(AdminState.ADMINS_MENU, AdminCallback.filter())
async def admin_callback_query(_: CallbackQuery, callback_data: AdminCallback, manager: Manager) -> None:
    await manager.state.update_data(admin_id=callback_data.user_id)
    await windows.admin_info(manager)


@router.callback_query(AdminState.ADMINS_MENU, F.data == "add")
async def admin_add_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admin_send_id(manager)


@router.callback_query(StateFilter(AdminState.ADMIN_INFO, AdminState.ADMIN_SEND_ID), F.data == "back")
async def back_to_admins_menu_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admins_menu(manager)


@router.callback_query(AdminState.ADMIN_INFO, F.data == "delete")
async def admin_delete_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admin_confirm_delete(manager)


@router.callback_query(AdminState.ADMIN_CONFIRM_DELETE, F.data == "back")
async def back_to_admin_info_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admin_info(manager)


@router.callback_query(AdminState.ADMIN_CONFIRM_DELETE, F.data == "confirm")
async def admin_confirm_delete_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    user_id = (await manager.state.get_data()).get("admin_id")
    admin = None if user_id is None else await manager.storage.remove_admin(user_id)
    if admin is not None:
        item_alert(callback_answer, manager, "item_deleted", admin.full_name)
        await bot_admin_commands_delete(manager.bot, admins_ids=[admin.user_id])
    await windows.admins_menu(manager, page=1)


@router.callback_query(AdminState.ADMIN_CONFIRM_ADD, F.data == "back")
async def back_to_admin_send_id_callback_query(_: CallbackQuery, manager: Manager) -> None:
    await windows.admin_send_id(manager)


@router.callback_query(AdminState.ADMIN_CONFIRM_ADD, F.data == "confirm")
async def admin_confirm_add_callback_query(
    _: CallbackQuery,
    callback_answer: CallbackAnswer,
    manager: Manager,
) -> None:
    admin = (await manager.state.get_data()).get("admin")
    if admin is None:
        await windows.admin_send_id(manager)
        return
    await manager.storage.add_admin(AdminData(**admin, created_at=now()))
    item_alert(callback_answer, manager, "item_added", admin["full_name"])
    await bot_admin_commands_setup(manager.bot, admins_ids=[admin["user_id"]])
    await windows.admins_menu(manager, page=1)


@router.message(AdminState.TOKEN_SEND_ADDRESS, F.text.as_("text"))
async def token_send_address_message(message: Message, text: str, manager: Manager, indexer: Indexer) -> None:
    await safe_delete(message)
    await manager.send_loader_message()
    texts = manager.text_message
    try:
        address = Address(text.strip()).to_str(is_bounceable=True)
    except AddressError:
        await windows.token_send_address(manager, texts.get("token_send_address_error"))
        return
    try:
        meta = await indexer.resolve_token(address)
    except IndexerError as ex:
        logger.warning("Token %s is not resolved: %s", address, ex)
        await windows.token_send_address(manager, texts.get("token_send_address_error_unavailable"))
        return

    if meta is None:
        await windows.token_send_address(manager, texts.get("token_send_address_error_not_supported"))
    elif await manager.storage.get_token(meta.address):
        await windows.token_send_address(manager, texts.get("token_send_address_error_already_exist"))
    else:
        await manager.state.update_data(token=asdict(meta))
        await windows.token_send_amount(manager)


@router.message(AdminState.TOKEN_SEND_AMOUNT, F.text.as_("text"))
async def token_send_amount_message(message: Message, text: str, manager: Manager) -> None:
    await safe_delete(message)
    token = (await manager.state.get_data()).get("token")
    if token is None:
        await windows.token_send_address(manager)
        return
    min_amount = parse_min_amount(text, token["type"], token["decimals"])
    if min_amount is None:
        await windows.token_send_amount(manager, manager.text_message.get("token_send_amount_error"))
        return
    await manager.state.update_data(token_min_amount=min_amount)
    await windows.token_confirm_add(manager)


@router.message(AdminState.TOKEN_EDIT_AMOUNT, F.text.as_("text"))
async def token_edit_amount_message(message: Message, text: str, manager: Manager) -> None:
    await safe_delete(message)
    token = await windows.selected_token(manager)
    if token is None:
        await windows.tokens_menu(manager)
        return
    min_amount = parse_min_amount(text, token.type, token.decimals)
    if min_amount is None:
        await windows.token_edit_amount(manager, manager.text_message.get("token_send_amount_error"))
        return
    await manager.storage.save_token(replace(token, min_amount=min_amount))
    await windows.token_info(manager)


@router.message(AdminState.ADMIN_SEND_ID, F.text.as_("text"))
async def admin_send_id_message(message: Message, text: str, manager: Manager) -> None:
    await safe_delete(message)
    texts = manager.text_message
    if not text.strip().isdecimal():
        error = texts.get("admin_send_id_error_not_member")
    else:
        try:
            chat = await manager.bot.get_chat(int(text))
        except TelegramBadRequest:
            error = texts.get("admin_send_id_error_not_found")
        else:
            username = f"@{chat.username}" if chat.username else None
            admin = {"user_id": chat.id, "full_name": chat.full_name, "username": username}
            await manager.state.update_data(admin=admin)
            await windows.admin_confirm_add(manager)
            return
    await windows.admin_send_id(manager, texts.get("admin_send_id_error").format(error=error))
