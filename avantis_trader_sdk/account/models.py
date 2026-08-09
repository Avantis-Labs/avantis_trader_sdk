"""Models for the core API `/user-data` payloads (raw on-chain scales in,
human-unit properties out)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..types import from_1e10, from_usdc

# OffchainOrderDto.orderType values (backend LimitOrder enum).
_TRIGGER_KINDS = {0: "tp", 1: "sl", 2: "liq", 3: "open", 4: "partial_tp", 5: "partial_sl"}


class PriceTrigger(BaseModel):
    """One entry of a position's ``priceTriggers``.

    Two flavors share the shape (backend OffchainOrderDto):

    - ``is_global`` True — the position's global on-chain TP/SL. Synthetic
      deterministic ``entityId`` (``global-tp-{trader}-{pairIndex}-{index}`` /
      ``global-sl-...``); change or remove via ``trade.update_tp_sl()``.
      ``coin_size`` is the full position size.
    - ``is_global`` False — an off-chain partial TP/SL signed intent; its
      ``entityId`` works with ``trade.update_partial_tp_sl()`` /
      ``cancel_partial_tp_sl()``. NOTE: a DB-backed entityId changes on every
      update (the response's ``newEntityId`` replaces it); global ids are
      stable.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    entity_id: str = Field(
        alias="entityId",
        # Pre-2026-08 core API deployments named this field `documentId`.
        validation_alias=AliasChoices("entityId", "documentId"),
    )
    trader: str = ""
    pair_index: int = Field(alias="pairIndex", default=0)
    index: int = 0
    is_global: bool = Field(alias="isGlobal", default=False)
    order_type: int = Field(alias="orderType", default=0)
    trigger_type: int = Field(alias="triggerType", default=0)
    buy: bool = False
    coin_size_raw: str = Field(alias="coinSize", default="0")
    price_raw: str = Field(alias="price", default="0")
    percentage_raw: str = Field(alias="percentage", default="0")
    final_trigger_price_raw: str = Field(alias="finalTriggerPrice", default="0")
    timestamp: int = 0
    sign_timestamp: int = Field(alias="signTimestamp", default=0)

    @property
    def document_id(self) -> str:
        """DEPRECATED alias for :attr:`entity_id` (pre-/price-triggers name)."""
        return self.entity_id

    @property
    def kind(self) -> str:
        """"tp" / "sl" / "partial_tp" / "partial_sl" (from the orderType enum)."""
        return _TRIGGER_KINDS.get(self.order_type, str(self.order_type))

    @property
    def coin_size(self) -> Decimal:
        return from_1e10(self.coin_size_raw)

    @property
    def price(self) -> Decimal:
        return from_1e10(self.price_raw)

    @property
    def final_trigger_price(self) -> Decimal:
        return from_1e10(self.final_trigger_price_raw)


class Position(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    trader: str
    pair_index: int = Field(alias="pairIndex")
    index: int
    buy: bool
    is_upside: bool = Field(alias="isPnl", default=False)
    """True when the position lives on an Upside pair (wire field ``isPnl``):
    it was opened with the PnL order type and pays a profit share instead of
    fixed fees."""
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
    price_triggers: list[PriceTrigger] = Field(alias="priceTriggers", default_factory=list)
    """All TP/SL triggers: global on-chain ones (``is_global`` True) plus
    off-chain partial orders. (The API's deprecated ``offchainOrders`` alias
    was removed 2026-08; this is the only trigger list now.)"""
    base_symbol: str | None = None
    """Base ("from") asset of the pair with any ``_UPSIDE`` suffix stripped,
    e.g. "BTC" for BTC_UPSIDE/USD or "USD" for USD/JPY. Not part of the core
    API payload — populated by ``AccountApi.positions()`` from the markets
    pair catalog."""

    # -- triggers -------------------------------------------------------------

    @property
    def global_triggers(self) -> list[PriceTrigger]:
        """The on-chain TP/SL (read-only entries; change via update_tp_sl)."""
        return [t for t in self.price_triggers if t.is_global]

    @property
    def partial_triggers(self) -> list[PriceTrigger]:
        """Off-chain partial TP/SL orders (entityId works with the CRUD)."""
        return [t for t in self.price_triggers if not t.is_global]

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
        """Notional in USDC (collateral * leverage), floored to 1e6 units as
        on-chain (``PositionMath.scaleByLeverage``)."""
        return from_usdc(int(self.collateral_raw) * int(self.leverage_raw) // 10**10)

    @property
    def size_in_asset(self) -> Decimal:
        """Position size in the base asset (collateral * leverage / open price).

        Mirrors the contracts' integer math (PositionMath.sol) so the value
        matches on-chain coin exposure exactly: the leveraged position is
        floored to 1e6 USDC units (``scaleByLeverage``), then converted with
        two sequential floor divisions to 1e10 coin units
        (``usdcToCoinAtPrice``). Plain Decimal division can disagree in the
        last digits because the chain rounds down at each step.

        For USD-base pairs (USD/JPY, USD/CHF, ...) the USDC notional already
        IS the base-asset size, so no division by the open price. This relies
        on ``base_symbol`` (set by ``AccountApi.positions()``); when it is
        missing the usual quote-USD convention is assumed.
        """
        # scaleByLeverage: collateral (1e6) * leverage (1e10) / 1e10 -> 1e6
        lev_pos_raw = int(self.collateral_raw) * int(self.leverage_raw) // 10**10
        if self.base_symbol is not None and self.base_symbol.upper() == "USD":
            return from_usdc(lev_pos_raw)
        price_raw = int(self.open_price_raw)
        if price_raw == 0:
            return Decimal(0)
        # usdcToCoinAtPrice: a * PRICE_PRECISION * COIN_OI_PRECISION / price
        # / USDC_PRECISION, floor at each division -> 1e10 coin units
        coin_raw = lev_pos_raw * 10**10 * 10**10 // price_raw // 10**6
        return from_1e10(coin_raw)


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
