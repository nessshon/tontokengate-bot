from aiogram import Dispatcher

from . import admin, chats, errors, private


# private goes first: /start must win over the admin text input expected in an admin state
def include_routers(dp: Dispatcher) -> None:
    dp.include_routers(
        private.router,
        admin.router,
        chats.router,
        errors.router,
    )


__all__ = ["include_routers"]
