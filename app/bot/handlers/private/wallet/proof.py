import logging
import secrets
from typing import Any
from urllib.parse import urlsplit

from nacl.exceptions import BadSignatureError
from ton_connect import VerifyTonProof, create_ton_proof_payload, verify_ton_proof_payload
from ton_connect.models import Wallet

from app.indexer import Indexer, IndexerError

from .errors import ConnectError

logger = logging.getLogger(__name__)

PROOF_TTL = 300
PROOF_SECRET = secrets.token_hex(32)


# Wallets sign ton_proof for the host of the manifest's url field; the bot keeps it the host of MANIFEST_URL too
def manifest_domain(manifest_url: str, manifest: Any) -> str:
    url = str(manifest.get("url") or "") if isinstance(manifest, dict) else ""
    domain = urlsplit(url).netloc.lower()
    if not domain:
        raise ValueError(
            "The manifest at MANIFEST_URL needs a url field with the full app address, like https://example.com"
        )
    if urlsplit(url).hostname != urlsplit(manifest_url).hostname:
        raise ValueError(f"The manifest url {url} and MANIFEST_URL {manifest_url} must be on one domain")
    return domain


def proof_payload() -> str:
    return create_ton_proof_payload(PROOF_SECRET, PROOF_TTL)


async def check_proof(wallet: Wallet, domain: str, indexer: Indexer) -> ConnectError | None:
    dto = wallet.ton_proof_dto
    if dto is None:
        return ConnectError.PROOF
    try:
        verify_ton_proof_payload(PROOF_SECRET, dto.proof.payload)
        await VerifyTonProof(dto).verify(
            allowed_domains=[domain],
            valid_auth_time=PROOF_TTL,
            get_wallet_public_key=indexer.public_key,
        )
    except BadSignatureError:
        return ConnectError.PROOF
    except IndexerError as ex:
        logger.warning("Public key of wallet %s is unknown: %s", wallet.account.address.to_str(), ex)
        return ConnectError.FAILED
    return None
