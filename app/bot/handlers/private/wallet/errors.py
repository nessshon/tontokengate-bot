from enum import StrEnum

from ton_connect.exceptions import (
    RequestTimeoutError,
    TonConnectError,
    UserRejectsError,
    WalletWrongNetworkError,
)


class ConnectError(StrEnum):
    TIMEOUT = "connect_wallet_timeout"
    REJECTED = "connect_wallet_rejected"
    PROOF = "connect_wallet_proof_wrong"
    NETWORK = "connect_wallet_wrong_network"
    FAILED = "connect_wallet_failed"


def connect_error(error: TonConnectError | None) -> ConnectError:
    if isinstance(error, RequestTimeoutError):
        return ConnectError.TIMEOUT
    if isinstance(error, UserRejectsError):
        return ConnectError.REJECTED
    if isinstance(error, WalletWrongNetworkError):
        return ConnectError.NETWORK
    return ConnectError.FAILED
