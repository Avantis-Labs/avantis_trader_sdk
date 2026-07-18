"""Core enums and shared models for the Avantis v2 SDK.

Unit conventions (see docs/v2/RESEARCH.md §2):
- All SDK-facing amounts are HUMAN units: 100 = 100 USDC, 10 = 10x leverage,
  prices are plain decimals. The tx-builder API performs 1e6/1e10 scaling.
- Raw on-chain values (from the core API or intent messages) are decimal
  strings; models expose helpers to convert.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum, IntEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------

USDC_SCALE = Decimal(10) ** 6
PRECISION_10 = Decimal(10) ** 10  # prices, leverage, slippage %, coin exposure


def from_usdc(raw: int | str) -> Decimal:
    return Decimal(raw) / USDC_SCALE


def from_1e10(raw: int | str) -> Decimal:
    return Decimal(raw) / PRECISION_10


Num = int | float | str | Decimal
"""Human-unit numeric input. Strings are preferred for exact decimals."""


def to_api_num(value: Num) -> str:
    """Serialize a human-unit number for the API (string to avoid float artifacts)."""
    if isinstance(value, float):
        # Repr of a float is its shortest exact decimal representation.
        return repr(value)
    return str(value)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    RELAYER = "relayer"
    DIRECT = "direct"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"

    @property
    def is_long(self) -> bool:
        return self is Side.LONG


class OrderType(str, Enum):
    """Open order types (v2 enum: limit=2/MOMENTUM, stop_limit=1/REVERSAL)."""

    MARKET = "market"
    STOP_LIMIT = "stop_limit"
    LIMIT = "limit"
    MARKET_PNL = "market_pnl"


class MarginAction(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"


class TriggerType(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class AggregatorOrderType(IntEnum):
    """Order types understood by the operator relayer batch endpoints.

    Mirrors avantis-ui-v2 lib/relayerEip712.ts.
    """

    MARKET_OPEN = 0
    MARKET_CLOSE = 1
    LIMIT_OPEN = 2
    LIMIT_CLOSE = 3
    UPDATE_MARGIN = 4
    UPDATE_SL = 5
    MARKET_OPEN_PNL = 6
    MARKET_CLOSE_PNL = 7
    LIMIT_CLOSE_PNL = 8
    INCREASE_SIZE = 9
    DECREASE_SIZE = 10
    LIMIT_PARTIAL_CLOSE = 11
    MARKET_OPEN_WITH_COIN_EXPOSURE = 12
    MARKET_OPEN_PNL_WITH_COIN_EXPOSURE = 13
    INCREASE_SIZE_WITH_COIN_EXPOSURE = 14
    MARKET_CLOSE_WITH_COIN_EXPOSURE = 15
    MARKET_CLOSE_PNL_WITH_COIN_EXPOSURE = 16


class RelayAction(str, Enum):
    TX_RELAY = "TX_RELAY"
    BATCH_MARKET_EXECUTION = "BATCH_MARKET_EXECUTION"
    BATCH_POSITION_UPDATE = "BATCH_POSITION_UPDATE"


# Intent kind -> relayer batch action. Only intents the operator relayer's
# batch endpoints actually consume are listed; TWAP/RFQ initiation and
# partial TP/SL storage use different transports (TX_RELAY passthrough /
# core-API offchain orders), and delegate/referral sigs are relayed as
# *WithSig calldata.
INTENT_BATCH_ACTION: dict[str, RelayAction] = {
    "OpenTradeReq": RelayAction.BATCH_MARKET_EXECUTION,
    "OpenTradeCoinExposureReq": RelayAction.BATCH_MARKET_EXECUTION,
    "CloseTradeReq": RelayAction.BATCH_MARKET_EXECUTION,
    "CloseTradeCoinExposureReq": RelayAction.BATCH_MARKET_EXECUTION,
    "IncreasePositionSizeReq": RelayAction.BATCH_POSITION_UPDATE,
    "IncreasePositionSizeWithCoinExposureReq": RelayAction.BATCH_POSITION_UPDATE,
    "UpdateTpSlReq": RelayAction.BATCH_POSITION_UPDATE,
}


# ---------------------------------------------------------------------------
# tx-builder payload models
# ---------------------------------------------------------------------------


class CallData(BaseModel):
    """Direct-route transaction payload from the tx-builder API."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    to: str
    from_: str = Field(alias="from")
    data: str
    value: str = "0x0"
    chain_id: int = Field(alias="chainId")
    description: str | None = None
    meta: dict[str, Any] | None = None

    @property
    def value_wei(self) -> int:
        return int(self.value, 16) if self.value.startswith("0x") else int(self.value)


class IntentPayload(BaseModel):
    """EIP-712 intent payload from the tx-builder API (relayer route)."""

    model_config = ConfigDict(extra="allow")

    intent: str
    signer_rule: Literal["trader-or-delegate", "trader-only"] = Field(alias="signerRule")
    domain: dict[str, Any]
    primary_type: str = Field(alias="primaryType")
    types: dict[str, list[dict[str, str]]]
    message: dict[str, Any]
    digest: str
    encoded_intent: str = Field(alias="encodedIntent")
    meta: dict[str, Any] | None = None

    @property
    def pair_index(self) -> int:
        """Best-effort pairIndex extraction for the relayer batch payload."""
        msg = self.message
        for key in ("pairIndex", "_pairIndex"):
            if key in msg:
                return int(msg[key])
        inner = msg.get("_t") or msg.get("_updateInfo") or {}
        if "pairIndex" in inner:
            return int(inner["pairIndex"])
        raise KeyError(f"pairIndex not found in intent message for {self.intent}")


class SignedIntent(BaseModel):
    """An intent payload plus the local signature over its digest."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    payload: IntentPayload
    signature: str  # 0x-hex 65-byte r||s||v
    signer: str  # address that produced the signature


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------


class RelayStatus(BaseModel):
    settled: bool
    success: bool | None = None
    tx_hash: str | None = None
    error_message: str | None = None
    receipt: dict[str, Any] | None = None


class ExecutionReceipt(BaseModel):
    """Uniform result of submitting an action through any route."""

    route: Literal["relayer-batch", "relayer-passthrough", "rpc", "txbuilder-relay"]
    tx_hash: str | None = None
    request_id: str | None = None
    description: str | None = None
    raw: dict[str, Any] | None = None
