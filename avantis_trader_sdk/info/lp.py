"""LP (liquidity provider) actions on the ERC-4626 tranche (avUSDC).

USDC must be approved to the TRANCHE (not TradingStorage) first:
``client.account.approve_usdc(amount, spender=tranche_address)``.
No lock/epoch in v2 — withdrawals are immediate, gated by utilization.
"""

from __future__ import annotations

from typing import Any

from ..base_api import ExecutingApi
from ..errors import ConfigError
from ..types import ExecutionReceipt, Num


class LpApi(ExecutingApi):
    @property
    def caller(self) -> str:
        signer = self._engine.signer
        if signer is None:
            raise ConfigError("LP actions require a signing key.")
        return signer.address

    async def state(self, owner: str | None = None) -> dict[str, Any]:
        """Vault totals, share price, utilization, per-owner max withdraw/redeem."""
        return await self._txb.lp_state(owner or self.caller)

    async def deposit(
        self, amount: Num, *, receiver: str | None = None, wait: bool = True
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/lp/deposit",
            {"caller": self.caller, "amountUsdc": amount, "receiver": receiver},
            wait,
            delegatable=False,
        )

    async def mint(
        self, shares: Num, *, receiver: str | None = None, wait: bool = True
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/lp/mint",
            {"caller": self.caller, "shares": shares, "receiver": receiver},
            wait,
            delegatable=False,
        )

    async def withdraw(
        self,
        amount: Num,
        *,
        receiver: str | None = None,
        owner: str | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/lp/withdraw",
            {"caller": self.caller, "amountUsdc": amount, "receiver": receiver, "owner": owner},
            wait,
            delegatable=False,
        )

    async def redeem(
        self,
        shares: Num,
        *,
        receiver: str | None = None,
        owner: str | None = None,
        wait: bool = True,
    ) -> ExecutionReceipt:
        return await self._passthrough_or_direct(
            "/v2/lp/redeem",
            {"caller": self.caller, "shares": shares, "receiver": receiver, "owner": owner},
            wait,
            delegatable=False,
        )
