"""Local intent builder — the market-maker fast path.

Builds ready-to-sign IntentPayloads with ZERO HTTP round-trips on the hot
path: schemas/domains come from `intents_schema` (mirrored from the contracts
and proven by the golden-vector suite), the digest is computed locally, and
`encodedIntent` is abi-encoded in Solidity struct order.

Bootstrap once with `/v2/meta` (chainId + addresses), then build/sign/submit
without touching the tx-builder. The digest produced here feeds the same
`sign_intent` gate, so a schema drift still fails loudly instead of reverting
on-chain.
"""

from __future__ import annotations

import secrets
import time
from decimal import Decimal
from typing import Any

from eth_abi import encode as abi_encode
from eth_account.messages import _hash_eip191_message, encode_typed_data
from eth_utils import to_bytes, to_checksum_address

from ..errors import ConfigError
from ..intents_schema import (
    INTENT_TYPES,
    REFERRAL_INTENTS,
    TNC_STRING,
    referral_domain,
    trading_domain,
)
from ..signing.intents import _EIP712_DOMAIN_FIELDS, to_int_message
from ..types import IntentPayload

USDC = 10**6
P10 = 10**10


def _scale(value: float | int | str | Decimal, factor: int) -> int:
    """Human units -> raw integer via exact decimal scaling.

    Binary-float multiplication can truncate one unit low
    (``int(0.0003 * 1e10) == 2_999_999``, bites low-priced pair prices and
    TP/SL); a float's ``str()`` is its shortest exact decimal representation,
    so scaling through Decimal gives the raw value the user actually meant.
    """
    return int(Decimal(str(value)) * factor)


def _usdc(value: float | int | str | Decimal) -> int:
    return _scale(value, USDC)


def _p10(value: float | int | str | Decimal) -> int:
    return _scale(value, P10)

# Solidity struct component order for abi.encode(struct). Identical to the
# typed-data order except DelegateReq (declares expiry, tnc, deadline).
_ABI_ORDERS: dict[str, list[str]] = {
    "DelegateReq": ["trader", "delegate", "expiry", "tnc", "deadline", "nonce"],
}

_ABI_TYPE_MAP = {"Trade": "tuple", "UpdatePositionSize": "tuple"}

# ITradingStorage.TriggerType (partial TP/SL).
_TRIGGER_TYPE_CODES = {"fixed": 0, "percentage": 1}
# ITradingStorage.LimitOrder — partial TP/SL live at codes 4/5.
_PARTIAL_KIND_CODES = {"take_profit": 4, "tp": 4, "stop_loss": 5, "sl": 5}


def _code_bytes32(code: str) -> str:
    """Referral code as bytes32 hex: pass 0x… through, right-pad short strings."""
    if code.startswith("0x"):
        raw = to_bytes(hexstr=code)
        if len(raw) != 32:
            raise ValueError("hex referral code must be exactly 32 bytes")
        return code
    raw = code.encode()
    if len(raw) > 32:
        raise ValueError("referral code must be at most 32 bytes")
    return "0x" + raw.ljust(32, b"\x00").hex()


class NoncePool:
    """Random 256-bit unordered nonces with local dedup (parallel-order safe)."""

    def __init__(self) -> None:
        self._used: set[int] = set()

    def next(self) -> int:
        while True:
            nonce = secrets.randbits(256)
            if nonce not in self._used:
                self._used.add(nonce)
                return nonce

    def release(self, nonce: int) -> None:
        self._used.discard(nonce)


def _abi_schema(kind: str) -> tuple[str, list[str]]:
    """(abi type string, ordered field names) for the top-level struct."""
    types = INTENT_TYPES[kind]
    fields = types[kind]
    order = _ABI_ORDERS.get(kind, [f["name"] for f in fields])
    field_types = {f["name"]: f["type"] for f in fields}

    parts = []
    for name in order:
        t = field_types[name]
        if t in types:  # nested struct
            inner = ",".join(f["type"] for f in types[t])
            parts.append(f"({inner})")
        elif t == "string":
            parts.append("string")
        else:
            parts.append(t)
    return "(" + ",".join(parts) + ")", order


def _abi_values(kind: str, message: dict[str, Any]) -> list[Any]:
    types = INTENT_TYPES[kind]
    field_types = {f["name"]: f["type"] for f in types[kind]}
    _, order = _abi_schema(kind)
    values: list[Any] = []
    for name in order:
        t = field_types[name]
        v = message[name]
        if t in types:  # nested struct -> tuple in declared order
            values.append(tuple(v[f["name"]] for f in types[t]))
        elif t == "bytes32":
            values.append(to_bytes(hexstr=v) if isinstance(v, str) else v)
        else:
            values.append(v)
    return values


