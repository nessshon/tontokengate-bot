import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from pydantic_core import PydanticSerializationError

from app.bot.utils import report_exception
from app.config import Config

logger = logging.getLogger(__name__)
router = Router()


@router.errors(ExceptionTypeFilter(TelegramBadRequest), F.exception.message.contains("query is too old"))
async def query_too_old(_: ErrorEvent) -> None:
    pass


@router.errors(ExceptionTypeFilter(TelegramForbiddenError), F.exception.message.contains("bot was blocked by the user"))
async def bot_blocked(_: ErrorEvent) -> None:
    pass


@router.errors()
async def handler(event: ErrorEvent, bot: Bot, config: Config) -> None:
    update_id = event.update.update_id
    logger.error("Update %s failed: %r", update_id, event.exception, exc_info=event.exception)

    try:
        update = event.update.model_dump_json(indent=2, exclude_none=True)
    except PydanticSerializationError:
        update = repr(event.update)
    await report_exception(bot, config.bot.ADMIN_ID, event.exception, str(update_id), f"\n{update}")
