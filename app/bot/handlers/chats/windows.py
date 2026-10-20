from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.markdown import hbold, hcode, hlink

from app.bot import keyboards
from app.bot.manager import Manager
from app.bot.utils import buy_url, token_amount
from app.config import Config
from app.indexer import raw_address
from app.storage import TokenData, UserData
from app.texts import TextMessage

TOP_SIZE = 10


def group_text(config: Config) -> TextMessage:
    return TextMessage(config.bot.GROUP_LANGUAGE)


async def balance_text(
    manager: Manager,
    user: UserData | None,
    full_name: str,
    text_key: str,
    empty_key: str,
) -> str:
    balances = []
    if user and user.wallet_address:
        owner = raw_address(user.wallet_address)
        for token in await manager.storage.tokens():
            if amount := await manager.storage.balance(token.address, owner):
                name = hlink(token.name, buy_url(token, manager.config.DEX_NAME))
                balances.append(f"{name} - {hcode(token_amount(token, amount))}")

    texts = group_text(manager.config)
    if not balances:
        return texts.get(empty_key).format(user_full_name=hbold(full_name))
    return texts.get(text_key).format(user_full_name=hbold(full_name), balances="\n".join(balances))


def top_select_token(manager: Manager, tokens: list[TokenData]) -> tuple[str, InlineKeyboardMarkup]:
    return group_text(manager.config).get("top_select_token"), keyboards.select_tokens(tokens)


async def top_text(manager: Manager, token: TokenData) -> str:
    holders = await manager.storage.holders(token.address)
    top = []
    for user in await manager.storage.users():
        if user.wallet_address and (amount := holders.get(raw_address(user.wallet_address), 0)):
            top.append((hlink(user.full_name, user.url), amount))
    top.sort(key=lambda item: item[1], reverse=True)

    rows = [
        f"{rank}. {name} - {hcode(token_amount(token, amount))}"
        for rank, (name, amount) in enumerate(top[:TOP_SIZE], start=1)
    ]
    texts = group_text(manager.config)
    return texts.get("top_holders").format(top_holders="\n".join(rows)) if rows else texts.get("top_holders_empty")


def kicked_text(config: Config, user_id: int, user: UserData | None) -> str:
    name = hlink(user.full_name, user.url) if user else hlink(str(user_id), f"tg://user?id={user_id}")
    return group_text(config).get("user_kicked").format(user=name)
