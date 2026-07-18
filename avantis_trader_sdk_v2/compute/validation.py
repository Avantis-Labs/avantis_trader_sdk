"""Pre-trade validation — same rules the Avantis UI enforces.

Note the tx-builder API also validates server-side (min position, leverage
envelope, headroom, market hours) and returns human-readable 400s; this local
validator is for building UIs/bots that want checks before any network call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .liquidity import max_position_size
from .tpsl import pnl_order_min_sl

MIN_ZFP_SL_P = 5.0
SL_BUFFER_SPREAD_P = 0.01  # added to the dynamic spread before scaling by leverage
SPREAD_ERROR_THRESHOLD_P = 0.5
SPREAD_LOSS_THRESHOLD_P = 25.1


@dataclass
class OrderValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_order(
    pair_info,
    snapshot,
    *,
    collateral: float,
    leverage: float,
    is_long: bool,
    is_pnl: bool = False,
    limit_price: float | None = None,
    market_price: float | None = None,
    take_profit_percent: float | None = None,
    stop_loss_percent: float | None = None,
    dynamic_spread_p: float | None = None,
    wallet_oi: float = 0.0,
    open_trades_on_pair: int = 0,
) -> OrderValidation:
    """Validate a prospective open order against pair config and live OI."""
    v = OrderValidation()
    position_size = collateral * leverage

    # pair state
    if not pair_info.is_pair_listed:
        v.errors.append(f"{pair_info.symbol} is delisted")
    if pair_info.additional_params.close_only_mode:
        v.errors.append(f"{pair_info.symbol} is in close-only mode")
    if not pair_info.is_market_open:
        v.errors.append(f"{pair_info.symbol} market is closed")

    # leverage envelope
    lev = pair_info.leverages
    min_lev = lev.pnl_min_leverage if is_pnl else lev.min_leverage
    max_lev = lev.pnl_max_leverage if is_pnl else lev.max_leverage
    if leverage < min_lev or leverage > max_lev:
        v.errors.append(f"leverage {leverage}x outside [{min_lev}, {max_lev}]")

    # size limits
    if position_size < pair_info.min_lev_pos_usdc:
        v.errors.append(
            f"position {position_size:.2f} USDC below minimum {pair_info.min_lev_pos_usdc}"
        )
    max_pos = max_position_size(pair_info, snapshot, is_long=is_long, wallet_oi=wallet_oi)
    if position_size > max_pos:
        v.errors.append(f"position {position_size:.2f} USDC exceeds available headroom {max_pos:.2f}")

    # trades per pair
    if snapshot.max_trades_per_pair and open_trades_on_pair >= snapshot.max_trades_per_pair:
        v.errors.append(f"max {snapshot.max_trades_per_pair} trades per pair reached")

    # limit price direction
    if limit_price is not None and market_price is not None:
        if is_long and limit_price >= market_price:
            v.errors.append("limit price must be below market for longs")
        if not is_long and limit_price <= market_price:
            v.errors.append("limit price must be above market for shorts")

    # TP bounds
    if take_profit_percent is not None:
        max_tp = pair_info.values.max_gain_p
        if is_pnl and pair_info.pnl_fees.tier_p:
            from .pnl import adjusted_max_gain_p

            max_tp = adjusted_max_gain_p(
                max_tp, pair_info.pnl_fees.tier_p, pair_info.pnl_fees.fees_p
            )
        if take_profit_percent > max_tp:
            v.errors.append(f"take profit {take_profit_percent}% above max {max_tp:.0f}%")

    # SL bounds
    if stop_loss_percent is not None:
        if stop_loss_percent > pair_info.values.max_sl_p:
            v.errors.append(
                f"stop loss {stop_loss_percent}% above max {pair_info.values.max_sl_p}%"
            )
        # UI rule: slPLimit = (priceImpactBenefit + SL_BUFFER_SPREAD) * leverage,
        # spread and buffer both in plain percent units; ZFP floors at
        # max(slPLimit, MIN_ZFP_SL_GE) and the pnlOrderMinSL curve.
        sl_limit = (
            ((dynamic_spread_p or 0.0) + SL_BUFFER_SPREAD_P) * leverage
            if dynamic_spread_p is not None
            else 0.0
        )
        if is_pnl:
            min_sl = max(sl_limit, MIN_ZFP_SL_P, pnl_order_min_sl(leverage))
            if stop_loss_percent < min_sl:
                v.errors.append(f"ZFP stop loss must be >= {min_sl:.2f}%")
        elif dynamic_spread_p is not None and stop_loss_percent < sl_limit:
            v.errors.append(
                f"stop loss can't be less than {sl_limit:.2f}% to guarantee execution"
            )

    # spread sanity
    if dynamic_spread_p is not None:
        if dynamic_spread_p / 2 > SPREAD_ERROR_THRESHOLD_P:
            v.errors.append(f"spread too high ({dynamic_spread_p:.3f}%)")
        elif dynamic_spread_p * leverage >= SPREAD_LOSS_THRESHOLD_P:
            v.errors.append(
                f"spread x leverage = {dynamic_spread_p * leverage:.1f}% >= {SPREAD_LOSS_THRESHOLD_P}%"
            )

    return v
