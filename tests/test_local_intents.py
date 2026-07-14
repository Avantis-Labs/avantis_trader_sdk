"""Local intent builder (MM fast path): digests must match the golden vectors
(computed by the on-chain SignatureHelpers library), and encodedIntent must
match viem's abi encoding byte-for-byte."""

import json
from pathlib import Path

import pytest

from avantis_trader_sdk.execution.local_intents import LocalIntentBuilder, NoncePool
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from avantis_trader_sdk.signing import LocalSigner, sign_intent
from tests.conftest import TEST_KEY, VECTORS

ENC_REF = json.loads(
    (Path(__file__).parent / "vectors" / "intent_encoding_reference.json").read_text()
)


def _builder() -> LocalIntentBuilder:
    domain = VECTORS["domain"]
    return LocalIntentBuilder(
        chain_id=domain["chainId"],
        trading_router=domain["verifyingContract"],
        referral=domain["verifyingContract"],  # vectors use one domain for all kinds
    )


def _int_message(kind: str, message: dict) -> dict:
    """Convert vector decimal strings to ints, driven by the schema."""
    types = INTENT_TYPES[kind]
    fields = {f["name"]: f["type"] for f in types[kind]}
    out = {}
    for name, value in message.items():
        t = fields[name]
        if t in types:
            inner_fields = {f["name"]: f["type"] for f in types[t]}
            out[name] = {
                k: (int(v) if inner_fields[k].startswith(("uint", "int")) else v)
                for k, v in value.items()
            }
        elif t.startswith(("uint", "int")):
            out[name] = int(value)
        else:
            out[name] = value
    return out


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["kind"])
def test_local_build_matches_golden_digest(vector):
    kind = vector["kind"]
    payload = _builder().build(kind, _int_message(kind, vector["message"]))
    assert payload.digest == vector["digest"]
    # and the full sign path (with digest assert) succeeds
    signed = sign_intent(payload, LocalSigner(TEST_KEY))
    assert len(bytes.fromhex(signed.signature[2:])) == 65


@pytest.mark.parametrize("kind", list(ENC_REF.keys()))
def test_encoded_intent_matches_viem(kind):
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == kind)
    payload = _builder().build(kind, _int_message(kind, vector["message"]))
    assert payload.encoded_intent == ENC_REF[kind].lower()


def test_open_trade_helper_scaling():
    b = _builder()
    payload = b.open_trade(
        trader="0x1111111111111111111111111111111111111111",
        pair_index=1,
        is_long=True,
        collateral_usdc=100,
        leverage=10,
        open_price=80000.0,
        tp=90000.0,
        slippage_percent=1,
        nonce=987654321123456789,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert msg["_t"]["positionSizeUSDC"] == "100000000"
    assert msg["_t"]["openPrice"] == "800000000000000"
    assert msg["_t"]["leverage"] == "100000000000"
    assert msg["_t"]["tp"] == "900000000000000"
    assert msg["_slippageP"] == "10000000000"
    assert msg["_deadline"] == "1800000000123"
    # signing the helper-built payload passes the digest gate
    signed = sign_intent(payload, LocalSigner(TEST_KEY))
    assert signed.signature.startswith("0x")


def test_nonce_pool_unique():
    pool = NoncePool()
    nonces = {pool.next() for _ in range(1000)}
    assert len(nonces) == 1000


def test_build_accepts_decimal_string_values():
    # callers may pass raw values as decimal strings (API convention);
    # digest and encoding must be identical to int inputs
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == "TwapOpenOrder")
    b = _builder()
    from_strings = b.build("TwapOpenOrder", vector["message"])  # decimal strings
    from_ints = b.build("TwapOpenOrder", _int_message("TwapOpenOrder", vector["message"]))
    assert from_strings.digest == from_ints.digest == vector["digest"]
    assert from_strings.encoded_intent == from_ints.encoded_intent
    # bools survived (isCoin=False in this vector)
    assert from_strings.message["isCoin"] is False
