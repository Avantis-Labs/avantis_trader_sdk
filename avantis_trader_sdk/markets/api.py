"""Market data: pair catalog snapshot (data API) and prices (feed-v3)."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from ..config import AvantisConfig
from ..errors import ApiError, ConfigError
from ..transport import HttpTransport
from ..types import PRECISION_10, Num, to_api_num
from .models import PairInfo, TradingSnapshot

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# risk-engine v2 spread OrderType enum (proto/risk-engine.proto). Note this is
# NOT the trade OrderType enum: stop-limit maps onto LIMIT here (the UI sends
# 1 for both limit flavors).
SPREAD_ORDER_TYPES = {
    "market": 0,
    "limit": 1,
    "stop_limit": 1,
    "tp": 2,
    "sl": 3,
    "liquidation": 4,
}


def _to_raw10(value: Num) -> str:
    """Human number -> 1e10 integer string via exact decimal arithmetic."""
    return str(int(Decimal(to_api_num(value)) * PRECISION_10))


def _from_raw10(value: Any) -> float | None:
    try:
        return float(Decimal(str(value)) / PRECISION_10)
    except (TypeError, ValueError, ArithmeticError):
        return None


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

    async def upside_pairs(self) -> dict[int, PairInfo]:
        """Upside markets only (separate pairs carrying the ``_UPSIDE`` suffix,
        e.g. BTC_UPSIDE/USD). These take the PnL order type automatically;
        see ``TradeApi``."""
        return {i: p for i, p in (await self.pairs()).items() if p.is_upside}

    async def upside_pair_for(self, base: str | int) -> PairInfo:
        """The Upside twin of a fixed-fee market ("BTC/USD" -> BTC_UPSIDE/USD).

        Matched like the Avantis UI: same symbols after stripping the
        ``_UPSIDE`` suffix (plus the shared price feed as a sanity check).
        Passing an upside pair returns it unchanged. Raises :class:`ApiError`
        when the market has no upside listing.
        """
        info = await self.pair(base)
        if info.is_upside:
            return info
        for candidate in (await self.pairs()).values():
            if not candidate.is_upside:
                continue
            if candidate.base_symbol.upper() != info.symbol.upper():
                continue
            same_feed = (
                not info.feed.feed_id
                or not candidate.feed.feed_id
                or candidate.feed.feed_id == info.feed.feed_id
            )
            if same_feed:
                return candidate
        raise ApiError(f"pair {info.symbol!r} has no Upside market")

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

    async def spread(
        self,
        pair: str | int,
        *,
        is_long: bool,
        coin_size: Num | None = None,
        collateral: Num | None = None,
        leverage: Num | None = None,
        is_open: bool = True,
        order_type: int | str = "market",
        wanted_price: Num | None = None,
        trader: str | None = None,
    ) -> dict[str, Any]:
        """Quoted spread from the risk-engine v2 spread API (``POST /spread``).

        This replaces :meth:`dynamic_spread` (the legacy risk-engine, which the
        v2 UI stopped calling in favor of this endpoint). The engine is sized
        by COIN exposure: pass ``coin_size`` (base-asset units) directly, or
        ``collateral`` + ``leverage`` and it is derived as
        ``collateral * leverage / price`` (``wanted_price`` if given, else the
        live feed price), the same conversion the UI applies.

        ``order_type`` is the risk-engine enum (``market``/``limit``/``tp``/
        ``sl``/``liquidation``; ``limit`` is also used for stop-limit) or its
        int value.
        ``wanted_price`` additionally feeds mechanism SM002; omit it to skip.

        Returns the raw response plus descaled float percentages:
        ``spreadPct`` (the quoted value: with-flow when available, else
        without-flow), ``spreadPctWithoutFlow`` and
        ``estimatedSpreadPctWithFlow``. Other fields: ``spreadMechanism``
        (SM001-SM006), ``byPass``, ``flowParams``.

        Error semantics (surfaced as :class:`ApiError`): 400 = malformed
        request, 403 = spread blocked (roll window / closed market / wallet),
        404 = mechanism matched but no spread computable; treat as
        "do not execute", never as zero spread.

        Deployment note: routed at ``{api_base_url}/risk/v2``; live on
        testnet. The mainnet route exists but the engine is not serving yet
        (5xx until the v2 cutover); use :meth:`dynamic_spread` there in the
        meantime.
        """
        info = await self.pair(pair)

        if coin_size is None:
            if collateral is None or leverage is None:
                raise ApiError("spread() needs coin_size or collateral+leverage")
            ref_price = (
                Decimal(to_api_num(wanted_price))
                if wanted_price is not None
                else Decimal(repr(await self.price(info.index)))
            )
            if ref_price <= 0:
                raise ApiError(f"no reference price for pair {info.symbol}")
            coin_size = (
                Decimal(to_api_num(collateral)) * Decimal(to_api_num(leverage)) / ref_price
            )

        if isinstance(order_type, str):
            try:
                order_type_int = SPREAD_ORDER_TYPES[order_type.lower()]
            except KeyError:
                raise ApiError(
                    f"unknown spread order_type {order_type!r}; "
                    f"use one of {sorted(SPREAD_ORDER_TYPES)}"
                ) from None
        else:
            order_type_int = int(order_type)

        body: dict[str, Any] = {
            "pairIndex": info.index,
            # trader is required (checksummed); the zero address matches the
            # UI's anonymous-quote fallback.
            "trader": trader or ZERO_ADDRESS,
            "coinSize10": _to_raw10(coin_size),
            "isLong": is_long,
            "isOpen": is_open,
            "orderType": order_type_int,
        }
        if wanted_price is not None:
            body["wantedPrice10"] = _to_raw10(wanted_price)

        data = await self._t.json(
            "POST", f"{self._cfg.risk_v2_api_url}/spread", json=body
        )

        out = dict(data)
        without_flow = _from_raw10(out.get("spreadPctWithoutFlow10"))
        with_flow = _from_raw10(out.get("estimatedSpreadPctWithFlow10"))
        out["spreadPctWithoutFlow"] = without_flow
        out["estimatedSpreadPctWithFlow"] = with_flow
        quoted = with_flow if with_flow is not None else without_flow
        out["spreadPct"] = quoted if quoted is not None else 0.0
        return out

    async def open_interests(self) -> dict[str, Any]:
        """Live per-pair long/short OI incl. pending amounts and the
        market-maker breakdown (core ``GET /v2/open-interests``)."""
        return await self._t.json(
            "GET", f"{self._cfg.core_api_url}/v2/open-interests"
        )

    async def orderbook_snapshots(self) -> Any:
        """Cumulative bid/ask coin liquidity per pair and orderbook source
        (risk-engine v2 ``GET /orderbook/snapshots``); ``ageMs`` flags
        staleness."""
        return await self._t.json(
            "GET", f"{self._cfg.risk_v2_api_url}/orderbook/snapshots"
        )

    async def dynamic_spread(
        self,
        pair: str | int,
        *,
        collateral: float,
        leverage: float,
        is_long: bool,
        is_upside: bool = False,
        trader: str | None = None,
    ) -> dict[str, Any]:
        """LEGACY risk-engine dynamic spread (``GET /v2/dynamic-spread``).

        Testnet-only since the 2026-08-12 mainnet cutover: the legacy engine
        is decommissioned on mainnet (risk-api.avantisfi.com is scaled to
        zero) and production quotes come from :meth:`spread` (risk-engine v2
        at ``{api_base_url}/risk/v2``). ``is_upside`` quotes the Upside (PnL)
        spread curve (wire param ``isPnl``).
        """
        if not self._cfg.risk_api_url:
            raise ConfigError(
                "The legacy risk engine is not deployed on this network "
                "(decommissioned on mainnet at the v2 cutover); use "
                "markets.spread(), or set AVANTIS_RISK_API_URL to override."
            )
        info = await self.pair(pair)
        precision = 18
        params: dict[str, Any] = {
            "collateralUsdc": collateral,
            "isLong": str(is_long).lower(),
            "leverage": leverage,
            "isPnl": str(is_upside).lower(),
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
