"""Pure computation layer — UI-parity math (no I/O).

All functions take human-unit numbers (USDC, plain prices, leverage as a
multiplier, percentages as plain numbers where 1 = 1%).
"""

from .fees import (
    MakerTakerFee,
    maker_or_taker_fee_p,
    pair_close_maker_taker_fee_p,
    pair_open_maker_taker_fee_p,
    skew_adjusted_open_fee,
)
from .liquidation import estimate_liquidation_price
from .liquidity import available_liquidity, max_position_size
from .pnl import (
    adjusted_max_gain_p,
    gross_pnl,
    net_pnl,
    pnl_fee_by_gross_profit_p,
    pnl_type_fee,
    position_net_pnl,
)
from .tpsl import (
    pnl_order_min_sl,
    sl_percent_to_price,
    sl_price_to_percent,
    tp_percent_to_price,
    tp_price_to_percent,
)
from .validation import MIN_UPSIDE_SL_P, OrderValidation, validate_order

__all__ = [
    "MIN_UPSIDE_SL_P",
    "gross_pnl",
    "net_pnl",
    "position_net_pnl",
    "pnl_fee_by_gross_profit_p",
    "pnl_type_fee",
    "adjusted_max_gain_p",
    "estimate_liquidation_price",
    "skew_adjusted_open_fee",
    "maker_or_taker_fee_p",
    "pair_open_maker_taker_fee_p",
    "pair_close_maker_taker_fee_p",
    "MakerTakerFee",
    "available_liquidity",
    "max_position_size",
    "tp_percent_to_price",
    "tp_price_to_percent",
    "sl_percent_to_price",
    "sl_price_to_percent",
    "pnl_order_min_sl",
    "validate_order",
    "OrderValidation",
]
