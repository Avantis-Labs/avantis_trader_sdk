"""Risk-engine v2 spread API (POST /spread) + new risk read endpoints.

Request/response schema mirrors avantis-backend-monorepo
src/risk-engine-v2-app/spread-module (SpreadRequestDto / SpreadResponseDto)
and the avantis-ui-v2 useDynamicSpread hook.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.errors import ApiError
from tests.conftest import TEST_KEY, TRADER

CORE = "https://core.test"
FEED = "https://feed.test"
DATA = "https://data.test"
RISK_V2 = "https://risk-v2.test"

SNAPSHOT = json.loads(
    (Path(__file__).parent / "vectors" / "trading_snapshot.json").read_text()
)

SPREAD_RESPONSE = {
    "spreadMechanism": 5,
    "byPass": False,
    "spreadPctWithoutFlow10": "500000000",  # 0.05%
    "estimatedSpreadPctWithFlow10": "750000000",  # 0.075%
    "flowParams": {
        "impactParam10": "1000000000000",
        "depth10": "5000000000000",
        "maxSpreadPct10": "100000000000",
    },
}


def _client() -> AsyncAvantis:
    return AsyncAvantis(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        core_api_url=CORE,
        feed_url=FEED,
        data_api_url=DATA,
        risk_v2_api_url=RISK_V2,
    )


def _mock_snapshot():
    respx.get(f"{DATA}/v2/trading").mock(
        return_value=httpx.Response(200, json=SNAPSHOT)
    )


@pytest.mark.asyncio
@respx.mock
async def test_spread_coin_size_request_body():
    _mock_snapshot()
    route = respx.post(f"{RISK_V2}/spread").mock(
        return_value=httpx.Response(200, json=SPREAD_RESPONSE)
    )

    async with _client() as client:
        out = await client.markets.spread(
            "ETH/USD",
            is_long=True,
            coin_size=2.5,
            order_type="market",
            trader=TRADER,
        )

    body = json.loads(route.calls.last.request.content)
    assert body["trader"] == TRADER
    assert body["coinSize10"] == str(int(2.5 * 1e10))
    assert body["isLong"] is True
    assert body["isOpen"] is True
    assert body["orderType"] == 0
    assert "wantedPrice10" not in body
    assert isinstance(body["pairIndex"], int)

    # descaled floats; quoted value prefers the with-flow estimate
    assert out["spreadPct"] == pytest.approx(0.075)
    assert out["spreadPctWithoutFlow"] == pytest.approx(0.05)
    assert out["estimatedSpreadPctWithFlow"] == pytest.approx(0.075)
    assert out["spreadMechanism"] == 5
    assert out["flowParams"]["depth10"] == "5000000000000"


@pytest.mark.asyncio
@respx.mock
async def test_spread_collateral_leverage_conversion_and_wanted_price():
    _mock_snapshot()
    route = respx.post(f"{RISK_V2}/spread").mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadMechanism": 1,
                "byPass": False,
                "spreadPctWithoutFlow10": "500000000",
            },
        )
    )

    async with _client() as client:
        out = await client.markets.spread(
            "ETH/USD",
            is_long=False,
            collateral=1000,
            leverage=10,
            wanted_price=2000,
            order_type="limit",
        )

    body = json.loads(route.calls.last.request.content)
    # coin size = 1000 * 10 / 2000 = 5 (UI coinFromCollateral parity)
    assert body["coinSize10"] == str(int(5 * 1e10))
    assert body["wantedPrice10"] == str(int(2000 * 1e10))
    assert body["orderType"] == 1
    # anonymous quote -> zero address (required by the API)
    assert body["trader"] == "0x" + "00" * 20

    # no with-flow estimate -> quoted falls back to without-flow
    assert out["spreadPct"] == pytest.approx(0.05)
    assert out["estimatedSpreadPctWithFlow"] is None


@pytest.mark.asyncio
@respx.mock
async def test_spread_no_spread_available_is_an_error():
    """404 = mechanism matched but no spread computable ("do not execute")."""
    _mock_snapshot()
    respx.post(f"{RISK_V2}/spread").mock(
        return_value=httpx.Response(404, json={"message": "orderbook stale"})
    )

    async with _client() as client:
        with pytest.raises(ApiError):
            await client.markets.spread("ETH/USD", is_long=True, coin_size=1)


@pytest.mark.asyncio
@respx.mock
async def test_spread_requires_sizing_args():
    _mock_snapshot()
    async with _client() as client:
        with pytest.raises(ApiError, match="coin_size or collateral"):
            await client.markets.spread("ETH/USD", is_long=True)


@pytest.mark.asyncio
@respx.mock
async def test_open_interests_and_orderbook_snapshots():
    oi = {"openInterests": [{"pairIndex": 0, "longOI": "1", "shortOI": "2"}], "mmData": []}
    books = [
        {
            "source": "BINANCE",
            "pairIndex": 0,
            "cumulativeCoinLiquidityBid": "100",
            "cumulativeCoinLiquidityAsk": "90",
            "ageMs": 250,
        }
    ]
    respx.get(f"{CORE}/v2/open-interests").mock(
        return_value=httpx.Response(200, json=oi)
    )
    respx.get(f"{RISK_V2}/orderbook/snapshots").mock(
        return_value=httpx.Response(200, json=books)
    )

    async with _client() as client:
        assert await client.markets.open_interests() == oi
        assert await client.markets.orderbook_snapshots() == books
