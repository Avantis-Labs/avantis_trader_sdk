"""Stream parsing tests (SSE price stream via mocked HTTP)."""

import asyncio

import httpx
import pytest
import respx

from avantis_trader_sdk.streams import LazerPriceStream

SSE_BODY = (
    b"event: price_update\n"
    b'data: {"timestampUs": 1782374525000000, "priceFeeds": [{"priceFeedId": 2, '
    b'"price": "617681861478", "exponent": -8, "bestBidPrice": "617600000000", '
    b'"bestAskPrice": "617700000000", "confidence": "100", "publisherCount": 10}]}\n'
    b"\n"
    b": heartbeat\n"
    b"\n"
)


@pytest.mark.asyncio
@respx.mock
async def test_lazer_sse_parses_price_updates():
    respx.get("https://feed.test/v1/stream").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=SSE_BODY,
        )
    )

    stream = LazerPriceStream("https://feed.test", [2])
    updates = []

    async def collect(update):
        updates.append(update)
        stream.stop()

    task = asyncio.create_task(stream.run(collect))
    await asyncio.wait_for(task, timeout=5)

    (u,) = updates
    assert u.feed_id == 2
    assert u.price == pytest.approx(6176.81861478)
    assert u.best_bid == pytest.approx(6176.0)
    assert u.best_ask == pytest.approx(6177.0)
    assert u.timestamp_ms == 1782374525000
