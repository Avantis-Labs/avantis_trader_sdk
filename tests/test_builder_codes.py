"""Builder-code v2 flow: per-order fee params + blitz routing.

The redesigned model: `builder_code` + a per-order `builder_fee_percent` are
sent to the tx-builder, which appends the signed suffix
``code || rate || 0x9481c2bc`` to the INNER trading calldata. Builder-fee
market orders relay via blitz (the type-4 always executes, so the fee always
charges) instead of batched-market, and the EIP-7702 authorization targets
the canonical fee-charging template from /v2/meta.
"""

import json

import httpx
import pytest
import respx

from tests.conftest import META, TEST_KEY, TRADER, mock_data_api
from veranta_sdk import AsyncVeranta
from veranta_sdk.errors import ApiError, ConfigError

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
BATCHED = "https://batched.test"
DATA = "https://data.test"

CODE = "MYAPP"


def _client(**overrides) -> AsyncVeranta:
    kwargs = dict(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        batched_market_url=BATCHED,
        data_api_url=DATA,
        relay_poll_interval_s=0.01,
    )
    kwargs.update(overrides)
    return AsyncVeranta(**kwargs)


def _ok(data):
    return httpx.Response(200, json={"ok": True, "data": data})


def _calldata_payload() -> dict:
    return {
        "to": META["addresses"]["tradingRouter"],
        "from": TRADER,
        "data": "0xdeadbeef",
        "value": "0x0",
        "chainId": 31337,
        "description": "Open long ETH/USD",
    }


RPC = "https://rpc.test"


def _mock_rpc() -> None:
    """Minimal JSON-RPC: nonce/gas reads for self-signed (trader-key) relays."""

    def responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": "0x0"})

    respx.post(RPC).mock(side_effect=responder)


def _mock_relayer() -> respx.Route:
    create = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "req-7"})
    )
    respx.get(f"{RELAYER}/relays/req-7").mock(
        return_value=httpx.Response(
            200,
            json={
                "requestId": "req-7",
                "status": "Finalised",
                "receipt": {"transactionHash": "0xbb", "status": "0x1"},
            },
        )
    )
    return create


@pytest.mark.asyncio
@respx.mock
async def test_builder_open_routes_via_blitz_with_params():
    """A configured builder code sends builderCode/builderFeeRate to the
    calldata builder and relays via blitz -- no intent, no batched-market."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    calldata_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    intent_route = respx.post(f"{TXB}/v2/intents/open").mock(return_value=_ok({}))
    batched_route = respx.post(f"{BATCHED}/market/execute-batched").mock(
        return_value=httpx.Response(200, json={})
    )
    create_route = _mock_relayer()

    async with _client(builder_code=CODE, builder_fee_percent=0.05) as client:
        receipt = await client.trade.market_open(
            "ETH/USD", "long", collateral=100, leverage=10
        )

    assert receipt.route == "relayer-passthrough"
    assert receipt.tx_hash == "0xbb"
    assert not intent_route.called
    assert not batched_route.called

    body = json.loads(calldata_route.calls[0].request.content)
    assert body["builderCode"] == CODE
    assert body["builderFeeRate"] == "0.05"

    # The EIP-7702 authorization targets the canonical template from /v2/meta.
    relay_body = json.loads(create_route.calls[0].request.content)
    (auth,) = relay_body["txParams"]["authorizationList"]
    assert auth["address"] == META["addresses"]["delegationTemplate"]


@pytest.mark.asyncio
@respx.mock
async def test_per_call_rate_overrides_config_default():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    calldata_route = respx.post(f"{TXB}/v2/trade/close").mock(
        return_value=_ok(_calldata_payload())
    )
    _mock_relayer()

    async with _client(builder_code=CODE, builder_fee_percent=0.05) as client:
        await client.trade.market_close(
            "ETH/USD", 0, collateral_to_close=100, builder_fee_percent=0.02
        )

    body = json.loads(calldata_route.calls[0].request.content)
    assert body["builderFeeRate"] == "0.02"


@pytest.mark.asyncio
@respx.mock
async def test_upside_open_forces_zero_rate_and_upside_close_keeps_it():
    """PnL-pair opens must carry an explicit zero rate; closes keep theirs
    (they are capped by the code's PnL-close cap on-chain)."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    open_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    close_route = respx.post(f"{TXB}/v2/trade/close").mock(
        return_value=_ok(_calldata_payload())
    )
    _mock_relayer()

    async with _client(builder_code=CODE, builder_fee_percent=0.05) as client:
        await client.trade.market_open("BTC_UPSIDE", "long", collateral=100, leverage=2)
        await client.trade.market_close("BTC_UPSIDE", 0, collateral_to_close=100)

    open_body = json.loads(open_route.calls[0].request.content)
    assert open_body["orderType"] == "market_pnl"
    assert open_body["builderFeeRate"] == "0"
    close_body = json.loads(close_route.calls[0].request.content)
    assert close_body["builderFeeRate"] == "0.05"


