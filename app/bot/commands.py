from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat


async def bot_commands_setup(bot: Bot) -> None:
    commands = {
        "en": [
            BotCommand(command="start", description="Restart bot"),
        ],
        "ru": [
            BotCommand(command="start", description="Перезапустить бота"),
        ],
    }
    await bot.set_my_commands(commands=commands["en"], scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=commands["ru"], scope=BotCommandScopeAllPrivateChats(), language_code="ru")

    chat_commands = {
        "en": [
            BotCommand(command="top", description="Top holders"),
            BotCommand(command="balance", description="Display balance"),
        ],
        "ru": [
            BotCommand(command="top", description="ТОП держателей"),
            BotCommand(command="balance", description="Отобразить баланс"),
        ],
    }
    await bot.set_my_commands(commands=chat_commands["en"], scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(commands=chat_commands["ru"], scope=BotCommandScopeAllGroupChats(), language_code="ru")


async def bot_commands_delete(bot: Bot) -> None:
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats(), language_code="ru")
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats(), language_code="ru")


async def bot_admin_commands_setup(bot: Bot, admins_ids: list[int]) -> None:
    admin_commands = {
        "en": [
            BotCommand(command="start", description="Restart bot"),
            BotCommand(command="admin", description="Admin panel"),
        ],
        "ru": [
            BotCommand(command="start", description="Перезапустить бота"),
            BotCommand(command="admin", description="Панель администратора"),
        ],
    }
    for admin_id in admins_ids:
        scope = BotCommandScopeChat(chat_id=admin_id)
        with suppress(TelegramBadRequest):
            await bot.set_my_commands(commands=admin_commands["en"], scope=scope)
        with suppress(TelegramBadRequest):
            await bot.set_my_commands(commands=admin_commands["ru"], scope=scope, language_code="ru")


async def bot_admin_commands_delete(bot: Bot, admins_ids: list[int]) -> None:
    for admin_id in admins_ids:
        scope = BotCommandScopeChat(chat_id=admin_id)
        with suppress(TelegramBadRequest):
            await bot.delete_my_commands(scope=scope)
        with suppress(TelegramBadRequest):
            await bot.delete_my_commands(scope=scope, language_code="ru")
