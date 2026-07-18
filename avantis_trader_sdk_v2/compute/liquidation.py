"""Liquidation price estimate — mirrors avantis-ui-v2 useLiqPrice.ts and
PairInfos.getTradeLiquidationPricePure.

The authoritative value for open positions comes from the core API
(``Position.liquidation_price``); this estimate is for pre-trade display and
what-if math (margin edits, increases).
"""

from __future__ import annotations

LIQ_THRESHOLD_P = 85.0  # % of collateral lost at liquidation


def estimate_liquidation_price(
    *,
    open_price: float,
    collateral: float,
    leverage: float,
    is_long: bool,
    rollover_fee: float = 0.0,
    funding_fee: float = 0.0,
    liq_threshold_p: float = LIQ_THRESHOLD_P,
) -> float:
    """liqDistance = openPrice * (collateral*threshold - fees) / (collateral*leverage)."""
    position_size = collateral * leverage
    if position_size <= 0:
        return 0.0
    distance = (
        open_price
        * (collateral * liq_threshold_p / 100 - rollover_fee - funding_fee)
        / position_size
    )
    return open_price - distance if is_long else open_price + distance
