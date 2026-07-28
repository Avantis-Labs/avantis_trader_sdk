"""End-to-end Phase 1 flow tests with mocked HTTP services.

Covers: meta bootstrap, intent fetch -> local sign (digest assert) ->
dual-payload (EIP-712 + EIP-7702) market execution via the batched-market
SSE endpoint; locally-encoded UPDATE_SL batch via the blitz relayer (type-2);
type-4 passthrough for limit orders; positions read from the core API.
"""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from tests.conftest import META, TEST_ADDRESS, TEST_KEY, TRADER, VECTORS

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
CORE = "https://core.test"
FEED = "https://feed.test"
DATA = "https://data.test"
BATCHED = "https://batched.test"

PRICE_UPDATE = {
    "core": {"price": 1900.0, "priceUpdateData": "0x" + "11" * 8},
    "pro": {"price": 1900.1, "priceUpdateData": "0x" + "22" * 8},
}


def _client() -> AsyncAvantis:
    return AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        batched_market_url=BATCHED,
        feed_url=FEED,
        data_api_url=DATA,
        relay_poll_interval_s=0.01,
    )


def _sse(*events: tuple[int | None, str, dict]) -> httpx.Response:
    """Build a batched-market SSE response from (seq, type, payload) tuples."""
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


def _tpsl_intent_payload() -> dict:
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == "UpdateTpSlReq")
    return {
        "intent": "UpdateTpSlReq",
        "signerRule": "trader-or-delegate",
        "domain": VECTORS["domain"],
        "primaryType": "UpdateTpSlReq",
        "types": INTENT_TYPES["UpdateTpSlReq"],
        "message": vector["message"],
        "digest": vector["digest"],
        "encodedIntent": "0x" + "ab" * 64,
    }


def _ok(data):
    return httpx.Response(200, json={"ok": True, "data": data})


@pytest.mark.asyncio
@respx.mock
async def test_market_open_batched_market_dual_payload():
    """Market opens submit BOTH the signed EIP-712 intent and a pre-signed
    EIP-7702 type-4 tx to the batched-market SSE endpoint."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    intent_route = respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=_ok(_open_intent_payload())
    )
    calldata_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse(
            (0, "MarketOrderAccepted", {"trackingId": "trk-1"}),
            (1, "MarketOrderInitiated", {"orderId": 42, "transactionHash": "0xinit"}),
            (2, "MarketOrderExecuted", {"orderId": 42, "transactionHash": "0xtx"}),
        )
    )

    async with _client() as client:
        receipt = await client.trade.market_open(
            "ETH/USD", "long", collateral=100, leverage=10
        )

    assert receipt.route == "batched-market"
    assert receipt.tracking_id == "trk-1"
    assert receipt.tx_hash == "0xtx"
    assert receipt.order_id == 42
    assert intent_route.called and calldata_route.called

    # intent request carried human units as strings
    intent_req = json.loads(intent_route.calls[0].request.content)
    assert intent_req["collateralUsdc"] == "100"
    assert intent_req["leverage"] == "10"
    assert intent_req["side"] == "long"
    assert intent_req["trader"] == TRADER

    # execute-batched body: orderType + both payloads, DTO string conventions
    body = json.loads(execute_route.calls[0].request.content)
    assert body["orderType"] == 0  # MARKET_OPEN
    assert body["erc712"]["userIntent"] == "0x" + "ab" * 64
    sig = body["erc712"]["userSignature"]
    assert sig.startswith("0x") and len(sig) == 132
    tx = body["eip7702"]
    assert tx["chainId"] == "31337" and isinstance(tx["gas"], str)
    # type-4 targets the SIGNER's delegated EOA (delegate mode here)
    assert tx["to"].lower() == TEST_ADDRESS.lower()
    assert tx["data"].startswith("0xe9ae5c53")  # execute(bytes32,bytes) wrapper
    (auth,) = tx["authorizationList"]
    assert auth["address"] == "0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0"
    assert isinstance(auth["chainId"], str) and isinstance(auth["nonce"], str)
    assert auth["yParity"] in (0, 1) and auth["v"] == str(auth["yParity"] + 27)


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
    respx.post(f"{TXB}/v2/trade/open-coin").mock(return_value=_ok(_calldata_payload()))
    execute_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse((0, "MarketOrderAccepted", {"trackingId": "trk-coin"}))
    )

    async with _client() as client:
        receipt = await client.trade.market_open_coin(
            "ETH/USD", "long", collateral=100, coin_exposure=0.5,
            leverage=10, min_leverage=1, max_leverage=75, wait=False,
        )

    assert receipt.route == "batched-market"
    assert receipt.tracking_id == "trk-coin"
    assert receipt.tx_hash is None  # wait=False: accepted, not settled
    body = json.loads(execute_route.calls[0].request.content)
    assert body["orderType"] == 12  # MARKET_OPEN_WITH_COIN_EXPOSURE
    req = json.loads(intent_route.calls[0].request.content)
    assert req["leverage"] == "10"
    assert req["minLeverage"] == "1"
    assert req["maxLeverage"] == "75"
    assert req["coinExposure"] == "0.5"


@pytest.mark.asyncio
@respx.mock
async def test_update_tp_sl_stays_on_blitz_type2_batch():
    """UPDATE_SL is excluded from the batched-market allow-list: the SDK still
    encodes executePositionUpdateBatched locally and relays via blitz."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-update").mock(
        return_value=_ok(_tpsl_intent_payload())
    )
    respx.get(f"{FEED}/v2/pairs/1/price-update-data").mock(
        return_value=httpx.Response(200, json=PRICE_UPDATE)
    )
    create_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-123"})
    )
    status_route = respx.get(f"{RELAYER}/relays/req-123").mock(
        side_effect=[
            httpx.Response(200, json={"requestId": "req-123", "status": "Inflight", "receipt": None}),
            httpx.Response(
                200,
                json={
                    "requestId": "req-123",
                    "status": "Finalised",
                    "receipt": {"transactionHash": "0xtx", "status": "0x1"},
                },
            ),
        ]
    )

    async with _client() as client:
        receipt = await client.trade.update_tp_sl(
            "ETH/USD", 0, take_profit=90000, stop_loss=70000
        )

    assert receipt.route == "relayer-batch"
    assert receipt.request_id == "req-123"
    assert receipt.tx_hash == "0xtx"
    assert status_route.called

    # blitz relay: SDK-encoded executePositionUpdateBatched, type-2, to the router
    body = json.loads(create_route.calls[0].request.content)
    assert body["wallet"] == TRADER
    tx = body["txParams"]
    assert tx["to"] == META["addresses"]["tradingRouter"]
    assert tx["transactionType"] == 2
    assert tx["chainId"] == 31337
    assert tx["gasLimit"] == "2500000"
    assert tx["value"] == "1"  # Lazer ('pro') price update -> 1 wei fee
    from eth_utils import keccak

    selector = keccak(
        text="executePositionUpdateBatched(uint8,bytes,bytes,bytes[],uint8,"
        "(int256,uint256,int256,bool,int256,bool,int256))"
    )[:4]
    assert tx["data"].startswith("0x" + selector.hex())
    assert ("ab" * 64) in tx["data"]  # encodedIntent embedded
    assert ("22" * 8) in tx["data"]  # pro price update embedded


