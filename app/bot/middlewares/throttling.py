from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject, User
from cachetools import TTLCache

RATE = 0.5


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.recent: TTLCache[int, None] = TTLCache(maxsize=10_000, ttl=RATE)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any | None:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if user.id in self.recent:
            if isinstance(event, CallbackQuery):
                await event.answer()
            elif isinstance(event, Message):
                with suppress(TelegramBadRequest):
                    await event.delete()
            return None

        self.recent[user.id] = None
        return await handler(event, data)
