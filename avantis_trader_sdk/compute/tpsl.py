"""TP/SL price <-> percent conversions and bounds.

Mirrors avantis-ui-v2 components/trade/tradeInput/tpsl/TPSL.tsx and
packages/shared/src/utils.ts (pnlOrderMinSL).

Percentages are "percent of collateral" (100 = +100% profit at TP).
"""

from __future__ import annotations


def tp_percent_to_price(
    base_price: float,
    take_profit_percent: float,
    leverage: float,
    is_long: bool,
    *,
    is_pnl: bool = False,
    pnl_fee_p: float = 0.0,
) -> float:
    add = base_price * (take_profit_percent / 100) / leverage
    if is_pnl and pnl_fee_p < 100:
        add = add / (100 - pnl_fee_p) * 100  # fee-adjusted so NET profit hits the target
    return base_price + add if is_long else base_price - add


def tp_price_to_percent(
    base_price: float,
    tp_price: float,
    leverage: float,
    is_long: bool,
    *,
    is_pnl: bool = False,
    pnl_fee_p: float = 0.0,
) -> float:
    direction = 1 if is_long else -1
    profit_p = (tp_price - base_price) * direction / base_price * 100 * leverage
    if is_pnl:
        profit_p = profit_p * (100 - pnl_fee_p) / 100
    return profit_p


def sl_percent_to_price(
    base_price: float, stop_loss_percent: float, leverage: float, is_long: bool
) -> float:
    diff = base_price * (stop_loss_percent / 100) / leverage
    return base_price - diff if is_long else base_price + diff


def sl_price_to_percent(
    base_price: float, sl_price: float, leverage: float, is_long: bool
) -> float:
    direction = 1 if is_long else -1
    return (base_price - sl_price) * direction / base_price * 100 * leverage


def pnl_order_min_sl(leverage: float) -> float:
    """Minimum SL % for ZFP (guaranteed-execution) orders — piecewise in leverage."""
    if leverage <= 10:
        return (leverage / 10) * 1.5
    if leverage <= 25:
        return ((leverage - 10) / 15) * 2.25 + 1.5
    if leverage <= 50:
        return ((leverage - 25) / 25) * 3.75 + 3.75
    if leverage <= 100:
        return ((leverage - 50) / 50) * 3.75 + 7.5
    if leverage <= 250:
        return ((leverage - 100) / 150) * 18.75 + 11.25
    if leverage <= 500:
        return ((leverage - 250) / 250) * 15 + 30
    if leverage <= 1000:
        return ((leverage - 500) / 500) * 9 + 45
    return 54.0
