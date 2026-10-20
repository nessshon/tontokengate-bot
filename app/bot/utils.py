import traceback
from collections.abc import Sequence
from contextlib import suppress
from datetime import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, ChatMember, TelegramObject, User
from aiogram.utils.markdown import hbold, hcode, hlink
from cachetools import TTLCache

from app.config import DEX_URLS, Config
from app.indexer import DEFAULT_DECIMALS
from app.storage import Storage, TokenData, TokenType
from app.texts import TextMessage

GETGEMS_COLLECTION_URL = "https://getgems.io/collection/"
TONVIEWER_URL = "https://tonviewer.com/"
MAX_AMOUNT = 2**120
# The join-request link, approving and declining requests need the first; removing a member needs the second
BOT_RIGHTS = ("can_invite_users", "can_restrict_members")

_reported: TTLCache[tuple[str, str], None] = TTLCache(maxsize=1_000, ttl=600)


# The same error reaches the admin at most once per 10 minutes: a broken chat fails on every pass
async def report_exception(bot: Bot, admin_id: int, exception: BaseException, name: str, details: str = "") -> None:
    key = (type(exception).__name__, str(exception))
    if key in _reported:
        return
    _reported[key] = None

    log = "".join(traceback.format_exception(exception)) + details
    document = BufferedInputFile(log.encode(), filename=f"error_{name}.txt")
    # A caption is limited to 1024 characters
    caption = f"{hbold(type(exception).__name__)}: {hcode(str(exception)[:900])}"
    await bot.send_document(admin_id, document, caption=caption)


async def admin_texts(config: Config, storage: Storage) -> TextMessage:
    admin = await storage.get_user(config.bot.ADMIN_ID)
    return TextMessage(admin.language_code if admin else None)


async def notify_admin(bot: Bot, config: Config, text: str) -> None:
    with suppress(TelegramAPIError):
        await bot.send_message(config.bot.ADMIN_ID, text)


def missing_rights(member: ChatMember | None) -> list[str]:
    return [right for right in BOT_RIGHTS if not getattr(member, right, False)]


def rights_list(texts: TextMessage, missing: Sequence[str]) -> str:
    return ", ".join(texts.get(f"right_{right}") for right in missing)


def rights_text(texts: TextMessage, chat_name: str, missing: Sequence[str]) -> str:
    return texts.get("chat_rights_missing").format(chat=hbold(chat_name), rights=rights_list(texts, missing))


async def is_admin(_: TelegramObject, event_from_user: User, storage: Storage, config: Config) -> bool:
    return event_from_user.id in await storage.admin_ids(config.bot.ADMIN_ID)


def tonviewer_link(address: str, name: str | None = None) -> str:
    return hlink(name or f"{address[:4]}...{address[-4:]}", TONVIEWER_URL + address)


def buy_url(token: TokenData, dex_name: str) -> str:
    base_url = GETGEMS_COLLECTION_URL if token.type == TokenType.NFT else DEX_URLS[dex_name]
    return base_url + token.address


def token_amount(token: TokenData, amount: int) -> str:
    if token.type == TokenType.NFT:
        return str(amount)
    decimals = DEFAULT_DECIMALS if token.decimals is None else token.decimals
    # Integer math: Decimal's 28-digit context fails on a huge balance; the fraction is cut to 9 digits
    whole, fraction = divmod(amount, 10**decimals)
    digits = str(fraction).rjust(decimals, "0")[:9].rstrip("0")
    return f"{whole}.{digits}" if digits else str(whole)


def date_string(created_at: str) -> str:
    return datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")


def paginate[T](items: list[T], page: int, page_size: int) -> tuple[list[T], int]:
    total_pages = (len(items) + page_size - 1) // page_size
    return items[(page - 1) * page_size : page * page_size], total_pages


def parse_min_amount(text: str, token_type: str, decimals: int | None) -> int | None:
    try:
        value = Decimal(text.strip().replace(",", "."))
        if token_type == TokenType.JETTON:
            value = value.scaleb(decimals or 0)
    except ArithmeticError:
        return None
    # A jetton amount is a VarUInteger 16 on chain: a larger minimum is a typo
    if not value.is_finite() or not 0 < value < MAX_AMOUNT or value != value.to_integral_value():
        return None
    return int(value)
