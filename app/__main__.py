import asyncio
import logging
from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_tonconnect import TonProof, setup_tonconnect
from redis.asyncio import Redis
from ton_connect import AppWalletsLoader
from ton_core import NetworkGlobalID, load_json

from .bot.commands import (
    bot_admin_commands_delete,
    bot_admin_commands_setup,
    bot_commands_delete,
    bot_commands_setup,
)
from .bot.handlers import include_routers
from .bot.handlers.private.wallet import PROOF_TTL, WalletView, manifest_domain, proof_secret
from .bot.middlewares import register_middlewares
from .bot.middlewares.retry_after import RetryMiddleware
from .config import Config, load_config
from .gate import run_checks
from .indexer import Indexer
from .storage import Storage

logger = logging.getLogger(__name__)

WALLETS_FALLBACK = Path(__file__).parents[1] / "data" / "wallets.json"


async def on_startup(
    dispatcher: Dispatcher,
    bot: Bot,
    config: Config,
    storage: Storage,
    indexer: Indexer,
) -> None:
    admins_ids = await storage.admin_ids(config.bot.ADMIN_ID)
    await bot_commands_setup(bot)
    await bot_admin_commands_setup(bot, admins_ids)

    dispatcher["checks"] = asyncio.create_task(run_checks(bot, config, storage, indexer))


async def on_shutdown(
    dispatcher: Dispatcher,
    bot: Bot,
    config: Config,
    storage: Storage,
) -> None:
    checks: asyncio.Task[None] = dispatcher["checks"]
    checks.cancel()
    with suppress(asyncio.CancelledError):
        await checks
    admins_ids = await storage.admin_ids(config.bot.ADMIN_ID)
    await bot_commands_delete(bot)
    await bot_admin_commands_delete(bot, admins_ids)


async def main() -> None:
    config = load_config()
    redis = Redis(
        host=config.redis.HOST,
        port=config.redis.PORT,
        db=config.redis.DB,
        username=config.redis.USERNAME,
        password=config.redis.PASSWORD,
        decode_responses=True,
    )
    await redis.ping()

    bot = Bot(token=config.bot.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(RetryMiddleware())
    indexer = Indexer(config.indexer.KEY, config.indexer.RPS, config.IS_TESTNET)

    dp = Dispatcher(storage=RedisStorage(redis), config=config, indexer=indexer)
    # Dispatcher(storage=...) is the FSM storage, so the bot data goes in separately
    dp["storage"] = Storage(redis)

    loader = AppWalletsLoader(
        include_wallets=config.WALLETS,
        order_wallets=config.WALLETS,
        fallback_path=WALLETS_FALLBACK,
    )
    # A Telegram button opens a wallet only by its universal link
    wallets = [wallet for wallet in await asyncio.to_thread(loader.get_wallets) if wallet.universal_url]
    if unknown := set(config.WALLETS) - {wallet.app_name for wallet in wallets}:
        logger.warning("WALLETS not in the catalog or without a universal link: %s", ", ".join(sorted(unknown)))
    if not wallets:
        raise ValueError("WALLETS has no wallet from https://config.ton.org/wallets-v2.json")

    try:
        manifest = await asyncio.to_thread(load_json, config.MANIFEST_URL)
    except RuntimeError as ex:
        raise ValueError(f"MANIFEST_URL is not readable, put the manifest where the bot can load it: {ex}") from ex
    proof_domain = manifest_domain(config.MANIFEST_URL, manifest)

    ton_proof = TonProof(
        domain=proof_domain,
        secret=proof_secret(config.bot.TOKEN),
        ttl=PROOF_TTL,
        get_wallet_public_key=indexer.public_key,
    )
    setup_tonconnect(
        dp,
        bot,
        manifest_url=config.MANIFEST_URL,
        view=WalletView(dp["storage"]),
        wallets=wallets,
        network=NetworkGlobalID.TESTNET if config.IS_TESTNET else NetworkGlobalID.MAINNET,
        ton_proof=ton_proof,
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    # Dispatcher registers closing its FSM storage, and with it the shared Redis, first: it goes last
    dp.shutdown.handlers.append(dp.shutdown.handlers.pop(0))
    register_middlewares(dp)
    include_routers(dp)

    await indexer.start()
    try:
        await bot.delete_webhook()
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await indexer.close()
        await redis.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # One INFO line per update floods the log; handler failures still come through as ERROR
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    asyncio.run(main())