@pytest.mark.asyncio
@respx.mock
async def test_no_builder_config_keeps_batched_market_untouched():
    """Without builder params nothing changes: dual payload to batched-market,
    and no builder keys in the calldata request."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    calldata_route = respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(_calldata_payload())
    )
    respx.post(f"{TXB}/v2/intents/open").mock(
        return_value=httpx.Response(500, json={"ok": False})
    )

    async with _client() as client:
        with pytest.raises(ApiError):
            # The intent leg 500s -- proving it WAS requested (batched path).
            await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

    if calldata_route.called:
        body = json.loads(calldata_route.calls[0].request.content)
        assert "builderCode" not in body
        assert "builderFeeRate" not in body


@pytest.mark.asyncio
@respx.mock
async def test_builder_misconfiguration_raises():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)

    # Rate override without a configured code.
    async with _client() as client:
        with pytest.raises(ConfigError, match="no builder code"):
            await client.trade.market_open(
                "ETH/USD", "long", collateral=100, leverage=10, builder_fee_percent=0.05
            )

    # Code without any rate (config or per call).
    async with _client(builder_code=CODE) as client:
        with pytest.raises(ConfigError, match="without a fee rate"):
            await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

    # Direct mode cannot charge builder fees (no 7702 template runs).
    async with _client(
        builder_code=CODE,
        builder_fee_percent=0.05,
        execution="direct",
        rpc_url="https://unused-rpc.test",
    ) as client:
        with pytest.raises(ConfigError, match="relayer mode"):
            await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)


@pytest.mark.asyncio
@respx.mock
async def test_register_builder_code_new_params():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    register_route = respx.post(f"{TXB}/v2/misc/builder-code/register").mock(
        return_value=_ok(_calldata_payload())
    )
    _mock_relayer()
    _mock_rpc()

    async with _client(trader_address=None, rpc_url=RPC) as client:
        await client.account.register_builder_code(
            CODE,
            fee_collector=TRADER,
            max_open_fee_percent=0.1,
            max_close_fee_percent=0.05,
            max_pnl_close_fee_percent=0,
        )

    body = json.loads(register_route.calls[0].request.content)
    assert body["code"] == CODE
    assert body["feeCollector"] == TRADER
    assert body["maxOpenFeePercent"] == "0.1"
    assert body["maxCloseFeePercent"] == "0.05"
    assert body["maxPnlCloseFeePercent"] == "0"
    assert "isPercentFee" not in body


@pytest.mark.asyncio
@respx.mock
async def test_approve_builder_fees_targets_registry():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    approve_route = respx.post(f"{TXB}/v2/token/approve").mock(
        return_value=_ok(_calldata_payload())
    )
    _mock_relayer()
    _mock_rpc()

    async with _client(trader_address=None, rpc_url=RPC) as client:
        await client.account.approve_builder_fees()

    body = json.loads(approve_route.calls[0].request.content)
    assert body["spender"] == META["addresses"]["builderCode"]
