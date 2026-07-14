"""Pair/OI/funding snapshot stream — Socket.IO ``RES:DATA`` broadcasts from
the data-service (same host as /v2/trading).

Requires the ``streams`` extra: ``pip install avantis-trader-sdk[streams]``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

Callback = Callable[[dict[str, Any]], Awaitable[None] | None]


class PairDataStream:
    def __init__(self, data_api_url: str) -> None:
        self._url = data_api_url.rstrip("/")
        self._sio: Any = None

    async def run(self, callback: Callback) -> None:
        """Connect and dispatch every RES:DATA payload (partial snapshots)."""
        try:
            import socketio
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "PairDataStream needs python-socketio: "
                "pip install 'avantis-trader-sdk[streams]'"
            ) from exc

        sio = socketio.AsyncClient(
            reconnection=True, reconnection_delay=1, reconnection_delay_max=30
        )
        self._sio = sio

        @sio.on("RES:DATA")
        async def _on_data(payload: dict[str, Any]) -> None:
            result = callback(payload)
            if asyncio.iscoroutine(result):
                await result

        await sio.connect(self._url, transports=["websocket", "polling"])
        await sio.wait()

    async def stop(self) -> None:
        if self._sio is not None:
            await self._sio.disconnect()
