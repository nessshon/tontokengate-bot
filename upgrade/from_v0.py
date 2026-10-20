# Moves the data of a 0.x bot from its SQLite file into Redis, see from_v0.md next to it
import asyncio
import json
import sqlite3
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from redis.asyncio import Redis

from app.bot.utils import parse_min_amount
from app.config import load_config
from app.indexer import Indexer, IndexerError
from app.storage import AdminData, ChatData, TokenData, TokenType, UserData
from app.storage.storage import ADMINS, CHATS, TOKENS, USERS, members_key


# SQLite kept UTC time without a zone, as "2024-05-01 12:00:00.123456"
def iso(value: str) -> str:
    return datetime.fromisoformat(value).replace(tzinfo=UTC).isoformat(timespec="seconds")


# Users without a username were stored as "@None"
def username(value: str | None) -> str | None:
    return None if value in (None, "@None") else value


async def old_tokens(connection: sqlite3.Connection, indexer: Indexer) -> tuple[list[TokenData], list[str]]:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tokens)")}
    tokens, notes = [], []
    for row in connection.execute("SELECT * FROM tokens"):
        label = f"{row['name']} {row['address']}"
        decimals = row["decimals"] if "decimals" in columns else None
        min_amount = int(row["min_amount"])
        # 1.0 takes only a minimum above zero: zero would let in every wallet owner
        if row["min_amount"] <= 0:
            notes.append(f"{label}: minimum {row['min_amount']} lets everyone in, add it again in the admin menu")
            continue
        # Before March 2025 a jetton minimum was kept in whole tokens and the decimals were not stored
        if row["type"] == TokenType.JETTON and decimals is None:
            try:
                meta = await indexer.resolve_token(row["address"])
            except IndexerError as ex:
                raise SystemExit(f"Toncenter is not available, nothing was changed, run it again: {ex}") from ex
            if meta is None or meta.type != TokenType.JETTON:
                notes.append(f"{label}: not found on Toncenter, add it again in the admin menu")
                continue
            decimals = meta.decimals
            in_units = parse_min_amount(str(row["min_amount"]), TokenType.JETTON, decimals)
            if in_units is None:
                notes.append(f"{label}: minimum {row['min_amount']} does not fit {decimals} decimals, add it again")
                continue
            min_amount = in_units
        tokens.append(
            TokenData(
                address=row["address"],
                name=row["name"],
                type=row["type"],
                min_amount=min_amount,
                created_at=iso(row["created_at"]),
                decimals=decimals,
            )
        )
    return tokens, notes


async def migrate(connection: sqlite3.Connection, redis: Redis, indexer: Indexer) -> list[str]:
    if await redis.exists(USERS, CHATS, TOKENS, ADMINS):
        raise SystemExit("Redis already has bot data, nothing was changed")

    connection.row_factory = sqlite3.Row
    users = {row["id"]: row for row in connection.execute("SELECT * FROM users")}
    tokens, notes = await old_tokens(connection, indexer)

    async with redis.pipeline(transaction=True) as pipe:
        for row in users.values():
            user = UserData(
                id=row["id"],
                full_name=row["full_name"],
                username=username(row["username"]),
                created_at=iso(row["created_at"]),
                language_code=row["language_code"],
                wallet_address=row["wallet_address"],
            )
            pipe.hset(USERS, str(user.id), json.dumps(asdict(user)))

        for row in connection.execute("SELECT * FROM chats"):
            chat = ChatData(
                id=row["id"],
                name=row["name"],
                type=row["type"],
                invite_link=row["invite_link"],
                created_at=iso(row["created_at"]),
            )
            pipe.hset(CHATS, str(chat.id), json.dumps(asdict(chat)))

        for token in tokens:
            pipe.hset(TOKENS, token.address, json.dumps(asdict(token)))

        for row in connection.execute("SELECT * FROM admins WHERE user_id IS NOT NULL"):
            user_row = users.get(row["user_id"])
            admin = AdminData(
                user_id=row["user_id"],
                full_name=user_row["full_name"] if user_row else str(row["user_id"]),
                username=username(user_row["username"]) if user_row else None,
                created_at=iso(row["created_at"]),
            )
            pipe.hsetnx(ADMINS, str(admin.user_id), json.dumps(asdict(admin)))

        for row in connection.execute("SELECT user_id, chat_id FROM members"):
            pipe.sadd(members_key(row["chat_id"]), row["user_id"])

        await pipe.execute()

    return notes


async def main(path: str) -> None:
    config = load_config()
    redis = Redis(
        host=config.redis.HOST,
        port=config.redis.PORT,
        db=config.redis.DB,
        username=config.redis.USERNAME,
        password=config.redis.PASSWORD,
        decode_responses=True,
    )
    indexer = Indexer(config.indexer.KEY, config.indexer.RPS, config.IS_TESTNET)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    await indexer.start()
    try:
        notes = await migrate(connection, redis, indexer)
        counts = {key: await redis.hlen(key) for key in (USERS, CHATS, TOKENS, ADMINS)}
    finally:
        connection.close()
        await indexer.close()
        await redis.aclose()

    print("Moved:", ", ".join(f"{key} {count}" for key, count in counts.items()))  # noqa: T201
    if notes:
        print("Check these tokens:", *notes, sep="\n  ")  # noqa: T201


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m upgrade.from_v0 <path to database.sqlite>")
    # Docker mounts a missing file as an empty folder
    if not Path(sys.argv[1]).is_file():
        raise SystemExit(f"{sys.argv[1]} is not found: copy database.sqlite of the old bot into the bot folder")
    asyncio.run(main(sys.argv[1]))
