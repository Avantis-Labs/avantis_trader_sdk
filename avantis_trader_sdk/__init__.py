"""Avantis v2 Python SDK — API-first perpetuals trading on Base.

Quick start (relayer route, delegate key from the Avantis UI):

    export AVANTIS_PRIVATE_KEY=0x...      # your API/agent key
    export AVANTIS_TRADER_ADDRESS=0x...   # your wallet

    from avantis_trader_sdk import AsyncAvantis

    async def main():
        async with AsyncAvantis() as client:
            await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
"""

from ._version import __version__
from .client import AsyncAvantis, Avantis
from .config import MAINNET, TESTNET, AvantisConfig
from .errors import (
    ApiError,
    AvantisError,
    ConfigError,
    DelegationError,
    DigestMismatchError,
    RelayError,
    RpcError,
    SigningError,
    ValidationError,
)
from .execution import BatchedMarketEvent
from .signing import BaseSigner, LocalSigner, sign_intent
from .types import (
    ExecutionMode,
    ExecutionReceipt,
    IntentPayload,
    MarginAction,
    OrderType,
    Side,
    TriggerType,
)

__all__ = [
    "__version__",
    "AsyncAvantis",
    "Avantis",
    "AvantisConfig",
    "TESTNET",
    "MAINNET",
    "BaseSigner",
    "LocalSigner",
    "sign_intent",
    "ExecutionMode",
    "ExecutionReceipt",
    "BatchedMarketEvent",
    "IntentPayload",
    "Side",
    "OrderType",
    "MarginAction",
    "TriggerType",
    "AvantisError",
    "ApiError",
    "ConfigError",
    "ValidationError",
    "SigningError",
    "DigestMismatchError",
    "RelayError",
    "RpcError",
    "DelegationError",
]
