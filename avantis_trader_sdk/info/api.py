"""History / portfolio / referral / vault analytics (avantis-server API).

All endpoints degrade gracefully: a missing endpoint on a given deployment
raises ApiError with status 404 rather than crashing the client.
Human units throughout (per the v2 history swagger).
"""

from __future__ import annotations

from typing import Any

from ..config import AvantisConfig
from ..transport import HttpTransport


class InfoApi:
    def __init__(self, config: AvantisConfig, transport: HttpTransport) -> None:
        self._cfg = config
        self._t = transport

    def _v1(self, path: str) -> str:
        return f"{self._cfg.history_api_url}/v1{path}"

    def _v2(self, path: str) -> str:
        return f"{self._cfg.history_api_url}/v2{path}"

    # ------------------------------------------------------------------ history

    async def trade_history(self, trader: str, page: int = 0, limit: int = 20) -> Any:
        """Fill history with full fee breakdown (gross/net PnL, fees, funding)."""
        return await self._t.json(
            "GET", self._v2(f"/history/trade-history/{trader}/{page}/{limit}")
        )

    async def order_history(self, trader: str, page: int = 0, limit: int = 20) -> Any:
        return await self._t.json(
            "GET", self._v2(f"/history/order-history/{trader}/{page}/{limit}")
        )

    async def recent_trades(self, pair_index: int) -> Any:
        return await self._t.json("GET", self._v1(f"/history/recent-trades/{pair_index}"))

    # ------------------------------------------------------------------ portfolio

    async def portfolio_pnl(self, trader: str, *, grouped: bool = False) -> Any:
        suffix = "/grouped" if grouped else ""
        return await self._t.json(
            "GET", self._v2(f"/history/portfolio/profit-loss/{trader}{suffix}")
        )

    async def portfolio_pnl_history(self, trader: str, period: str, date_group: str = "day") -> Any:
        return await self._t.json(
            "GET",
            self._v1(f"/history/portfolio/profit-loss/history/{trader}/{period}/{date_group}"),
        )

    async def portfolio_volume(self, trader: str, *, grouped: bool = False) -> Any:
        suffix = "/grouped" if grouped else ""
        return await self._t.json(
            "GET", self._v1(f"/history/portfolio/total-size/{trader}{suffix}")
        )

    async def win_rate(self, trader: str, *, grouped: bool = False) -> Any:
        suffix = "/grouped" if grouped else ""
        return await self._t.json(
            "GET", self._v1(f"/history/portfolio/win-rate/{trader}{suffix}")
        )

    async def total_fees(self, trader: str) -> Any:
        return await self._t.json("GET", self._v1(f"/history/portfolio/total-fees/{trader}"))

    async def loss_protection_received(self, trader: str) -> Any:
        return await self._t.json(
            "GET", self._v1(f"/history/portfolio/loss-protection/{trader}")
        )

    async def portfolio_highlights(self, trader: str) -> Any:
        return await self._t.json("GET", self._v1(f"/history/portfolio/top/{trader}"))

    async def leaderboard(self, trader: str | None = None) -> Any:
        path = f"/history/portfolio/leader-board/{trader}" if trader else "/history/portfolio/leader-board"
        return await self._t.json("GET", self._v1(path))

    # ------------------------------------------------------------------ referral

    async def referral_stats(self, trader: str) -> Any:
        """{asReferrer: {totalFees, totalRebates, totalTraders}, asTrader: {...}}."""
        return await self._t.json("GET", self._v2(f"/history/referral/stats/{trader}"))

    async def referral_count(self, trader: str) -> Any:
        return await self._t.json("GET", self._v1(f"/history/referrals/count/{trader}"))

    async def referred_fees(self, trader: str) -> Any:
        return await self._t.json("GET", self._v1(f"/history/referrals/fees/referred/{trader}"))

    # ------------------------------------------------------------------ vault / LP

    async def vault_returns(self) -> Any:
        return await self._t.json("GET", self._v1("/vault/returns"))

    async def vault_share_rate_returns(self, *, chart: bool = False) -> Any:
        path = "/vault/share-rate-returns/chart" if chart else "/vault/share-rate-returns"
        return await self._t.json("GET", self._v2(path))

    async def user_vault_info(self, vault_type: str, trader: str) -> Any:
        return await self._t.json(
            "GET", self._v2(f"/history/vaults/user-vault-info/{vault_type}/{trader}")
        )

    # ------------------------------------------------------------------ status

    async def app_status(self) -> Any:
        return await self._t.json("GET", self._v1("/app/status"))
