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
from typing import Any

from eth_abi import encode as abi_encode
from eth_account.messages import _hash_eip191_message, encode_typed_data
from eth_utils import to_bytes, to_checksum_address

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

# Solidity struct component order for abi.encode(struct). Identical to the
# typed-data order except DelegateReq (declares expiry, tnc, deadline).
_ABI_ORDERS: dict[str, list[str]] = {
    "DelegateReq": ["trader", "delegate", "expiry", "tnc", "deadline", "nonce"],
}

_ABI_TYPE_MAP = {"Trade": "tuple", "UpdatePositionSize": "tuple"}


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
            "_t": {
                "trader": to_checksum_address(trader),
                "pairIndex": pair_index,
                "index": 0,
                "initialPosToken": 0,
                "positionSizeUSDC": int(collateral_usdc * USDC),
                "openPrice": int(open_price * P10),
                "buy": is_long,
                "leverage": int(leverage * P10),
                "tp": int(tp * P10),
                "sl": int(sl * P10),
                "timestamp": 0,
            },
            "_type": order_type,
            "_slippageP": int(slippage_percent * P10),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": nonce if nonce is not None else self.nonces.next(),
        }
        return self.build("OpenTradeReq", message)

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
            "_amount": int(amount_usdc * USDC),
            "_wantedPrice": int(wanted_price * P10),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": nonce if nonce is not None else self.nonces.next(),
        }
        return self.build("CloseTradeReq", message)

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
            "_newTp": int(tp * P10),
            "_newSl": int(sl * P10),
            "_deadline": self._deadline(deadline_ms),
            "_nonce": nonce if nonce is not None else self.nonces.next(),
        }
        return self.build("UpdateTpSlReq", message)

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
            "nonce": nonce if nonce is not None else self.nonces.next(),
        }
        return self.build("DelegateReq", message)
