from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import LEAVE_TRANSITION, PROMOTED_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import CallbackQuery, ChatJoinRequest, ChatMemberUpdated, LinkPreviewOptions, Message
from aiogram.utils.markdown import hbold

from app.bot.handlers.admin.windows import chat_confirm_add
from app.bot.handlers.private.windows import select_language, show_access
from app.bot.keyboards import TopCallback
from app.bot.manager import Manager, SendMode
from app.bot.utils import admin_texts, is_admin, missing_rights, notify_admin, rights_text
from app.config import Config
from app.gate import Access, check_access
from app.indexer import Indexer
from app.storage import Storage

from . import windows

# In a group the picture goes above the text; private screens keep Telegram's default below
PICTURE_ABOVE = LinkPreviewOptions(show_above_text=True)

router = Router()
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.from_user.is_bot.is_(False))
router.callback_query.filter(F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
router.my_chat_member.filter(F.chat.type.in_({ChatType.CHANNEL, ChatType.SUPERGROUP}))


@router.message(Command("balance"), F.reply_to_message.from_user.is_bot.is_(False))
async def balance_command(message: Message, manager: Manager) -> None:
    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        return
    target = message.reply_to_message.from_user
    user = await manager.storage.get_user(target.id)
    text = await windows.balance_text(manager, user, target.full_name, "balance_command", "balance_command_no_tokens")
    await message.answer(text, link_preview_options=PICTURE_ABOVE)


@router.message(Command("top"))
async def top_command(message: Message, manager: Manager) -> None:
    tokens = await manager.storage.tokens()
    if len(tokens) > 1:
        text, reply_markup = windows.top_select_token(manager, tokens)
        await message.answer(text, reply_markup=reply_markup, link_preview_options=PICTURE_ABOVE)
    elif tokens:
        await message.answer(await windows.top_text(manager, tokens[0]), link_preview_options=PICTURE_ABOVE)


@router.callback_query(TopCallback.filter())
async def top_list_callback_query(call: CallbackQuery, callback_data: TopCallback, manager: Manager) -> None:
    message = call.message
    token = await manager.storage.get_token(callback_data.address)
    if not isinstance(message, Message) or token is None:
        return
    try:
        await message.edit_text(await windows.top_text(manager, token), link_preview_options=PICTURE_ABOVE)
    except TelegramBadRequest as ex:
        # A double tap edits the message twice
        if "message is not modified" not in ex.message:
            raise


async def chat_added(event: ChatMemberUpdated, storage: Storage) -> bool:
    return await storage.get_chat(event.chat.id) is not None


# Before bot_promoted: a promotion in an added chat brings the rights back, it does not add the chat again
@router.my_chat_member(chat_added)
async def bot_rights_changed(event: ChatMemberUpdated, bot: Bot, config: Config, storage: Storage) -> None:
    texts = await admin_texts(config, storage)
    title = event.chat.title or str(event.chat.id)
    before, after = missing_rights(event.old_chat_member), missing_rights(event.new_chat_member)
    if event.new_chat_member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
        text = texts.get("chat_bot_removed").format(chat=hbold(title))
    elif after and after != before:
        text = rights_text(texts, title, after)
    elif before and not after:
        text = texts.get("chat_rights_restored").format(chat=hbold(title))
    else:
        return
    await notify_admin(bot, config, text)


@router.my_chat_member(ChatMemberUpdatedFilter(PROMOTED_TRANSITION), is_admin)
async def bot_promoted(event: ChatMemberUpdated, manager: Manager) -> None:
    await manager.state.update_data(chat={"id": event.chat.id, "name": event.chat.title, "type": event.chat.type})
    await chat_confirm_add(manager, send_mode=SendMode.SEND)


@router.chat_join_request()
async def chat_join_request(event: ChatJoinRequest, manager: Manager, indexer: Indexer) -> None:
    if await manager.storage.get_chat(event.chat.id) is None:
        return
    # Telegram lets the bot write to a user who never started it only until the request is processed
    if not manager.user.wallet_address:
        try:
            await select_language(manager, send_mode=SendMode.SEND)
        finally:
            await event.decline()
        return

    access = await check_access(indexer, manager.storage, manager.user, await manager.storage.tokens())
    if access == Access.GRANTED:
        # Recorded first: a member let in without the record would never be checked
        await manager.storage.add_member(event.chat.id, manager.user.id)
        await event.approve()
        if event.chat.type != ChatType.CHANNEL:
            full_name = event.from_user.full_name
            text = await windows.balance_text(
                manager, manager.user, full_name, "welcome_to_chat", "welcome_to_chat_no_tokens"
            )
            await event.answer(text, link_preview_options=PICTURE_ABOVE)
        return
    # Nothing approves a request later: the user sends a new one once the wallet holds enough or the indexer is back
    try:
        await show_access(manager, access, send_mode=SendMode.SEND)
    finally:
        await event.decline()


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def member_left(
    event: ChatMemberUpdated,
    bot: Bot,
    dispatcher: Dispatcher,
    config: Config,
    storage: Storage,
) -> None:
    user_id = event.new_chat_member.user.id
    await storage.remove_member(event.chat.id, user_id)
    if event.from_user.id != bot.id or event.new_chat_member.status != ChatMemberStatus.KICKED:
        return

    if event.chat.type != ChatType.CHANNEL:
        with suppress(TelegramAPIError):
            text = windows.kicked_text(config, user_id, await storage.get_user(user_id))
            await bot.send_message(event.chat.id, text, link_preview_options=PICTURE_ABOVE)
    manager = await Manager.from_user(dispatcher, bot, user_id)
    if manager is not None:
        with suppress(TelegramAPIError):
            await show_access(manager, Access.DENIED, send_mode=SendMode.SEND)
