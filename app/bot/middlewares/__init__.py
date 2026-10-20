from aiogram import Dispatcher
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

from .throttling import ThrottlingMiddleware
from .user import UserMiddleware


def register_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware.register(UserMiddleware())

    throttling_middleware = ThrottlingMiddleware()
    dp.message.middleware.register(throttling_middleware)
    dp.callback_query.middleware.register(throttling_middleware)
    dp.callback_query.middleware.register(CallbackAnswerMiddleware())


__all__ = ["register_middlewares"]
