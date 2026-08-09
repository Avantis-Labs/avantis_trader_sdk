"""Upside pairs: symbol resolution, catalog helpers, automatic PNL order-type
routing (no user flag), market-only guards, and priceTriggers parsing.

Upside markets are separate ``_UPSIDE``-suffixed pairs whose
``storagePairParams.isPnlTypeAllowed`` = 1; the contract enforces strict
equality with the order type, so the pair fully determines routing.
"""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.account.models import Position
from avantis_trader_sdk.errors import ApiError, ValidationError
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from avantis_trader_sdk.markets.models import (
    TradingSnapshot,
    strip_upside_suffix,
)
from tests.conftest import (
    META,
    TEST_KEY,
    TRADER,
    TRADING_SNAPSHOT,
    VECTORS,
    mock_data_api,
)

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
CORE = "https://core.test"
DATA = "https://data.test"
BATCHED = "https://batched.test"
TWAP = "https://twap.test"

SNAPSHOT = TradingSnapshot.model_validate(TRADING_SNAPSHOT)


def _ok(data):
    return httpx.Response(200, json={"ok": True, "data": data})


def _client() -> AsyncAvantis:
    return AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        batched_market_url=BATCHED,
        twap_api_url=TWAP,
        data_api_url=DATA,
        relay_poll_interval_s=0.01,
    )


def _sse(*events: tuple[int | None, str, dict]) -> httpx.Response:
    frames = ["retry: 3000\n\n", ": open\n\n"]
    for seq, event_type, payload in events:
        frame = ""
        if seq is not None:
            frame += f"id: {seq}\n"
        frame += f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        frames.append(frame)
    return httpx.Response(
        200,
        content="".join(frames).encode(),
        headers={"content-type": "text/event-stream; charset=utf-8"},
    )


def _vector_payload(kind: str) -> dict:
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == kind)
    return {
        "intent": kind,
        "signerRule": "trader-or-delegate",
        "domain": VECTORS["domain"],
        "primaryType": kind,
        "types": INTENT_TYPES[kind],
        "message": vector["message"],
        "digest": vector["digest"],
        "encodedIntent": "0x" + "ab" * 64,
    }


def _calldata_payload() -> dict:
    return {
        "to": META["addresses"]["tradingRouter"],
        "from": TRADER,
        "data": "0xdeadbeef",
        "value": "0x0",
        "chainId": 31337,
        "description": "trade",
    }


# ---------------------------------------------------------------- resolution


def test_upside_symbol_resolution():
    """Underscores in upside names survive; legacy separator forms still work."""
    assert SNAPSHOT.pair_by_symbol("BTC_UPSIDE").index == 116
    assert SNAPSHOT.pair_by_symbol("btc_upside").index == 116
    assert SNAPSHOT.pair_by_symbol("BTC_UPSIDE/USD").index == 116
    assert SNAPSHOT.pair_by_symbol("btc_upside/usd").index == 116
    assert SNAPSHOT.pair_by_symbol("USD/JPY_UPSIDE").index == 119
    assert SNAPSHOT.pair_by_symbol("usd/jpy_upside").index == 119
    # legacy forms unchanged
    assert SNAPSHOT.pair_by_symbol("ETH").index == 1
    assert SNAPSHOT.pair_by_symbol("eth-usd").index == 1
    assert SNAPSHOT.pair_by_symbol("eth_usd").index == 1
    assert SNAPSHOT.pair_by_symbol("USD/JPY").index == 20
    with pytest.raises(ApiError, match="unknown pair"):
        SNAPSHOT.pair_by_symbol("DOGE_UPSIDE")


def test_pair_upside_properties():
    btc_upside = SNAPSHOT.pairs[116]
    assert btc_upside.is_upside
    assert btc_upside.base_symbol == "BTC/USD"
    assert btc_upside.storage_pair_params.is_pnl_type_allowed == 1
    jpy_upside = SNAPSHOT.pairs[119]
    assert jpy_upside.is_upside  # quote-side suffix (USD/JPY_UPSIDE)
    assert jpy_upside.base_symbol == "USD/JPY"
    assert not SNAPSHOT.pairs[2].is_upside
    assert SNAPSHOT.pairs[2].base_symbol == "BTC/USD"
    assert strip_upside_suffix("BTC_UPSIDE") == "BTC"
    assert strip_upside_suffix("BTC") == "BTC"


@pytest.mark.asyncio
@respx.mock
async def test_markets_upside_helpers():
    mock_data_api(DATA)
    async with _client() as client:
        upside = await client.markets.upside_pairs()
        assert set(upside) == {116, 119}

        twin = await client.markets.upside_pair_for("BTC/USD")
        assert twin.index == 116
        # by index, and idempotent on an upside pair
        assert (await client.markets.upside_pair_for(2)).index == 116
        assert (await client.markets.upside_pair_for(116)).index == 116
        assert (await client.markets.upside_pair_for("USD/JPY")).index == 119

        with pytest.raises(ApiError, match="no Upside market"):
            await client.markets.upside_pair_for("ETH/USD")


