from dataclasses import dataclass

from environs import Env, validate

from app.texts import SUPPORTED_LANGUAGES

DEX_URLS = {
    "dedust": "https://dedust.io/swap/GRAM/",
    "stonfi": "https://app.ston.fi/swap?chartVisible=false&ft=GRAM&tt=",
    "swapcoffee": "https://swap.coffee/dex?ft=GRAM&st=",
}


@dataclass
class BotConfig:
    TOKEN: str
    ADMIN_ID: int
    GROUP_LANGUAGE: str


@dataclass
class RedisConfig:
    HOST: str
    PORT: int
    DB: int
    USERNAME: str | None
    PASSWORD: str | None


@dataclass
class IndexerConfig:
    KEY: str | None
    RPS: int | None


@dataclass
class Config:
    bot: BotConfig
    redis: RedisConfig
    indexer: IndexerConfig

    DEX_NAME: str
    IS_TESTNET: bool
    MANIFEST_URL: str
    WALLETS: list[str]
    CHECK_INTERVAL: int


def load_config() -> Config:
    env = Env()
    env.read_env()

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            ADMIN_ID=env.int("BOT_ADMIN_ID"),
            GROUP_LANGUAGE=env.str("BOT_GROUP_LANGUAGE", "ru", validate=validate.OneOf(SUPPORTED_LANGUAGES)),
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST"),
            PORT=env.int("REDIS_PORT"),
            DB=env.int("REDIS_DB"),
            USERNAME=env.str("REDIS_USERNAME", None) or None,
            PASSWORD=env.str("REDIS_PASSWORD", None) or None,
        ),
        indexer=IndexerConfig(
            KEY=env.str("TONCENTER_KEY", None) or None,
            RPS=env.int("TONCENTER_RPS", None, validate=validate.Range(min=1)),
        ),
        DEX_NAME=env.str("DEX_NAME", "", validate=validate.OneOf(["", *DEX_URLS])) or "swapcoffee",
        IS_TESTNET=env.bool("IS_TESTNET"),
        MANIFEST_URL=env.str("MANIFEST_URL"),
        WALLETS=[name.strip() for name in env.list("WALLETS", [], subcast=str)],
        CHECK_INTERVAL=env.int("CHECK_INTERVAL", 5, validate=validate.Range(min=1)),
    )
