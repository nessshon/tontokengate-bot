from __future__ import annotations

from contextlib import suppress
from enum import StrEnum

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

from app.config import Config
from app.storage import Storage, UserData
from app.texts import TextButton, TextMessage

# Telegram reports these only as the text of TelegramBadRequest
MESSAGE_EDIT_ERRORS = [
    "there is no text in the message to edit",
    "message can't be edited",
    "message to edit not found",
]
MESSAGE_DELETE_ERRORS = [
    "message can't be deleted",
    "message to delete not found",
]


async def safe_delete(message: Message) -> None:
    with suppress(TelegramBadRequest):
        await message.delete()


class SendMode(StrEnum):
    SEND = "send"
    EDIT = "edit"


class Manager:
    def __init__(
        self,
        bot: Bot,
        config: Config,
        storage: Storage,
        state: FSMContext,
        user: UserData,
        language_code: str | None,
    ) -> None:
        self.bot = bot
        self.config = config
        self.storage = storage
        self.state = state
        self.user = user
        self.set_language(language_code)

    @classmethod
    async def from_user(cls, dispatcher: Dispatcher, bot: Bot, user_id: int) -> Manager | None:
        storage: Storage = dispatcher["storage"]
        user = await storage.get_user(user_id)
        if user is None:
            return None
        state = dispatcher.fsm.get_context(bot, user_id, user_id)
        return cls(bot, dispatcher["config"], storage, state, user, user.language_code)

    def set_language(self, language_code: str | None) -> None:
        self.text_button = TextButton(language_code)
        self.text_message = TextMessage(language_code)

    async def send_loader_message(self) -> None:
        await self.send_message(self.text_message.get("loader_text"))

    async def send_message(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        send_mode: SendMode = SendMode.EDIT,
    ) -> None:
        message_id = (await self.state.get_data()).get("message_id")
        if send_mode == SendMode.EDIT and message_id is not None:
            try:
                await self.bot.edit_message_text(
                    text=text,
                    chat_id=self.user.id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                )
                return
            except TelegramBadRequest as ex:
                if "message is not modified" in ex.message:
                    return
                if not any(error in ex.message for error in MESSAGE_EDIT_ERRORS):
                    raise
        message = await self.bot.send_message(chat_id=self.user.id, text=text, reply_markup=reply_markup)
        await self.state.update_data(message_id=message.message_id)
        if message_id is not None:
            await self.blank_screen(message_id)

    # Messages older than 48 hours can't be deleted, the old screen is blanked instead
    async def blank_screen(self, message_id: int) -> None:
        try:
            await self.bot.delete_message(chat_id=self.user.id, message_id=message_id)
        except TelegramBadRequest as ex:
            if not any(error in ex.message for error in MESSAGE_DELETE_ERRORS):
                raise
            with suppress(TelegramBadRequest):
                await self.bot.edit_message_text(
                    text=self.text_message.get("outdated_text"),
                    chat_id=self.user.id,
                    message_id=message_id,
                )
