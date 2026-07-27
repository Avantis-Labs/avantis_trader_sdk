"""End-to-end Phase 1 flow tests with mocked HTTP services.

Covers: meta bootstrap, intent fetch -> local sign (digest assert) ->
erc712 batch payload queued on the live relayer (POST /v2/relay/queue);
TX_RELAY type-4 passthrough for limit orders; positions read from the
core API.
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
FEED = "https://feed.test"
DATA = "https://data.test"

def _client() -> AsyncAvantis:
    return AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        feed_url=FEED,
        data_api_url=DATA,
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
    create_route = respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-123"})
    )
    status_route = respx.get(f"{RELAYER}/v2/relay/req-123").mock(
        side_effect=[
            httpx.Response(
                200, json={"success": False, "errorMessage": None, "receipt": None}
            ),
            httpx.Response(
                200,
                json={
                    "success": True,
                    "errorMessage": None,
                    "receipt": {"transactionHash": "0xtx"},
                },
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
    assert intent_route.called and status_route.called

    # intent request carried human units as strings
    intent_req = json.loads(intent_route.calls[0].request.content)
    assert intent_req["collateralUsdc"] == "100"
    assert intent_req["leverage"] == "10"
    assert intent_req["side"] == "long"
    assert intent_req["trader"] == TRADER

    # live relayer: erc712 payload — the server encodes the batch call itself
    body = json.loads(create_route.calls[0].request.content)
    assert body["wallet"] == TRADER
    assert body["action"] == "BATCH_MARKET_EXECUTION"
    erc712 = body["payload"]["erc712"]
    assert erc712["userIntent"] == "0x" + "ab" * 64
    assert erc712["userSignature"].startswith("0x") and len(erc712["userSignature"]) == 132
    assert erc712["pairIndex"] == 1
    assert erc712["orderType"] == 0  # MARKET_OPEN


@pytest.mark.asyncio
@respx.mock
async def test_market_open_coin_sends_required_leverage():
    """Coin-exposure opens must carry leverage (contract-required target fill
    leverage) alongside the [min, max] bounds — regression for the live 400."""
    vector = next(
        v for v in VECTORS["vectors"] if v["kind"] == "OpenTradeCoinExposureReq"
    )
    payload = {
        "intent": "OpenTradeCoinExposureReq",
        "signerRule": "trader-or-delegate",
        "domain": VECTORS["domain"],
        "primaryType": "OpenTradeCoinExposureReq",
        "types": INTENT_TYPES["OpenTradeCoinExposureReq"],
        "message": vector["message"],
        "digest": vector["digest"],
        "encodedIntent": "0x" + "ab" * 64,
    }
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    intent_route = respx.post(f"{TXB}/v2/intents/open-coin").mock(
        return_value=_ok(payload)
    )
    respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-coin"})
    )

    async with _client() as client:
        receipt = await client.trade.market_open_coin(
            "ETH/USD", "long", collateral=100, coin_exposure=0.5,
            leverage=10, min_leverage=1, max_leverage=75, wait=False,
        )

    assert receipt.route == "relayer-batch"
    req = json.loads(intent_route.calls[0].request.content)
    assert req["leverage"] == "10"
    assert req["minLeverage"] == "1"
    assert req["maxLeverage"] == "75"
    assert req["coinExposure"] == "0.5"


@pytest.mark.asyncio
@respx.mock
async def test_limit_open_uses_type4_passthrough():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    create_route = respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-9"})
    )
    respx.get(f"{RELAYER}/v2/relay/req-9").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "errorMessage": None,
                "receipt": {"transactionHash": "0xaa"},
            },
        )
    )

    async with _client() as client:
        receipt = await client.trade.limit_open(
            "ETH/USD", "short", collateral=50, leverage=5, price=3000
        )

    assert receipt.route == "relayer-passthrough"
    body = json.loads(create_route.calls[0].request.content)
    assert body["wallet"] == TRADER
    assert body["action"] == "TX_RELAY"
    tx = body["payload"]["type4"]
    assert tx["chainId"] == "31337"
    assert tx["data"].startswith("0xe9ae5c53")  # execute(bytes32,bytes) wrapper
    assert tx["gas"].isdigit()
    assert "value" not in tx and "transactionType" not in tx
    (auth,) = tx["authorizationList"]
    assert auth["address"] == "0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0"
    assert auth["chainId"] == "31337" and auth["nonce"] == "0"
    assert auth["yParity"] in (0, 1) and auth["v"] == str(auth["yParity"] + 27)


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
                    },
                    {
                        "trader": TRADER,
                        "pairIndex": 20,
                        "index": 0,
                        "buy": True,
                        "isPnl": False,
                        "collateral": "1000000000",  # 1_000 USDC
                        "leverage": "500000000000",  # 50x
                        "openPrice": "1554500000000",  # 155.45 JPY per USD
                        "openedAt": 1782374525,
                        "offchainOrders": [],
                    },
                ],
                "limitOrders": [],
            },
        )
    )
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.get(f"{DATA}/v2/trading").mock(
        return_value=httpx.Response(
            200,
            json={
                "pairInfos": {
                    "1": {"index": 1, "from": "BTC", "to": "USD"},
                    "20": {"index": 20, "from": "USD", "to": "JPY"},
                }
            },
        )
    )

    async with _client() as client:
        data = await client.account.positions()

    pos, jpy = data.positions
    assert pos.side == "long"
    assert float(pos.collateral) == 12500.0
    assert float(pos.leverage) == 10.0
    assert float(pos.open_price) == pytest.approx(61768.1861478347)
    assert float(pos.position_size) == 125000.0
    # quote-USD pair: coin size = notional / open price
    assert pos.base_symbol == "BTC"
    assert float(pos.size_in_asset) == pytest.approx(125000.0 / 61768.1861478347)
    # USD-base pair (USD/JPY): the USDC notional already IS the base-asset size
    assert jpy.base_symbol == "USD"
    assert float(jpy.position_size) == 50000.0
    assert float(jpy.size_in_asset) == 50000.0


@pytest.mark.asyncio
@respx.mock
async def test_relayer_error_message_raises():
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok(_open_intent_payload()))
    respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-err"})
    )
    respx.get(f"{RELAYER}/v2/relay/req-err").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": False,
                "errorMessage": "execution reverted: BELOW_MIN_POS",
                "receipt": None,
            },
        )
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="reverted"):
            await client.trade.market_open("ETH/USD", "long", collateral=1, leverage=2)


@pytest.mark.asyncio
@respx.mock
async def test_relayer_pending_forever_times_out():
    from avantis_trader_sdk.errors import RelayTimeoutError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok(_open_intent_payload()))
    respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(200, json={"requestId": "req-t"})
    )
    # live relayer has no explicit "Failed" state: stuck relays just stay
    # pending (success=false, no errorMessage) until the caller's poll timeout
    respx.get(f"{RELAYER}/v2/relay/req-t").mock(
        return_value=httpx.Response(
            200, json={"success": False, "errorMessage": None, "receipt": None}
        )
    )

    client = AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        feed_url=FEED,
        relay_poll_interval_s=0.01,
        relay_poll_timeout_s=0.05,
    )
    async with client:
        with pytest.raises(RelayTimeoutError, match="not settled"):
            await client.trade.market_open("ETH/USD", "long", collateral=1, leverage=2)


@pytest.mark.asyncio
@respx.mock
async def test_relayer_queue_rejection_raises():
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok(_open_intent_payload()))
    respx.post(f"{RELAYER}/v2/relay/queue").mock(
        return_value=httpx.Response(
            400, json={"message": "payload.erc712 is required"}
        )
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="rejected"):
            await client.trade.market_open(
                "ETH/USD", "long", collateral=100, leverage=10, wait=False
            )


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
