"""Real-time price streams.

- LazerPriceStream: feed-v3 SSE (`/v1/stream?price_feed_ids=…`, event
  ``price_update``, 30s heartbeats); lowest latency, Avantis-hosted.
- HermesPriceStream: Pyth Hermes WebSocket (`wss://hermes.pyth.network/ws`).

Both reconnect with exponential backoff and deliver ``PriceUpdate`` objects to
an async callback or via ``async for``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx

from ..errors import ApiError

Callback = Callable[["PriceUpdate"], Awaitable[None] | None]


@dataclass
class PriceUpdate:
    feed_id: str | int
    price: float
    timestamp_ms: int | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    raw: dict | None = None


async def _dispatch(callback: Callback | None, update: PriceUpdate) -> None:
    if callback is None:
        return
    result = callback(update)
    if asyncio.iscoroutine(result):
        await result


class _ReconnectingStream:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(min(1.0 * 2**attempt, 30.0))


class LazerPriceStream(_ReconnectingStream):
    """feed-v3 SSE price stream (Pyth Lazer relays)."""

    def __init__(self, feed_url: str, lazer_feed_ids: list[int]) -> None:
        super().__init__()
        self._url = f"{feed_url.rstrip('/')}/v1/stream"
        self._feed_ids = lazer_feed_ids

    async def run(self, callback: Callback) -> None:
        attempt = 0
        params = {"price_feed_ids": ",".join(str(i) for i in self._feed_ids)}
        while not self._stop.is_set():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=90.0)) as client:
                    async with client.stream("GET", self._url, params=params) as resp:
                        if resp.status_code >= 400:
                            raise ApiError(
                                f"SSE stream HTTP {resp.status_code}", status=resp.status_code
                            )
                        attempt = 0
                        event_name = ""
                        async for line in resp.aiter_lines():
                            if self._stop.is_set():
                                return
                            if line.startswith("event:"):
                                event_name = line.split(":", 1)[1].strip()
                            elif line.startswith("data:") and event_name == "price_update":
                                data = json.loads(line.split(":", 1)[1])
                                ts = data.get("timestampUs")
                                # feed-v3 sends timestampUs as a decimal string
                                ts = int(ts) if ts is not None else None
                                for feed in data.get("priceFeeds", []):
                                    price = float(feed["price"]) * 10 ** feed.get("exponent", 0)
                                    await _dispatch(
                                        callback,
                                        PriceUpdate(
                                            feed_id=feed.get("priceFeedId"),
                                            price=price,
                                            timestamp_ms=int(ts / 1000) if ts else None,
                                            best_bid=(
                                                float(feed["bestBidPrice"])
                                                * 10 ** feed.get("exponent", 0)
                                                if feed.get("bestBidPrice")
                                                else None
                                            ),
                                            best_ask=(
                                                float(feed["bestAskPrice"])
                                                * 10 ** feed.get("exponent", 0)
                                                if feed.get("bestAskPrice")
                                                else None
                                            ),
                                            raw=feed,
                                        ),
                                    )
            except (httpx.HTTPError, ApiError, json.JSONDecodeError):
                if self._stop.is_set():
                    return
                await self._backoff(attempt)
                attempt += 1

    async def __aiter__(self) -> AsyncIterator[PriceUpdate]:
        queue: asyncio.Queue[PriceUpdate] = asyncio.Queue()
        task = asyncio.create_task(self.run(queue.put_nowait))
        try:
            while True:
                yield await queue.get()
        finally:
            self.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


class HermesPriceStream(_ReconnectingStream):
    """Pyth Hermes WebSocket subscription (feed ids are 0x-hex Pyth ids)."""

    def __init__(self, ws_url: str, feed_ids: list[str]) -> None:
        super().__init__()
        self._url = ws_url
        self._feed_ids = feed_ids

    async def run(self, callback: Callback) -> None:
        import websockets

        attempt = 0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self._url, ping_interval=20) as ws:
                    attempt = 0
                    await ws.send(
                        json.dumps({"type": "subscribe", "ids": self._feed_ids})
                    )
                    async for raw in ws:
                        if self._stop.is_set():
                            return
                        data = json.loads(raw)
                        if data.get("type") != "price_update":
                            continue
                        feed = data.get("price_feed", {})
                        p = feed.get("price", {})
                        price = float(p.get("price", 0)) * 10 ** p.get("expo", 0)
                        await _dispatch(
                            callback,
                            PriceUpdate(
                                feed_id=feed.get("id"),
                                price=price,
                                timestamp_ms=(p.get("publish_time") or 0) * 1000 or None,
                                raw=feed,
                            ),
                        )
            except Exception:
                if self._stop.is_set():
                    return
                await self._backoff(attempt)
                attempt += 1
