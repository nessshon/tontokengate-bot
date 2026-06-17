import asyncio
import logging
from typing import List

from aiogram import Bot
from pytonapi import AsyncTonapi
from pytonapi.exceptions import TONAPIInternalServerError
from pytonapi.schema.jettons import JettonHolder, JettonHolders
from pytonapi.schema.nft import NftItem, NftItems
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.utils.messages import send_message
from app.config import Config
from app.db.models import TokenDB


async def get_all_nft_items(
        config: Config,
        tonapi: AsyncTonapi,
        account_id: str,
) -> NftItems:
    nft_items: List[NftItem] = []
    interval = 1 / config.tonapi.RPS
    offset, limit = 0, 1000

    while True:
        result = await tonapi.nft.get_items_by_collection_address(
            account_id=account_id, limit=limit, offset=offset,
        )
        nft_items += result.nft_items
        offset += limit

        await asyncio.sleep(interval)
        if len(result.nft_items) == 0:
            break

    return NftItems(nft_items=nft_items)


async def get_all_jetton_holders(
        config: Config,
        tonapi: AsyncTonapi,
        account_id: str,
        min_amount: int,
) -> JettonHolders:
    jetton_holders: List[JettonHolder] = []
    interval = 1 / config.tonapi.RPS
    offset, limit = 0, 1000

    while True:
        result = await tonapi.jettons.get_holders(
            account_id=account_id, limit=limit, offset=offset,
        )
        jetton_holders += result.addresses
        offset += limit

        await asyncio.sleep(interval)
        last_balance = int(jetton_holders[-1].balance)
        if last_balance < min_amount:
            break

    return JettonHolders(addresses=jetton_holders, total=last_balance)


async def update_token_holders() -> None:
    loop = asyncio.get_event_loop()
    bot: Bot = loop.__getattribute__("bot")
    config: Config = loop.__getattribute__("config")
    tonapi: AsyncTonapi = loop.__getattribute__("tonapi")
    sessionmaker: async_sessionmaker = loop.__getattribute__("sessionmaker")

    tokens = await TokenDB.all(sessionmaker)
    for token in tokens:
        holders = {}

        try:
            if token.type == TokenDB.Type.NFTCollection:
                result = await get_all_nft_items(config, tonapi, token.address)
                collection = await tonapi.nft.get_collection_by_collection_address(token.address)
                total_holders, found_holders = collection.next_item_index, 0

                for nft in result.nft_items:
                    if nft.owner.address.to_raw() in holders:
                        holders[nft.owner.address.to_raw()] += 1
                    else:
                        holders[nft.owner.address.to_raw()] = 1
                    found_holders += 1

            else:
                result = await get_all_jetton_holders(config, tonapi, token.address, token.min_amount)
                total_holders = found_holders = result.total
                if total_holders > token.min_amount:
                    found_holders = -1

                for holder in result.addresses:
                    holders[holder.owner.address.to_raw()] = int(holder.balance)

        except TONAPIInternalServerError as e:
            logging.error(f"{e.__class__.__name__}: {e}")
            logging.error(f"Failed to update holders for {token.name} [{token.address}]")
            continue

        except Exception as e:
            await send_message(bot, config.bot.DEV_ID, text=f"{e.__class__.__name__}: {e}")
            logging.error(f"{e.__class__.__name__}: {e}")
            logging.error(f"Failed to update holders for {token.name} [{token.address}]")
            continue

        if holders and found_holders > 0:
            logging.info(f"Updated holders for {token.name} [{token.address}] (Found: {found_holders}/{total_holders})")
            await TokenDB.update(sessionmaker, primary_key=token.id, holders=holders)
        else:
            logging.error(f"Failed to update holders for {token.name} [{token.address}]")
            logging.error(f"Found holders: {found_holders}, Total Holders: {total_holders}")
