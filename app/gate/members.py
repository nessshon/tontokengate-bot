import asyncio
import logging
from collections.abc import Sequence
from contextlib import suppress
from datetime import timedelta
from typing import NamedTuple

from aiogram import Bot, html
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.utils.markdown import hbold

from app.bot.utils import admin_texts, missing_rights, notify_admin, report_exception, rights_text
from app.config import Config
from app.indexer import Indexer, raw_address
from app.storage import ChatData, Storage, TokenData, UserData

from .holders import user_is_holder

logger = logging.getLogger(__name__)

# Telegram makes a ban under 30 seconds permanent; minutes leave room for a skewed host clock
KICK_BAN = timedelta(minutes=5)


class ChatProblem(NamedTuple):
    chat: ChatData
    missing: list[str]
    error: str = ""


async def run_checks(
    bot: Bot,
    config: Config,
    storage: Storage,
    indexer: Indexer,
) -> None:
    # Chats the admin was told about, until they pass a check again
    reported: set[int] = set()
    while True:
        try:
            problems = await check_members(bot, storage, indexer)
            for problem in problems:
                if problem.chat.id in reported:
                    continue
                texts = await admin_texts(config, storage)
                if problem.missing:
                    text = rights_text(texts, problem.chat.name, problem.missing)
                else:
                    text = texts.get("chat_check_failed").format(
                        chat=hbold(problem.chat.name), error=html.quote(problem.error)
                    )
                await notify_admin(bot, config, text)
            reported = {problem.chat.id for problem in problems}
        except Exception as ex:
            logger.exception("Member check failed")
            with suppress(TelegramAPIError):
                await report_exception(bot, config.bot.ADMIN_ID, ex, "member_check")
        await asyncio.sleep(config.CHECK_INTERVAL * 60)


async def check_members(bot: Bot, storage: Storage, indexer: Indexer) -> list[ChatProblem]:
    tokens = await storage.tokens()
    # Until an admin adds a token, nobody can hold it: kicking everyone would empty the chats
    if not tokens:
        return []
    owners = [raw_address(user.wallet_address) for user in await storage.users() if user.wallet_address]
    balances = await indexer.balances(tokens, owners)
    # No bot user may hold a token at all; it is an indexer gap only if nobody on chain holds it either
    empty = [token for token in tokens if owners and not balances[token.address]]
    if gaps := [token.name for token in empty if not await indexer.has_holders(token)]:
        logger.warning("Member check skipped, no holders of %s", ", ".join(gaps))
        return []
    for token in tokens:
        await storage.set_balances(token.address, owners, balances[token.address])

    problems = []
    for chat in await storage.chats():
        try:
            if problem := await check_chat(bot, storage, indexer, chat, tokens):
                problems.append(problem)
        except TelegramAPIError as ex:
            logger.warning("Members of chat %s are not checked: %s", chat.id, ex)
            problems.append(ChatProblem(chat, [], ex.message))
    return problems


async def check_chat(
    bot: Bot,
    storage: Storage,
    indexer: Indexer,
    chat: ChatData,
    tokens: Sequence[TokenData],
) -> ChatProblem | None:
    administrators = await bot.get_chat_administrators(chat.id)
    missing = missing_rights(next((member for member in administrators if member.user.id == bot.id), None))
    # Without the ban right nobody can be removed: the members wait until the right is back
    if "can_restrict_members" in missing:
        return ChatProblem(chat, missing)
    admins = {member.user.id for member in administrators}
    suspects: list[tuple[int, UserData | None]] = []
    for user_id in await storage.members(chat.id) - admins:
        user = await storage.get_user(user_id)
        if not (user and await user_is_holder(storage, user, tokens)):
            suspects.append((user_id, user))

    # The pass balances may be older than a join request in the meantime: only a fresh answer removes a member
    owners = [raw_address(user.wallet_address) for _, user in suspects if user and user.wallet_address]
    if owners:
        balances = await indexer.balances(tokens, owners)
        for token in tokens:
            await storage.set_balances(token.address, owners, balances[token.address])

    error = ""
    for user_id, user in suspects:
        if not (user and await user_is_holder(storage, user, tokens)):
            error = await kick(bot, storage, chat.id, user_id) or error
    return ChatProblem(chat, missing, error) if missing or error else None


async def kick(bot: Bot, storage: Storage, chat_id: int, user_id: int) -> str | None:
    try:
        await bot.ban_chat_member(chat_id, user_id, until_date=KICK_BAN)
    except TelegramBadRequest as ex:
        logger.warning("User %s is not removed from chat %s: %s", user_id, chat_id, ex.message)
        return ex.message
    # The chat_member update of this ban announces it, so a member who already left is removed silently
    await storage.remove_member(chat_id, user_id)
    logger.info("User %s is removed from chat %s", user_id, chat_id)
    return None
