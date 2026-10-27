from aiogram import Dispatcher

from . import admin, chats, errors, private
from .private import wallet


# private goes first: /start must win over the admin text input expected in an admin state
def include_routers(dp: Dispatcher) -> None:
    dp.include_routers(
        private.router,
        wallet.router,
        admin.router,
        chats.router,
        errors.router,
    )


__all__ = ["include_routers"]
