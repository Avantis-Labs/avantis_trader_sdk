"""End-to-end Phase 1 flow tests with mocked HTTP services.

Covers: meta bootstrap, intent fetch -> local sign (digest assert) -> relayer
batch submit (erc712 + type4) -> status polling; TX_RELAY passthrough for
limit orders; positions read from the core API.
"""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from tests.conftest import META, TEST_KEY, TRADER, VECTORS

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
CORE = "https://core.test"


def _client() -> AsyncAvantis:
    return AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        relay_poll_interval_s=0.01,
    )


def _open_intent_payload() -> dict:
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == "OpenTradeReq")
    return {
        "intent": "OpenTradeReq",
        "signerRule": "trader-or-delegate",
        "domain": VECTORS["domain"],
        "primaryType": "OpenTradeReq",
        "types": INTENT_TYPES["OpenTradeReq"],
        "message": vector["message"],
        "digest": vector["digest"],
        "encodedIntent": "0x" + "ab" * 64,
        "meta": {"pair": "ETH/USD"},
    }


def _calldata_payload() -> dict:
    return {
        "to": META["addresses"]["tradingRouter"],
        "from": TRADER,
        "data": "0xdeadbeef",
        "value": "0x0",
        "chainId": 31337,
        "description": "Open long ETH/USD",
    }


def _ok(data):
    return httpx.Response(200, json={"ok": True, "data": data})


@pytest.mark.asyncio
@respx.mock
async def test_market_open_relayer_batch():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    intent_route = respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=_ok(_open_intent_payload())
    )
    calldata_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    queue_route = respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-123"})
    )
    status_route = respx.get(f"{RELAYER}/v2/relay/req-123").mock(
        side_effect=[
            httpx.Response(404),
            httpx.Response(200, json={"success": None}),
            httpx.Response(
                200, json={"success": True, "receipt": {"transactionHash": "0xtx"}}
            ),
        ]
    )

    async with _client() as client:
        receipt = await client.trade.market_open(
            "ETH/USD", "long", collateral=100, leverage=10
        )

    assert receipt.route == "relayer-batch"
    assert receipt.request_id == "req-123"
    assert receipt.tx_hash == "0xtx"
    assert intent_route.called and calldata_route.called and status_route.called

    # intent request carried human units as strings
    intent_req = json.loads(intent_route.calls[0].request.content)
    assert intent_req["collateralUsdc"] == "100"
    assert intent_req["leverage"] == "10"
    assert intent_req["side"] == "long"
    assert intent_req["trader"] == TRADER

    # calldata request asked for delegate wrapping (signer != trader)
    calldata_req = json.loads(calldata_route.calls[0].request.content)
    assert calldata_req["delegate"].lower() != TRADER.lower()

    # relayer batch payload shape
    body = json.loads(queue_route.calls[0].request.content)
    assert body["wallet"] == TRADER
    assert body["action"] == "BATCH_MARKET_EXECUTION"
    erc712 = body["payload"]["erc712"]
    assert erc712["orderType"] == 0  # MARKET_OPEN
    assert erc712["pairIndex"] == 1
    assert erc712["userIntent"] == "0x" + "ab" * 64
    assert erc712["userSignature"].startswith("0x") and len(erc712["userSignature"]) == 132
    type4 = body["payload"]["type4"]
    assert type4["to"]  # smart account = signer EOA
    assert type4["data"].startswith("0xe9ae5c53")  # execute(bytes32,bytes)
    assert type4["authorizationList"][0]["address"] == (
        "0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0"
    )


@pytest.mark.asyncio
@respx.mock
async def test_limit_open_uses_passthrough():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    queue_route = respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-9"})
    )
    respx.get(f"{RELAYER}/v2/relay/req-9").mock(
        return_value=httpx.Response(
            200, json={"success": True, "receipt": {"transactionHash": "0xaa"}}
        )
    )

    async with _client() as client:
        receipt = await client.trade.limit_open(
            "ETH/USD", "short", collateral=50, leverage=5, price=3000
        )

    assert receipt.route == "relayer-passthrough"
    body = json.loads(queue_route.calls[0].request.content)
    assert body["action"] == "TX_RELAY"
    assert "erc712" not in body["payload"]
    assert body["payload"]["type4"]["data"].startswith("0xe9ae5c53")


@pytest.mark.asyncio
@respx.mock
async def test_positions_read():
    respx.get(f"{CORE}/user-data").mock(
        return_value=httpx.Response(
            200,
            json={
                "positions": [
                    {
                        "trader": TRADER,
                        "pairIndex": 1,
                        "index": 2,
                        "buy": True,
                        "isPnl": False,
                        "collateral": "12500000000",
                        "leverage": "100000000000",
                        "openPrice": "617681861478347",
                        "tp": "926736003595864",
                        "sl": "568267312560080",
                        "liquidationPrice": "570901654660929",
                        "rolloverFee": "977487633",
                        "unrealisedFundingFee": "180622991",
                        "lossProtection": "0",
                        "openedAt": 1782374525,
                        "offchainOrders": [],
                    }
                ],
                "limitOrders": [],
            },
        )
    )
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))

    async with _client() as client:
        data = await client.account.positions()

    (pos,) = data.positions
    assert pos.side == "long"
    assert float(pos.collateral) == 12500.0
    assert float(pos.leverage) == 10.0
    assert float(pos.open_price) == pytest.approx(61768.1861478347)
    assert float(pos.position_size) == 125000.0


@pytest.mark.asyncio
@respx.mock
async def test_relayer_error_raises():
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok(_open_intent_payload()))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-err"})
    )
    respx.get(f"{RELAYER}/v2/relay/req-err").mock(
        return_value=httpx.Response(200, json={"errorMessage": "BelowMinPosition()"})
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="BelowMinPosition"):
            await client.trade.market_open("ETH/USD", "long", collateral=1, leverage=2)


@pytest.mark.asyncio
@respx.mock
async def test_api_validation_error_maps_to_typed_exception():
    from avantis_trader_sdk.errors import ValidationError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=httpx.Response(
            400,
            json={
                "ok": False,
                "error": {"code": "BAD_REQUEST", "message": "Below minimum position (100 USDC)"},
            },
        )
    )

    async with _client() as client:
        with pytest.raises(ValidationError, match="minimum position"):
            await client.trade.market_open("ETH/USD", "long", collateral=1, leverage=2)
