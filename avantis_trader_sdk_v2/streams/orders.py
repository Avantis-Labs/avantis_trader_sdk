"""Order-execution event stream (Pusher public channels).

The Avantis operator publishes per-trader execution events on channel
``events-{traderAddress}``: ``OrderPickedUpForExecution``,
``ExecutionConfirmedInFlashblock``, ``OrderFilled``, ``OrderCanceled``.

Implemented directly over the Pusher WebSocket protocol (protocol 7, public
channels — no auth), so no extra dependency is required beyond ``websockets``.
Requires the deployment's Pusher app key (``pusher_key`` config).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

Callback = Callable[["OrderEvent"], Awaitable[None] | None]

EVENTS = (
    "OrderPickedUpForExecution",
    "ExecutionConfirmedInFlashblock",
    "OrderFilled",
    "OrderCanceled",
)


@dataclass
class OrderEvent:
    event: str
    data: dict[str, Any]
    channel: str


class OrderEventStream:
    def __init__(
        self, pusher_key: str, trader: str, *, cluster: str = "us2"
    ) -> None:
        self._url = (
            f"wss://ws-{cluster}.pusher.com/app/{pusher_key}"
            "?protocol=7&client=avantis-python-sdk&version=2.0"
        )
        self._channel = f"events-{trader}"
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self, callback: Callback) -> None:
        import websockets

        attempt = 0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self._url, ping_interval=30) as ws:
                    attempt = 0
                    await ws.send(
                        json.dumps(
                            {
                                "event": "pusher:subscribe",
                                "data": {"channel": self._channel},
                            }
                        )
                    )
                    async for raw in ws:
                        if self._stop.is_set():
                            return
                        msg = json.loads(raw)
                        event = msg.get("event", "")
                        if event == "pusher:ping":
                            await ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                            continue
                        if event.startswith("pusher"):
                            continue
                        data = msg.get("data", {})
                        if isinstance(data, str):
                            try:
                                data = json.loads(data)
                            except json.JSONDecodeError:
                                data = {"raw": data}
                        result = callback(
                            OrderEvent(event=event, data=data, channel=msg.get("channel", ""))
                        )
                        if asyncio.iscoroutine(result):
                            await result
            except Exception:
                if self._stop.is_set():
                    return
                await asyncio.sleep(min(1.0 * 2**attempt, 30.0))
                attempt += 1
