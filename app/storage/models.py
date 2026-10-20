from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class UserData:
    id: int
    full_name: str
    username: str | None
    created_at: str
    language_code: str | None = None
    wallet_address: str | None = None

    @property
    def url(self) -> str:
        if self.username:
            return f"https://t.me/{self.username.removeprefix('@')}"
        return f"tg://user?id={self.id}"


@dataclass
class ChatData:
    id: int
    name: str
    type: str
    invite_link: str
    created_at: str


class TokenType(StrEnum):
    NFT = "nft_collection"
    JETTON = "jetton_master"


@dataclass
class TokenData:
    address: str
    name: str
    type: str
    min_amount: int
    created_at: str
    decimals: int | None = None


@dataclass
class AdminData:
    user_id: int
    full_name: str
    username: str | None
    created_at: str
