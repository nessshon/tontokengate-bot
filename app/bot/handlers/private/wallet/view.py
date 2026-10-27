from aiogram.types import User
from aiogram_tonconnect import Texts, View

from app.storage import Storage
from app.texts import SUPPORTED_LANGUAGES, TextButton, TextMessage


def wallet_texts(language_code: str) -> Texts:
    message, button = TextMessage(language_code), TextButton(language_code)
    failed = message.get("connect_wallet_failed")
    return Texts(
        connect=message.get("connect_wallet"),
        rejected=message.get("connect_wallet_rejected"),
        timeout=message.get("connect_wallet_timeout"),
        wrong_network=message.get("connect_wallet_wrong_network"),
        bad_signature=message.get("connect_wallet_proof_wrong"),
        bad_manifest=message.get("connect_wallet_bad_manifest"),
        not_supported=failed,
        not_connected=failed,
        unavailable=failed,
        failed=failed,
        open_wallet=button.get("connect_wallet"),
        go_back=button.get("back"),
        unknown_wallet=message.get("any_wallet"),
    )


class WalletView(View):
    def __init__(self, storage: Storage) -> None:
        super().__init__(texts={code: wallet_texts(code) for code in SUPPORTED_LANGUAGES})
        self.storage = storage

    async def language(self, user: User) -> str | None:
        user_data = await self.storage.get_user(user.id)
        if user_data is not None and user_data.language_code:
            return user_data.language_code
        return await super().language(user)