@pytest.mark.asyncio
@respx.mock
async def test_limit_open_uses_type4_passthrough():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    create_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-9"})
    )
    respx.get(f"{RELAYER}/relays/req-9").mock(
        return_value=httpx.Response(
            200,
            json={
                "requestId": "req-9",
                "status": "Finalised",
                "receipt": {"transactionHash": "0xaa", "status": "0x1"},
            },
        )
    )

    async with _client() as client:
        receipt = await client.trade.limit_open(
            "ETH/USD", "short", collateral=50, leverage=5, price=3000
        )

    assert receipt.route == "relayer-passthrough"
    body = json.loads(create_route.calls[0].request.content)
    tx = body["txParams"]
    assert tx["transactionType"] == 4
    assert tx["data"].startswith("0xe9ae5c53")  # execute(bytes32,bytes) wrapper
    (auth,) = tx["authorizationList"]
    assert auth["address"] == "0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0"
    assert isinstance(auth["chainId"], int) and isinstance(auth["nonce"], int)
    assert auth["yParity"] in (0, 1) and auth["v"] == auth["yParity"] + 27


@pytest.mark.asyncio
@respx.mock
async def test_delegate_key_signs_authorization_with_nonce_zero_no_rpc():
    """Delegate/API keys (register in the UI, export the key) are fresh EOAs:
    the EIP-7702 authorization is correctly signed over nonce 0 and the SDK
    needs no RPC at all — the normal setup."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    create_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-n"})
    )

    async with _client() as client:  # TEST_KEY signs for TRADER: delegate mode
        await client.trade.limit_open(
            "ETH/USD", "short", collateral=50, leverage=5, price=3000, wait=False
        )

    body = json.loads(create_route.calls[0].request.content)
    (auth,) = body["txParams"]["authorizationList"]
    assert auth["nonce"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_trader_eoa_without_rpc_fails_fast_in_relayer_mode():
    """Signing with the trader EOA directly needs an RPC for the authorization
    nonce (its nonce is almost never 0; a stale nonce is silently skipped
    on-chain and the tx reverts — found live 2026-07-28). Without one, the SDK
    must raise a clear ConfigError instead of an opaque on-chain revert."""
    from avantis_trader_sdk.errors import ConfigError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))

    async with AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,  # signer IS the trader: no trader_address
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        feed_url=FEED,
        data_api_url=DATA,
    ) as client:
        with pytest.raises(ConfigError, match="AVANTIS_RPC_URL"):
            await client.trade.limit_open(
                "ETH/USD", "short", collateral=50, leverage=5, price=3000, wait=False
            )


@pytest.mark.asyncio
@respx.mock
async def test_trader_eoa_with_rpc_reads_real_authorization_nonce():
    """With rpc_url set (any Base endpoint), the authorization is signed over
    the EOA's real protocol nonce from eth_getTransactionCount."""
    RPC = "https://rpc.test"

    def rpc_responder(request):
        body = json.loads(request.content)
        result = {"eth_getTransactionCount": hex(1287), "eth_estimateGas": hex(300_000)}.get(
            body["method"], "0x0"
        )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    respx.post(RPC).mock(side_effect=rpc_responder)
    create_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-n"})
    )

    async with AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        rpc_url=RPC,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        feed_url=FEED,
        data_api_url=DATA,
    ) as client:
        await client.trade.limit_open(
            "ETH/USD", "short", collateral=50, leverage=5, price=3000, wait=False
        )

    body = json.loads(create_route.calls[0].request.content)
    (auth,) = body["txParams"]["authorizationList"]
    assert auth["nonce"] == 1287


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
async def test_batched_market_canceled_raises():
    """MarketOrderCanceled terminal (tx succeeded, fill declined) is a RelayError."""
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok(_open_intent_payload()))
    respx.post(f"{TXB}/v2/trade/open").mock(return_value=_ok(_calldata_payload()))
    respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=_sse(
            (0, "MarketOrderAccepted", {"trackingId": "trk-x"}),
            (1, "MarketOrderInitiated", {"orderId": 7, "transactionHash": "0xinit"}),
            (2, "MarketOrderCanceled", {"orderId": 7, "reason": "SLIPPAGE_EXCEEDED"}),
        )
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="canceled"):
            await client.trade.market_open("ETH/USD", "long", collateral=1, leverage=2)