# ------------------------------------------------------------- auto-routing


@pytest.mark.asyncio
@respx.mock
async def test_market_open_on_upside_pair_routes_pnl():
    """Open on BTC_UPSIDE (by index): orderType market_pnl in the tx-builder
    request, MARKET_OPEN_PNL (6) on the batched-market body — no user flag."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    intent_route = respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=_ok(_vector_payload("OpenTradeReq"))
    )
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-u"}))
    )

    async with _client() as client:
        await client.trade.market_open(
            116, "long", collateral=100, leverage=100, wait=False
        )

    req = json.loads(intent_route.calls[0].request.content)
    assert req["pairIndex"] == "116"
    assert req["orderType"] == "market_pnl"
    body = json.loads(execute_route.calls[0].request.content)
    assert body["orderType"] == 6  # MARKET_OPEN_PNL


@pytest.mark.asyncio
@respx.mock
async def test_market_open_by_upside_symbol_resolves_pair_index():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    intent_route = respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=_ok(_vector_payload("OpenTradeReq"))
    )
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-s"}))
    )

    async with _client() as client:
        await client.trade.market_open(
            "BTC_UPSIDE", "long", collateral=100, leverage=100, wait=False
        )

    req = json.loads(intent_route.calls[0].request.content)
    assert req["pairIndex"] == "116"
    assert "pair" not in req
    assert req["orderType"] == "market_pnl"
    assert json.loads(execute_route.calls[0].request.content)["orderType"] == 6


@pytest.mark.asyncio
@respx.mock
async def test_market_open_coin_on_upside_pair():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    intent_route = respx.post(f"{TXB}/v2/intents/open-coin").mock(
        return_value=_ok(_vector_payload("OpenTradeCoinExposureReq"))
    )
    respx.post(f"{TXB}/v2/trade/open-coin").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-c"}))
    )

    async with _client() as client:
        await client.trade.market_open_coin(
            "BTC_UPSIDE", "long", collateral=100, coin_exposure=0.01,
            leverage=100, min_leverage=75, max_leverage=500, wait=False,
        )

    req = json.loads(intent_route.calls[0].request.content)
    assert req["pairIndex"] == "116"
    assert req["orderType"] == "market_pnl"
    body = json.loads(execute_route.calls[0].request.content)
    assert body["orderType"] == 13  # MARKET_OPEN_PNL_WITH_COIN_EXPOSURE


@pytest.mark.asyncio
@respx.mock
async def test_market_close_routes_from_pair():
    """Closes derive the aggregator type from the pair: PNL close (7) on the
    upside pair, plain close (1) on the fixed pair — is_pnl param is gone."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/close").mock(
        return_value=_ok(_vector_payload("CloseTradeReq"))
    )
    respx.post(f"{TXB}/v2/trade/close").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-x"}))
    )

    async with _client() as client:
        await client.trade.market_close(116, 0, collateral_to_close=100, wait=False)
        await client.trade.market_close("ETH/USD", 0, collateral_to_close=100, wait=False)

    first = json.loads(execute_route.calls[0].request.content)
    second = json.loads(execute_route.calls[1].request.content)
    assert first["orderType"] == 7  # MARKET_CLOSE_PNL
    assert second["orderType"] == 1  # MARKET_CLOSE


@pytest.mark.asyncio
@respx.mock
async def test_market_close_coin_on_upside_pair():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/close-coin").mock(
        return_value=_ok(_vector_payload("CloseTradeCoinExposureReq"))
    )
    respx.post(f"{TXB}/v2/trade/close-coin").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-cc"}))
    )

    async with _client() as client:
        await client.trade.market_close_coin(
            "USD/JPY_UPSIDE", 0, coin_exposure=1000, wait=False
        )

    body = json.loads(execute_route.calls[0].request.content)
    assert body["orderType"] == 16  # MARKET_CLOSE_PNL_WITH_COIN_EXPOSURE


# ------------------------------------------------------------ market-only


