from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import TelegramObject, User

from app.bot.manager import Manager
from app.storage import Storage


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or user.is_bot:
            return await handler(event, data)

        bot: Bot = data["bot"]
        dispatcher: Dispatcher = data["dispatcher"]
        storage: Storage = data["storage"]

        username = f"@{user.username}" if user.username else None
        user_data = await storage.upsert_user(user.id, user.full_name, username)
        language_code = user_data.language_code or user.language_code

        state = dispatcher.fsm.get_context(bot, user.id, user.id)
        data["manager"] = Manager(bot, data["config"], storage, state, user_data, language_code)
        return await handler(event, data)