@pytest.mark.asyncio
@respx.mock
async def test_relayer_reverted_receipt_raises():
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-update").mock(
        return_value=_ok(_tpsl_intent_payload())
    )
    respx.get(f"{FEED}/v2/pairs/1/price-update-data").mock(
        return_value=httpx.Response(200, json=PRICE_UPDATE)
    )
    respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-err"})
    )
    respx.get(f"{RELAYER}/relays/req-err").mock(
        return_value=httpx.Response(
            200,
            json={
                "requestId": "req-err",
                "status": "Finalised",
                "receipt": {"transactionHash": "0xbad", "status": "0x0"},
            },
        )
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="reverted"):
            await client.trade.update_tp_sl("ETH/USD", 0, take_profit=90000)


@pytest.mark.asyncio
@respx.mock
async def test_relayer_failed_status_raises():
    from avantis_trader_sdk.errors import RelayError

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-update").mock(
        return_value=_ok(_tpsl_intent_payload())
    )
    respx.get(f"{FEED}/v2/pairs/1/price-update-data").mock(
        return_value=httpx.Response(200, json=PRICE_UPDATE)
    )
    respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-t"})
    )
    respx.get(f"{RELAYER}/relays/req-t").mock(
        return_value=httpx.Response(
            200, json={"requestId": "req-t", "status": "Failed", "receipt": None}
        )
    )

    async with _client() as client:
        with pytest.raises(RelayError, match="failed"):
            await client.trade.update_tp_sl("ETH/USD", 0, take_profit=90000)


@pytest.mark.asyncio
@respx.mock
async def test_relayer_busy_503_retries_then_succeeds():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-update").mock(
        return_value=_ok(_tpsl_intent_payload())
    )
    respx.get(f"{FEED}/v2/pairs/1/price-update-data").mock(
        return_value=httpx.Response(200, json=PRICE_UPDATE)
    )
    create_route = respx.post(f"{RELAYER}/relays").mock(
        side_effect=[
            httpx.Response(503, json={"message": "all wallets busy"}),
            httpx.Response(200, json={"requestId": "req-2"}),
        ]
    )

    async with _client() as client:
        receipt = await client.trade.update_tp_sl(
            "ETH/USD", 0, take_profit=90000, wait=False
        )

    assert receipt.request_id == "req-2"
    assert create_route.call_count == 2


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
