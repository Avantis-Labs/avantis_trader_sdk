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


TRADER = "0x1111111111111111111111111111111111111111"


def test_open_trade_coin_helper_scaling():
    payload = _builder().open_trade_coin(
        trader=TRADER,
        pair_index=1,
        is_long=True,
        collateral_usdc=100,
        coin_exposure=0.5,
        leverage=10,
        min_leverage=2,
        max_leverage=25,
        open_price=80000.0,
        slippage_percent=1,
        nonce=987654321123456789,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert payload.primary_type == "OpenTradeCoinExposureReq"
    assert msg["_t"]["positionSizeUSDC"] == "100000000"
    assert msg["_t"]["openPrice"] == "800000000000000"
    assert msg["_coinExposure"] == "5000000000"
    assert msg["_minLeverage"] == "20000000000"
    assert msg["_maxLeverage"] == "250000000000"
    assert msg["_slippageP"] == "10000000000"
    signed = sign_intent(payload, LocalSigner(TEST_KEY))
    assert signed.signature.startswith("0x")


def test_close_trade_coin_helper_scaling():
    payload = _builder().close_trade_coin(
        trader=TRADER,
        pair_index=2,
        index=1,
        open_timestamp=1750000000,
        coin_exposure=0.25,
        wanted_price=80000.0,
        nonce=1,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert payload.primary_type == "CloseTradeCoinExposureReq"
    assert msg["_coinExposure"] == "2500000000"
    assert msg["_wantedPrice"] == "800000000000000"
    assert msg["_openTimestamp"] == "1750000000"
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_increase_position_helper_scaling():
    payload = _builder().increase_position(
        trader=TRADER,
        pair_index=1,
        index=0,
        additional_collateral_usdc=50,
        leverage=5,
        open_price=3000.0,
        slippage_percent=0.5,
        nonce=1,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert payload.primary_type == "IncreasePositionSizeReq"
    assert msg["_updateInfo"]["initialPosToken"] == "50000000"
    assert msg["_updateInfo"]["openPrice"] == "30000000000000"
    assert msg["_updateInfo"]["leverage"] == "50000000000"
    assert msg["_slippageP"] == "5000000000"
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_increase_position_coin_helper_scaling():
    payload = _builder().increase_position_coin(
        trader=TRADER,
        pair_index=1,
        index=0,
        additional_collateral_usdc=50,
        coin_exposure=0.1,
        leverage=5,
        min_leverage=2,
        max_leverage=25,
        open_price=3000.0,
        nonce=1,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert payload.primary_type == "IncreasePositionSizeWithCoinExposureReq"
    assert msg["_updateInfo"]["initialPosToken"] == "50000000"
    assert msg["_coinExposure"] == "1000000000"
    assert msg["_minLeverage"] == "20000000000"
    assert msg["_maxLeverage"] == "250000000000"
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_partial_tp_sl_helper_fixed():
    payload = _builder().partial_tp_sl(
        trader=TRADER,
        pair_index=1,
        index=0,
        kind="tp",
        is_long=True,
        coin_exposure=0.1,
        open_timestamp=1750000000,
        trigger="fixed",
        price=90000.0,
        sign_timestamp_ms=1800000000123,
        nonce=1,
    )
    msg = payload.message
    assert payload.primary_type == "TpSlReq"
    assert "deadline" not in msg and "_deadline" not in msg  # no deadline by design
    assert msg["triggerType"] == "0"
    assert msg["orderType"] == "4"  # partial_tp
    assert msg["coinSize"] == "1000000000"
    assert msg["price"] == "900000000000000"
    assert msg["percentage"] == "0"
    assert msg["buy"] is True
    assert msg["signTimestamp"] == "1800000000123"
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_partial_tp_sl_helper_percentage_signed():
    payload = _builder().partial_tp_sl(
        trader=TRADER,
        pair_index=1,
        index=0,
        kind="stop_loss",
        is_long=False,
        coin_exposure=0.1,
        open_timestamp=1750000000,
        trigger="percentage",
        percentage=-50,
        sign_timestamp_ms=1800000000123,
        nonce=1,
    )
    msg = payload.message
    assert msg["orderType"] == "5"  # partial_sl
    assert msg["triggerType"] == "1"
    assert msg["percentage"] == "-500000000000"  # signed, 1e10 = 1%
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_partial_tp_sl_helper_validation():
    b = _builder()
    common = dict(
        trader=TRADER, pair_index=1, index=0, is_long=True,
        coin_exposure=0.1, open_timestamp=1750000000,
    )
    with pytest.raises(ValueError, match="price is required"):
        b.partial_tp_sl(kind="tp", trigger="fixed", **common)
    with pytest.raises(ValueError, match="percentage is required"):
        b.partial_tp_sl(kind="sl", trigger="percentage", **common)
    with pytest.raises(ValueError, match="kind"):
        b.partial_tp_sl(kind="nope", trigger="fixed", price=1.0, **common)
    with pytest.raises(ValueError, match="trigger"):
        b.partial_tp_sl(kind="tp", trigger="nope", price=1.0, **common)


def test_twap_open_helper_scaling():
    b = _builder()
    collateral_sized = b.twap_open(
        trader=TRADER,
        pair_index=1,
        is_long=True,
        collateral_usdc=100,
        run_time_seconds=3600,
        leverage=10,
        max_leverage=50,
        nonce=1,
        deadline_ms=1800000000123,
    )
    msg = collateral_sized.message
    assert collateral_sized.primary_type == "TwapOpenOrder"
    assert msg["collateral"] == "100000000"
    assert msg["isCoin"] is False
    assert msg["coinSize"] == "0"
    assert msg["defaultLeverage"] == "100000000000"
    assert msg["maxLeverage"] == "500000000000"
    assert msg["runTime"] == "3600"
    assert msg["__reserved1"] == "0"
    sign_intent(collateral_sized, LocalSigner(TEST_KEY))

    coin_sized = b.twap_open(
        trader=TRADER,
        pair_index=1,
        is_long=True,
        collateral_usdc=100,
        run_time_seconds=3600,
        leverage=10,
        max_leverage=50,
        coin_exposure=0.5,
        nonce=2,
        deadline_ms=1800000000123,
    )
    assert coin_sized.message["isCoin"] is True
    assert coin_sized.message["coinSize"] == "5000000000"


def test_twap_close_helper_scaling():
    payload = _builder().twap_close(
        trader=TRADER,
        pair_index=1,
        index=0,
        coin_exposure_to_close=0.75,
        run_time_seconds=1800,
        nonce=1,
        deadline_ms=1800000000123,
    )
    msg = payload.message
    assert payload.primary_type == "TwapCloseOrder"
    assert msg["coinSizeToClose"] == "7500000000"
    assert msg["runTime"] == "1800"
    assert msg["__reserved1"] == "0"
    sign_intent(payload, LocalSigner(TEST_KEY))


def test_twap_cancel_helper_matches_golden_digest():
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == "TwapCancelReq")
    payload = _builder().twap_cancel(
        trader="0x1111111111111111111111111111111111111111",
        twap_id=7,
        nonce=987654321123456789,
        deadline_ms=1800000000123,
    )
    assert payload.message["twapId"] == "7"
    assert "__reserved1" not in payload.message  # cancel has no reserved slot
    assert payload.digest == vector["digest"]


def test_cancel_offchain_order_helper_matches_golden_digest():
    vector = next(
        v for v in VECTORS["vectors"] if v["kind"] == "CancelOffchainOrder"
    )
    payload = _builder().cancel_offchain_order(
        entity_id="665f1c2ab7a1b2c3d4e5f601"
    )
    assert payload.message == {"entityId": "665f1c2ab7a1b2c3d4e5f601"}
    assert payload.digest == vector["digest"]


def test_referral_helpers():
    b = _builder()
    reg = b.register_code(
        code="MYCODE", referrer=TRADER, nonce=1, deadline_ms=1800000000123
    )
    assert reg.primary_type == "RegisterCodeReq"
    assert reg.message["_code"] == "0x" + b"MYCODE".ljust(32, b"\x00").hex()
    assert (
        reg.domain["verifyingContract"].lower()
        == VECTORS["domain"]["verifyingContract"].lower()
    )
    sign_intent(reg, LocalSigner(TEST_KEY))

    hex_code = "0x" + b"OTHER".ljust(32, b"\x00").hex()
    ref = b.set_referral_code(
        code=hex_code, referee=TRADER, nonce=2, deadline_ms=1800000000123
    )
    assert ref.primary_type == "SetTraderReferralCodeByUserReq"
    assert ref.message["_code"] == hex_code
    sign_intent(ref, LocalSigner(TEST_KEY))


def test_referral_helpers_require_referral_address():
    from avantis_trader_sdk.errors import ConfigError

    domain = VECTORS["domain"]
    b = LocalIntentBuilder(
        chain_id=domain["chainId"], trading_router=domain["verifyingContract"]
    )
    with pytest.raises(ConfigError):
        b.register_code(code="MYCODE", referrer=TRADER)
    with pytest.raises(ConfigError):
        b.set_referral_code(code="MYCODE", referee=TRADER)


def test_code_bytes32_validation():
    from avantis_trader_sdk.execution.local_intents import _code_bytes32

    with pytest.raises(ValueError, match="at most 32 bytes"):
        _code_bytes32("x" * 33)
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        _code_bytes32("0x1234")


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
