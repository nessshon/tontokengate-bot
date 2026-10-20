import asyncio
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from typing import Any, Protocol

from redis.asyncio import Redis

from .models import AdminData, ChatData, TokenData, UserData, now

USERS = "users"
CHATS = "chats"
TOKENS = "tokens"
ADMINS = "admins"


def members_key(chat_id: int) -> str:
    return f"members:{chat_id}"


def holders_key(token_address: str) -> str:
    return f"holders:{token_address}"


class Record(Protocol):
    created_at: str


class Storage:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.lock = asyncio.Lock()

    async def _get[T](self, key: str, field: int | str, record: Callable[..., T]) -> T | None:
        raw = await self.redis.hget(key, str(field))
        return None if raw is None else record(**json.loads(raw))

    async def _all[T: Record](self, key: str, record: Callable[..., T]) -> list[T]:
        records = [record(**json.loads(raw)) for raw in await self.redis.hvals(key)]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    async def _put(self, key: str, field: int | str, record: Any) -> None:
        await self.redis.hset(key, str(field), json.dumps(asdict(record)))

    async def get_user(self, user_id: int) -> UserData | None:
        return await self._get(USERS, user_id, UserData)

    async def users(self) -> list[UserData]:
        return await self._all(USERS, UserData)

    async def upsert_user(self, user_id: int, full_name: str, username: str | None) -> UserData:
        user = await self.get_user(user_id)
        if user is not None and (user.full_name, user.username) == (full_name, username):
            return user
        async with self.lock:
            user = await self.get_user(user_id)
            if user is None:
                user = UserData(id=user_id, full_name=full_name, username=username, created_at=now())
            elif (user.full_name, user.username) == (full_name, username):
                return user
            else:
                user = replace(user, full_name=full_name, username=username)
            await self._put(USERS, user_id, user)
        return user

    async def patch_user(self, user_id: int, **fields: Any) -> UserData | None:
        async with self.lock:
            user = await self.get_user(user_id)
            if user is None:
                return None
            user = replace(user, **fields)
            await self._put(USERS, user_id, user)
        return user

    async def get_chat(self, chat_id: int) -> ChatData | None:
        return await self._get(CHATS, chat_id, ChatData)

    async def chats(self) -> list[ChatData]:
        return await self._all(CHATS, ChatData)

    async def save_chat(self, chat: ChatData) -> None:
        await self._put(CHATS, chat.id, chat)

    async def delete_chat(self, chat_id: int) -> ChatData | None:
        chat = await self.get_chat(chat_id)
        async with self.redis.pipeline() as pipe:
            pipe.hdel(CHATS, str(chat_id))
            pipe.delete(members_key(chat_id))
            await pipe.execute()
        return chat

    async def get_token(self, address: str) -> TokenData | None:
        return await self._get(TOKENS, address, TokenData)

    async def tokens(self) -> list[TokenData]:
        return await self._all(TOKENS, TokenData)

    async def save_token(self, token: TokenData) -> None:
        await self._put(TOKENS, token.address, token)

    async def delete_token(self, address: str) -> TokenData | None:
        token = await self.get_token(address)
        async with self.redis.pipeline() as pipe:
            pipe.hdel(TOKENS, address)
            pipe.delete(holders_key(address))
            await pipe.execute()
        return token

    async def holders(self, token_address: str) -> dict[str, int]:
        stored = await self.redis.hgetall(holders_key(token_address))
        return {address: int(amount) for address, amount in stored.items()}

    async def balance(self, token_address: str, owner: str) -> int:
        amount = await self.redis.hget(holders_key(token_address), owner)
        return int(amount) if amount else 0

    # Only the given owners: a fresh balance written meanwhile for someone else stays
    async def set_balances(self, token_address: str, owners: Sequence[str], balances: dict[str, int]) -> None:
        async with self.redis.pipeline() as pipe:
            for owner in owners:
                if amount := balances.get(owner, 0):
                    pipe.hset(holders_key(token_address), owner, str(amount))
                else:
                    pipe.hdel(holders_key(token_address), owner)
            await pipe.execute()

    async def get_admin(self, user_id: int) -> AdminData | None:
        return await self._get(ADMINS, user_id, AdminData)

    async def admins(self) -> list[AdminData]:
        return await self._all(ADMINS, AdminData)

    async def add_admin(self, admin: AdminData) -> bool:
        return bool(await self.redis.hsetnx(ADMINS, str(admin.user_id), json.dumps(asdict(admin))))

    async def remove_admin(self, user_id: int) -> AdminData | None:
        admin = await self.get_admin(user_id)
        await self.redis.hdel(ADMINS, str(user_id))
        return admin

    async def admin_ids(self, *fixed_ids: int) -> list[int]:
        stored_ids = [int(user_id) for user_id in await self.redis.hkeys(ADMINS)]
        return list(dict.fromkeys([*fixed_ids, *stored_ids]))

    async def add_member(self, chat_id: int, user_id: int) -> None:
        await self.redis.sadd(members_key(chat_id), user_id)

    async def remove_member(self, chat_id: int, user_id: int) -> None:
        await self.redis.srem(members_key(chat_id), user_id)

    async def members(self, chat_id: int) -> set[int]:
        return {int(user_id) for user_id in await self.redis.smembers(members_key(chat_id))}