class LocalIntentBuilder:
    def __init__(
        self,
        chain_id: int,
        trading_router: str,
        referral: str | None = None,
        *,
        default_deadline_ms: int = 120_000,
    ) -> None:
        self.chain_id = chain_id
        self.trading_router = to_checksum_address(trading_router)
        self.referral = to_checksum_address(referral) if referral else None
        self.default_deadline_ms = default_deadline_ms
        self.nonces = NoncePool()

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> LocalIntentBuilder:
        addrs = meta["addresses"]
        return cls(int(meta["chainId"]), addrs["tradingRouter"], addrs.get("referral"))

    # ------------------------------------------------------------------ core

    def build(self, kind: str, message: dict[str, Any]) -> IntentPayload:
        """Build an IntentPayload from a raw-scale message (int or decimal-string
        values; bools stay bools)."""
        types = INTENT_TYPES[kind]
        domain = (
            referral_domain(self.chain_id, self.referral or "")
            if kind in REFERRAL_INTENTS
            else trading_domain(self.chain_id, self.trading_router)
        )
        # Canonical int-typed message: coerces int fields (accepts int or str),
        # passes bools/addresses/strings/bytes32 through untouched.
        int_message = to_int_message(types, kind, message)

        signable = encode_typed_data(
            full_message={
                "types": {"EIP712Domain": _EIP712_DOMAIN_FIELDS, **types},
                "primaryType": kind,
                "domain": domain,
                "message": int_message,
            }
        )
        digest = "0x" + _hash_eip191_message(signable).hex()
        abi_type, _ = _abi_schema(kind)
        encoded = abi_encode([abi_type], [_abi_values(kind, int_message)])

        def _stringify(value: Any) -> Any:
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return str(value)
            if isinstance(value, dict):
                return {k: _stringify(v) for k, v in value.items()}
            return value

        return IntentPayload.model_validate(
            {
                "intent": kind,
                "signerRule": "trader-only" if kind == "DelegateReq" else "trader-or-delegate",
                "domain": domain,
                "primaryType": kind,
                "types": types,
                "message": {k: _stringify(v) for k, v in int_message.items()},
                "digest": digest,
                "encodedIntent": "0x" + encoded.hex(),
            }
        )

    # ------------------------------------------------------------------ trading helpers

    def _deadline(self, deadline_ms: int | None) -> int:
        return deadline_ms if deadline_ms is not None else int(time.time() * 1000) + self.default_deadline_ms

    def _nonce(self, nonce: int | None) -> int:
        return nonce if nonce is not None else self.nonces.next()

    @staticmethod
    def _trade_struct(
        *,
        trader: str,
        pair_index: int,
        is_long: bool,
        collateral_usdc: float,
        leverage: float,
        open_price: float,
        tp: float,
        sl: float,
    ) -> dict[str, Any]:
        return {
            "trader": to_checksum_address(trader),
            "pairIndex": pair_index,
            "index": 0,
            "initialPosToken": 0,
            "positionSizeUSDC": _usdc(collateral_usdc),
            "openPrice": _p10(open_price),
            "buy": is_long,
            "leverage": _p10(leverage),
            "tp": _p10(tp),
            "sl": _p10(sl),
            "timestamp": 0,
        }

    def open_trade(
        self,
        *,
        trader: str,
        pair_index: int,
        is_long: bool,
        collateral_usdc: float,
        leverage: float,
        open_price: float,
        order_type: int = 0,  # 0 market, 1 stop_limit, 2 limit, 3 market_pnl
        tp: float = 0,
        sl: float = 0,
        slippage_percent: float = 1,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        message = {
            "_t": self._trade_struct(
                trader=trader,
                pair_index=pair_index,
                is_long=is_long,
                collateral_usdc=collateral_usdc,
                leverage=leverage,
                open_price=open_price,
                tp=tp,
                sl=sl,
            ),
            "_type": order_type,
            "_slippageP": _p10(slippage_percent),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("OpenTradeReq", message)

    def open_trade_coin(
        self,
        *,
        trader: str,
        pair_index: int,
        is_long: bool,
        collateral_usdc: float,
        coin_exposure: float,
        leverage: float,
        min_leverage: float,
        max_leverage: float,
        open_price: float,
        order_type: int = 0,  # 0 market, 3 market_pnl
        tp: float = 0,
        sl: float = 0,
        slippage_percent: float = 1,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """Open targeting a fixed base-asset exposure (fill leverage floats
        within [min_leverage, max_leverage]; ``leverage`` is the reference)."""
        message = {
            "_t": self._trade_struct(
                trader=trader,
                pair_index=pair_index,
                is_long=is_long,
                collateral_usdc=collateral_usdc,
                leverage=leverage,
                open_price=open_price,
                tp=tp,
                sl=sl,
            ),
            "_type": order_type,
            "_coinExposure": _p10(coin_exposure),
            "_minLeverage": _p10(min_leverage),
            "_maxLeverage": _p10(max_leverage),
            "_slippageP": _p10(slippage_percent),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("OpenTradeCoinExposureReq", message)

    def close_trade(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        open_timestamp: int,
        amount_usdc: float,
        wanted_price: float,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        message = {
            "_trader": to_checksum_address(trader),
            "_pairIndex": pair_index,
            "_index": index,
            "_openTimestamp": open_timestamp,
            "_amount": _usdc(amount_usdc),
            "_wantedPrice": _p10(wanted_price),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("CloseTradeReq", message)

    def close_trade_coin(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        open_timestamp: int,
        coin_exposure: float,
        wanted_price: float,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """Close a fixed base-asset exposure instead of a USDC amount."""
        message = {
            "_trader": to_checksum_address(trader),
            "_pairIndex": pair_index,
            "_index": index,
            "_openTimestamp": open_timestamp,
            "_coinExposure": _p10(coin_exposure),
            "_wantedPrice": _p10(wanted_price),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("CloseTradeCoinExposureReq", message)

    def _update_position_size_struct(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        open_price: float,
        additional_collateral_usdc: float,
        leverage: float,
    ) -> dict[str, Any]:
        return {
            "trader": to_checksum_address(trader),
            "pairIndex": pair_index,
            "index": index,
            "openPrice": _p10(open_price),
            "initialPosToken": _usdc(additional_collateral_usdc),
            "leverage": _p10(leverage),
        }

    def increase_position(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        additional_collateral_usdc: float,
        leverage: float,
        open_price: float,
        slippage_percent: float = 1,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """Increase position size (``open_price`` is the reference price for
        the added size; no feed locally, so the caller must supply it)."""
        message = {
            "_updateInfo": self._update_position_size_struct(
                trader=trader,
                pair_index=pair_index,
                index=index,
                open_price=open_price,
                additional_collateral_usdc=additional_collateral_usdc,
                leverage=leverage,
            ),
            "_slippageP": _p10(slippage_percent),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("IncreasePositionSizeReq", message)

    def increase_position_coin(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        additional_collateral_usdc: float,
        coin_exposure: float,
        leverage: float,
        min_leverage: float,
        max_leverage: float,
        open_price: float,
        slippage_percent: float = 1,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """Increase targeting a fixed base-asset exposure (fill leverage floats
        within [min_leverage, max_leverage])."""
        message = {
            "_updateInfo": self._update_position_size_struct(
                trader=trader,
                pair_index=pair_index,
                index=index,
                open_price=open_price,
                additional_collateral_usdc=additional_collateral_usdc,
                leverage=leverage,
            ),
            "_coinExposure": _p10(coin_exposure),
            "_minLeverage": _p10(min_leverage),
            "_maxLeverage": _p10(max_leverage),
            "_slippageP": _p10(slippage_percent),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("IncreasePositionSizeWithCoinExposureReq", message)

    def update_tp_sl(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        tp: float = 0,
        sl: float = 0,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        message = {
            "trader": to_checksum_address(trader),
            "_pairIndex": pair_index,
            "_index": index,
            "_newTp": _p10(tp),
            "_newSl": _p10(sl),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("UpdateTpSlReq", message)

    def partial_tp_sl(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        kind: str,  # "tp"/"take_profit" | "sl"/"stop_loss"
        is_long: bool,  # side of the POSITION being trimmed
        coin_exposure: float,
        open_timestamp: int,  # the position's Trade.timestamp
        trigger: str = "fixed",  # "fixed" | "percentage"
        price: float | None = None,  # required with trigger="fixed"
        percentage: float | None = None,  # signed, 1 = 1%; required with "percentage"
        sign_timestamp_ms: int | None = None,
        nonce: int | None = None,
    ) -> IntentPayload:
        """Partial TP/SL trigger order (TpSlReq).

        NO deadline by design — freshness comes from ``signTimestamp`` (ms,
        must not be in the future). The signed order is stored OFF-CHAIN via
        the core API /offchain-orders; building/signing alone does nothing.
        """
        if trigger not in _TRIGGER_TYPE_CODES:
            raise ValueError(f"trigger must be one of {sorted(_TRIGGER_TYPE_CODES)}")
        if kind not in _PARTIAL_KIND_CODES:
            raise ValueError(f"kind must be one of {sorted(_PARTIAL_KIND_CODES)}")
        if trigger == "fixed" and price is None:
            raise ValueError("price is required with trigger='fixed'")
        if trigger == "percentage" and percentage is None:
            raise ValueError("percentage is required with trigger='percentage'")
        message = {
            "trader": to_checksum_address(trader),
            "pairIndex": pair_index,
            "index": index,
            "triggerType": _TRIGGER_TYPE_CODES[trigger],
            "coinSize": _p10(coin_exposure),
            "buy": is_long,
            "price": _p10(price) if price is not None else 0,
            "percentage": _p10(percentage) if percentage is not None else 0,
            "timestamp": open_timestamp,
            "signTimestamp": (
                sign_timestamp_ms if sign_timestamp_ms is not None else int(time.time() * 1000)
            ),
            "orderType": _PARTIAL_KIND_CODES[kind],
            "nonce": self._nonce(nonce),
        }
        return self.build("TpSlReq", message)

    def twap_open(
        self,
        *,
        trader: str,
        pair_index: int,
        is_long: bool,
        collateral_usdc: float,
        run_time_seconds: int,
        leverage: float,
        max_leverage: float,
        coin_exposure: float | None = None,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """TWAP open (collateral spread over run_time_seconds slices);
        ``coin_exposure`` switches to fixed base-asset exposure targeting."""
        message = {
            "trader": to_checksum_address(trader),
            "pairIndex": pair_index,
            "collateral": _usdc(collateral_usdc),
            "buy": is_long,
            "isCoin": coin_exposure is not None,
            "coinSize": _p10(coin_exposure) if coin_exposure is not None else 0,
            "defaultLeverage": _p10(leverage),
            "maxLeverage": _p10(max_leverage),
            "runTime": run_time_seconds,
            "nonce": self._nonce(nonce),
            "deadline": self._deadline(deadline_ms),
            "__reserved1": 0,
        }
        return self.build("TwapOpenOrder", message)

    def twap_close(
        self,
        *,
        trader: str,
        pair_index: int,
        index: int,
        coin_exposure_to_close: float,
        run_time_seconds: int,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        message = {
            "trader": to_checksum_address(trader),
            "pairIndex": pair_index,
            "index": index,
            "coinSizeToClose": _p10(coin_exposure_to_close),
            "runTime": run_time_seconds,
            "nonce": self._nonce(nonce),
            "deadline": self._deadline(deadline_ms),
            "__reserved1": 0,
        }
        return self.build("TwapCloseOrder", message)

    def twap_cancel(
        self,
        *,
        trader: str,
        twap_id: int,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        """Cancel a TWAP by its on-chain ``twapId`` (no __reserved1 field)."""
        message = {
            "trader": to_checksum_address(trader),
            "twapId": twap_id,
            "nonce": self._nonce(nonce),
            "deadline": self._deadline(deadline_ms),
        }
        return self.build("TwapCancelReq", message)

    def cancel_offchain_order(self, *, document_id: str) -> IntentPayload:
        """Delete proof for a stored partial TP/SL: signs the order's Mongo
        ``documentId`` (from the create response / a position's
        ``offchainOrders``). Off-chain only — never submitted to a contract."""
        return self.build("CancelOffchainOrder", {"documentId": document_id})

    def delegate_req(
        self,
        *,
        trader: str,
        delegate: str,
        expiry_seconds: int,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        message = {
            "trader": to_checksum_address(trader),
            "delegate": to_checksum_address(delegate),
            "expiry": expiry_seconds,
            "deadline": self._deadline(deadline_ms),
            "tnc": TNC_STRING,
            "nonce": self._nonce(nonce),
        }
        return self.build("DelegateReq", message)

    # ------------------------------------------------------------------ referral
    # Separate EIP-712 domain (verifyingContract = Referral) and a
    # Referral-local nonce bitmap. msg.sender-scoped on-chain: trader key only.

    def _require_referral(self) -> None:
        if self.referral is None:
            raise ConfigError(
                "referral intents need the Referral contract address; "
                "pass referral= to LocalIntentBuilder (from_meta sets it automatically)"
            )

    def register_code(
        self,
        *,
        code: str,  # bytes32 hex or short string (right-padded)
        referrer: str,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        self._require_referral()
        message = {
            "_code": _code_bytes32(code),
            "_referrer": to_checksum_address(referrer),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("RegisterCodeReq", message)

    def set_referral_code(
        self,
        *,
        code: str,  # bytes32 hex or short string (right-padded)
        referee: str,
        nonce: int | None = None,
        deadline_ms: int | None = None,
    ) -> IntentPayload:
        self._require_referral()
        message = {
            "_code": _code_bytes32(code),
            "_referee": to_checksum_address(referee),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": self._nonce(nonce),
        }
        return self.build("SetTraderReferralCodeByUserReq", message)
