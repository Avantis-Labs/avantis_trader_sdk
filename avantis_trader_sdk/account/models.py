"""Models for the core API `/user-data` payloads (raw on-chain scales in,
human-unit properties out)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..types import from_1e10, from_usdc


class Position(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    trader: str
    pair_index: int = Field(alias="pairIndex")
    index: int
    buy: bool
    is_pnl: bool = Field(alias="isPnl", default=False)
    collateral_raw: str = Field(alias="collateral")
    leverage_raw: str = Field(alias="leverage")
    open_price_raw: str = Field(alias="openPrice")
    tp_raw: str = Field(alias="tp", default="0")
    sl_raw: str = Field(alias="sl", default="0")
    liquidation_price_raw: str = Field(alias="liquidationPrice", default="0")
    rollover_fee_raw: str = Field(alias="rolloverFee", default="0")
    unrealised_funding_fee_raw: str = Field(alias="unrealisedFundingFee", default="0")
    loss_protection_raw: str = Field(alias="lossProtection", default="0")
    opened_at: int = Field(alias="openedAt", default=0)
    offchain_orders: list[dict[str, Any]] = Field(alias="offchainOrders", default_factory=list)

    # -- human units ---------------------------------------------------------

    @property
    def side(self) -> str:
        return "long" if self.buy else "short"

    @property
    def collateral(self) -> Decimal:
        return from_usdc(self.collateral_raw)

    @property
    def leverage(self) -> Decimal:
        return from_1e10(self.leverage_raw)

    @property
    def open_price(self) -> Decimal:
        return from_1e10(self.open_price_raw)

    @property
    def tp(self) -> Decimal:
        return from_1e10(self.tp_raw)

    @property
    def sl(self) -> Decimal:
        return from_1e10(self.sl_raw)

    @property
    def liquidation_price(self) -> Decimal:
        return from_1e10(self.liquidation_price_raw)

    @property
    def rollover_fee(self) -> Decimal:
        return from_usdc(self.rollover_fee_raw)

    @property
    def unrealised_funding_fee(self) -> Decimal:
        return from_usdc(self.unrealised_funding_fee_raw)

    @property
    def position_size(self) -> Decimal:
        """Notional in USDC (collateral * leverage)."""
        return self.collateral * self.leverage

    @property
    def size_in_asset(self) -> Decimal:
        """Position size in the base asset (collateral * leverage / open price)."""
        if self.open_price == 0:
            return Decimal(0)
        return self.position_size / self.open_price


class LimitOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    trader: str
    pair_index: int = Field(alias="pairIndex")
    index: int
    buy: bool
    collateral_raw: str = Field(alias="collateral", default="0")
    position_size_raw: str = Field(alias="positionSize", default="0")
    price_raw: str = Field(alias="price", default="0")
    leverage_raw: str = Field(alias="leverage", default="0")
    tp_raw: str = Field(alias="tp", default="0")
    sl_raw: str = Field(alias="sl", default="0")
    slippage_raw: str = Field(alias="slippageP", default="0")
    block: int = 0

    @property
    def side(self) -> str:
        return "long" if self.buy else "short"

    @property
    def price(self) -> Decimal:
        return from_1e10(self.price_raw)

    @property
    def leverage(self) -> Decimal:
        return from_1e10(self.leverage_raw)

    @property
    def collateral(self) -> Decimal:
        raw = self.collateral_raw if self.collateral_raw != "0" else self.position_size_raw
        return from_usdc(raw)


class UserData(BaseModel):
    positions: list[Position] = Field(default_factory=list)
    limit_orders: list[LimitOrder] = Field(alias="limitOrders", default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def position(self, pair_index: int, index: int) -> Position | None:
        for p in self.positions:
            if p.pair_index == pair_index and p.index == index:
                return p
        return None
