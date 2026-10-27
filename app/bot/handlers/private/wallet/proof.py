import hashlib
from typing import Any
from urllib.parse import urlsplit

PROOF_TTL = 300


# The challenges outlive restarts, so the key must too; the token is the secret the bot already keeps
def proof_secret(bot_token: str) -> str:
    return hashlib.sha256(f"ton_proof:{bot_token}".encode()).hexdigest()


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
