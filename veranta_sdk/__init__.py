"""Veranta v2 Python SDK: API-first perpetuals trading on Base.

Quick start (relayer route, delegate key from the Veranta UI):

    export VERANTA_PRIVATE_KEY=0x...      # your API/agent key
    export VERANTA_TRADER_ADDRESS=0x...   # your wallet

    from veranta_sdk import AsyncVeranta

    async def main():
        async with AsyncVeranta() as client:
            await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
"""

from ._version import __version__
from .client import AsyncVeranta, Veranta
from .config import MAINNET, TESTNET, VerantaConfig
from .errors import (
    ApiError,
    ConfigError,
    DelegationError,
    DigestMismatchError,
    RelayError,
    RpcError,
    SigningError,
    ValidationError,
    VerantaError,
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

# Pre-rename names (Avantis is now Veranta): importable for one release cycle
# with a DeprecationWarning, e.g. `from veranta_sdk import AsyncAvantis`.
_DEPRECATED_ALIASES = {
    "AsyncAvantis": "AsyncVeranta",
    "Avantis": "Veranta",
    "AvantisConfig": "VerantaConfig",
    "AvantisError": "VerantaError",
}


def __getattr__(name: str):  # noqa: ANN202 - module-level PEP 562 hook
    target = _DEPRECATED_ALIASES.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import warnings

    warnings.warn(
        f"veranta_sdk.{name} is deprecated (Avantis is now Veranta); use veranta_sdk.{target}",
        DeprecationWarning,
        stacklevel=2,
    )
    return globals()[target]


__all__ = [
    "__version__",
    "AsyncVeranta",
    "Veranta",
    "VerantaConfig",
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
    "VerantaError",
    "ApiError",
    "ConfigError",
    "ValidationError",
    "SigningError",
    "DigestMismatchError",
    "RelayError",
    "RpcError",
    "DelegationError",
]
