import logging
from urllib.parse import urlencode

from ton_connect import TonConnect
from ton_connect.exceptions import TonConnectError
from ton_connect.models import AppWallet
from ton_core import NetworkGlobalID

from app.bot.manager import Manager

from .. import windows
from .errors import ConnectError
from .proof import PROOF_TTL, proof_payload

logger = logging.getLogger(__name__)

QR_URL = "https://qrcode.ness.uz/create"


def qr_url(link: str, logo: str) -> str:
    return f"{QR_URL}?{urlencode({'data': link, 'size': 'large', 'style': 'rounded', 'logo': logo})}"


def app_wallet(tonconnect: TonConnect, app_name: str | None) -> AppWallet:
    wallets = tonconnect.app_wallets
    return next((wallet for wallet in wallets if wallet.app_name == app_name), wallets[0])


async def connect_wallet(manager: Manager, tonconnect: TonConnect, app_name: str | None = None) -> None:
    app_name = app_name or (await manager.state.get_data()).get("app_wallet")
    wallet = app_wallet(tonconnect, app_name)
    connector = tonconnect.connectors.get(str(manager.user.id))
    if connector is None:
        connector = tonconnect.create_connector(str(manager.user.id))
        request = connector["request"] = connector.make_connect_request(ton_proof_payload=proof_payload())
        network = NetworkGlobalID.TESTNET if manager.config.IS_TESTNET else NetworkGlobalID.MAINNET
        try:
            await connector.connect(request, network=network, timeout=PROOF_TTL)
        except TonConnectError as ex:
            logger.warning("Wallet connection of user %s is not started: %s", manager.user.id, ex)
            await connector.close()
            await windows.connect_wallet_error(manager, ConnectError.FAILED)
            return
    link = connector.make_connect_url(connector["request"], wallet)
    await windows.connect_wallet(manager, tonconnect.app_wallets, wallet, qr_url(link, wallet.image), link)