@pytest.mark.asyncio
@respx.mock
async def test_limit_and_twap_blocked_on_upside_pairs():
    """Upside pairs are market-only: clear local error, no builder HTTP call."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    open_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    twap_route = respx.post(f"{TXB}/v2/intents/twap-open").mock(
        return_value=_ok(_vector_payload("TwapOpenOrder"))
    )

    async with _client() as client:
        with pytest.raises(ValidationError, match="market-only") as exc:
            await client.trade.limit_open(
                "BTC_UPSIDE", "long", collateral=100, leverage=100, price=50000
            )
        assert exc.value.code == "UPSIDE_MARKET_ONLY"

        with pytest.raises(ValidationError, match="market-only"):
            await client.trade.twap_open(
                116, "long", collateral=1000, run_time_seconds=600,
                leverage=100, max_leverage=500,
            )
        with pytest.raises(ValidationError, match="market-only"):
            await client.trade.twap_close(
                "BTC_UPSIDE", 0, coin_exposure_to_close=0.1, run_time_seconds=600
            )

    assert not open_route.called
    assert not twap_route.called


# ------------------------------------------------- priceTriggers / global ids


def _position_payload(**overrides) -> dict:
    payload = {
        "trader": TRADER,
        "pairIndex": 116,
        "index": 0,
        "buy": True,
        "isPnl": True,
        "collateral": "100000000",
        "leverage": "1000000000000",
        "openPrice": "500000000000000",
        "tp": "600000000000000",
        "sl": "0",
        "openedAt": 1782374525,
        "priceTriggers": [
            {
                "entityId": f"global-tp-{TRADER}-116-0",
                "trader": TRADER,
                "pairIndex": 116,
                "index": 0,
                "timestamp": 1782374525,
                "triggerType": 0,
                "coinSize": "20000000000",
                "buy": True,
                "price": "600000000000000",
                "percentage": "0",
                "signTimestamp": 1782374525000,
                "orderType": 0,
                "nonce": "0",
                "finalTriggerPrice": "600000000000000",
                "isGlobal": True,
            },
            {
                # Old wire name: pre-/price-triggers deployments send
                # documentId. Parsing it proves the back-compat alias.
                "documentId": "665f1c2ab7a1b2c3d4e5f601",
                "trader": TRADER,
                "pairIndex": 116,
                "index": 0,
                "timestamp": 1782374525,
                "triggerType": 0,
                "coinSize": "5000000000",
                "buy": True,
                "price": "580000000000000",
                "percentage": "0",
                "signTimestamp": 1782374530000,
                "orderType": 4,
                "nonce": "1",
                "finalTriggerPrice": "580000000000000",
                "isGlobal": False,
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_position_parses_price_triggers_and_is_upside():
    pos = Position.model_validate(_position_payload())
    assert pos.is_upside  # wire alias isPnl
    assert len(pos.price_triggers) == 2

    (glob,) = pos.global_triggers
    assert glob.is_global and glob.kind == "tp"
    assert glob.entity_id.startswith("global-tp-")
    assert float(glob.price) == pytest.approx(60000.0)
    assert float(glob.coin_size) == pytest.approx(2.0)

    (partial,) = pos.partial_triggers
    assert not partial.is_global and partial.kind == "partial_tp"
    # Fed via the legacy `documentId` wire name — the validation alias maps it.
    assert partial.entity_id == "665f1c2ab7a1b2c3d4e5f601"
    assert partial.document_id == partial.entity_id  # deprecated property
    assert float(partial.final_trigger_price) == pytest.approx(58000.0)


@pytest.mark.asyncio
@respx.mock
async def test_positions_strip_upside_suffix_from_base_symbol():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.get(f"{CORE}/user-data").mock(
        return_value=httpx.Response(
            200, json={"positions": [_position_payload()], "limitOrders": []}
        )
    )

    async with _client() as client:
        data = await client.account.positions()

    (pos,) = data.positions
    assert pos.base_symbol == "BTC"  # BTC_UPSIDE -> BTC
    assert pos.is_upside


@pytest.mark.asyncio
@respx.mock
async def test_global_trigger_ids_rejected_by_partial_crud():
    """Synthetic global-tp-*/global-sl-* entityIds (priceTriggers isGlobal
    entries) must not reach the partial-order CRUD (/price-triggers)."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    delete_route = respx.delete(f"{CORE}/price-triggers").mock(
        return_value=httpx.Response(200, json={})
    )

    global_id = f"global-sl-{TRADER}-116-0"
    async with _client() as client:
        with pytest.raises(ValidationError, match="update_tp_sl") as exc:
            await client.trade.cancel_partial_tp_sl(global_id)
        assert exc.value.code == "GLOBAL_TRIGGER_ID"

        with pytest.raises(ValidationError, match="update_tp_sl"):
            await client.trade.cancel_partial_tp_sl({"entityId": global_id})

        with pytest.raises(ValidationError, match="update_tp_sl"):
            await client.trade.cancel_partial_tp_sl({"documentId": global_id})

        with pytest.raises(ValidationError, match="update_tp_sl"):
            await client.trade.update_partial_tp_sl(
                global_id, 116, 0, side="long", kind="sl",
                coin_exposure=0.1, price=40000,
            )

    assert not delete_route.called
