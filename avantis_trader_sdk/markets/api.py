"""Market data: pair catalog snapshot (data API) and prices (feed-v3)."""

from __future__ import annotations

import time
from typing import Any

from ..config import AvantisConfig
from ..errors import ApiError
from ..transport import HttpTransport
from .models import PairInfo, TradingSnapshot


class MarketsApi:
    def __init__(self, config: AvantisConfig, transport: HttpTransport) -> None:
        self._cfg = config
        self._t = transport
        self._snapshot: TradingSnapshot | None = None
        self._snapshot_at: float = 0.0
        self.snapshot_ttl_s: float = 5.0

    # ------------------------------------------------------------------ snapshot

    async def snapshot(self, *, force: bool = False) -> TradingSnapshot:
        """Full /v2/trading snapshot (cached for snapshot_ttl_s)."""
        now = time.monotonic()
        if force or self._snapshot is None or now - self._snapshot_at > self.snapshot_ttl_s:
            data = await self._t.json("GET", f"{self._cfg.data_api_url}/v2/trading")
            payload = data.get("data", data) if isinstance(data, dict) else data
            self._snapshot = TradingSnapshot.model_validate(payload)
            self._snapshot_at = now
        return self._snapshot

    async def pairs(self) -> dict[int, PairInfo]:
        return (await self.snapshot()).pairs

    async def pair(self, ref: str | int) -> PairInfo:
        snap = await self.snapshot()
        if isinstance(ref, int):
            info = snap.pairs.get(ref)
            if info is None:
                raise ApiError(f"unknown pair index {ref}")
            return info
        return snap.pair_by_symbol(ref)

    async def pair_index(self, symbol: str) -> int:
        return (await self.pair(symbol)).index

    # ------------------------------------------------------------------ prices

    async def price(self, pair: str | int) -> float:
        """Latest price for a pair via feed-v3 last-price."""
        info = await self.pair(pair)
        data = await self._t.json(
            "GET", f"{self._cfg.feed_url}/v1/price-feeds/last-price"
        )
        rows = data if isinstance(data, list) else data.get("data", [])
        for row in rows:
            if row.get("pairIndex") == info.index:
                return float(row["c"])
        raise ApiError(f"no last price for pair {info.symbol}")

    async def price_update_data(self, pair: str | int) -> dict[str, Any]:
        """Pyth price update bytes (core + pro) for on-chain calls."""
        info = await self.pair(pair)
        return await self._t.json(
            "GET", f"{self._cfg.feed_url}/v2/pairs/{info.index}/price-update-data"
        )

    async def dynamic_spread(
        self,
        pair: str | int,
        *,
        collateral: float,
        leverage: float,
        is_long: bool,
        is_pnl: bool = False,
        trader: str | None = None,
    ) -> dict[str, Any]:
        """Risk-API dynamic spread (percent) + component breakdown."""
        info = await self.pair(pair)
        precision = 18
        params: dict[str, Any] = {
            "collateralUsdc": collateral,
            "isLong": str(is_long).lower(),
            "leverage": leverage,
            "isPnl": str(is_pnl).lower(),
            "precision": precision,
        }
        if trader:
            params["trader"] = trader
        data = await self._t.json(
            "GET",
            f"{self._cfg.risk_api_url}/v2/dynamic-spread/{info.index}",
            params=params,
        )
        scale = 10**precision

        def _descale(value: Any) -> Any:
            try:
                return float(value) / scale
            except (TypeError, ValueError):
                return value

        out = dict(data)
        if "dynamicSpreadPct" in out:
            out["dynamicSpreadPct"] = _descale(out["dynamicSpreadPct"])
        out["metadata"] = {k: _descale(v) for k, v in (out.get("metadata") or {}).items()}
        return out

    async def candles(
        self, symbol: str, resolution: str, start: int, end: int
    ) -> Any:
        """OHLCV candles via the feed-v3 TradingView shim."""
        return await self._t.json(
            "GET",
            f"{self._cfg.feed_url}/v1/shims/tradingview/history",
            params={"symbol": symbol, "resolution": resolution, "from": start, "to": end},
        )
