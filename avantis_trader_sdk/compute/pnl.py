"""PnL math — mirrors avantis-ui-v2 lib/utils.ts and positions.helper.ts."""

from __future__ import annotations

from dataclasses import dataclass


def gross_pnl(
    current_price: float,
    open_price: float,
    collateral: float,
    leverage: float,
    is_long: bool,
) -> float:
    """(current - open) * dir / open * leverage * collateral."""
    direction = 1 if is_long else -1
    return (current_price - open_price) * direction / open_price * leverage * collateral


def pnl_fee_by_gross_profit_p(
    tier_p: list[float], desired_gross_profit_p: float, fees_p: list[float]
) -> float:
    """Tiered Upside profit-sharing fee %: highest tier whose threshold is met."""
    for i in range(len(tier_p) - 1, -1, -1):
        if desired_gross_profit_p >= tier_p[i]:
            return fees_p[i] if i < len(fees_p) else 0.0
    return fees_p[0] if fees_p else 0.0


def pnl_type_fee(
    tier_p: list[float], fees_p: list[float], profit_p: float, pnl: float
) -> tuple[float, float]:
    """(feeP, fee USDC) for a realized Upside profit; 0 when pnl <= 0."""
    if pnl <= 0:
        return 0.0, 0.0
    i = 0
    while i < len(tier_p) and profit_p >= tier_p[i]:
        i += 1
    if i == len(tier_p):
        i = len(tier_p) - 1
    return fees_p[i], pnl * fees_p[i] / 100


def adjusted_max_gain_p(max_gain_p: float, tier_p: list[float], fees_p: list[float]) -> float:
    """Max TP % for Upside positions, net of the profit-sharing fee at that level."""
    return max_gain_p * (100 - pnl_fee_by_gross_profit_p(tier_p, max_gain_p, fees_p)) / 100


@dataclass
class NetPnlBreakdown:
    gross: float
    closing_fee: float
    rollover_fee: float
    funding_fee: float
    loss_protection: float
    profit_share_fee: float
    net: float


def net_pnl(
    *,
    current_price: float,
    open_price: float,
    collateral: float,
    leverage: float,
    is_long: bool,
    is_upside: bool = False,
    close_fee_p: float = 0.0,
    fee_discount_p: float = 0.0,
    rollover_fee: float = 0.0,
    funding_fee: float = 0.0,
    loss_protection_p: float = 0.0,
    pnl_tier_p: list[float] | None = None,
    pnl_fees_p: list[float] | None = None,
) -> NetPnlBreakdown:
    """Unrealized net PnL breakdown for an open position (UI parity).

    - Fixed-fee (is_upside=False): net = gross - closingFee - rollover - funding
      + lossProtection (loss protection only offsets negative gross, capped).
    - Upside (is_upside=True): net = gross * (1 - tieredFeeP/100) - rollover - funding.
    """
    g = gross_pnl(current_price, open_price, collateral, leverage, is_long)

    if is_upside:
        gross_p = g / collateral * 100 if collateral else 0.0
        fee_p = (
            pnl_fee_by_gross_profit_p(pnl_tier_p or [], gross_p, pnl_fees_p or [])
            if gross_p > 0
            else 0.0
        )
        share = g * fee_p / 100
        net = g - share - rollover_fee - funding_fee
        return NetPnlBreakdown(
            gross=g,
            closing_fee=0.0,
            rollover_fee=rollover_fee,
            funding_fee=funding_fee,
            loss_protection=0.0,
            profit_share_fee=share,
            net=net,
        )

    closing_fee = (
        (collateral * leverage + g) * close_fee_p * (1 - fee_discount_p / 100) / 100
    )
    protection = 0.0
    if g < 0 and loss_protection_p > 0:
        protection = min(-g * loss_protection_p / 100, collateral * loss_protection_p / 100)
    net = g - closing_fee - rollover_fee - funding_fee + protection
    return NetPnlBreakdown(
        gross=g,
        closing_fee=closing_fee,
        rollover_fee=rollover_fee,
        funding_fee=funding_fee,
        loss_protection=protection,
        profit_share_fee=0.0,
        net=net,
    )


def position_net_pnl(position, pair_info, current_price: float) -> NetPnlBreakdown:
    """Net PnL for an ``account.models.Position`` using its pair snapshot info."""
    return net_pnl(
        current_price=current_price,
        open_price=float(position.open_price),
        collateral=float(position.collateral),
        leverage=float(position.leverage),
        is_long=position.buy,
        is_upside=position.is_upside,
        close_fee_p=pair_info.close_fee_p,
        rollover_fee=float(position.rollover_fee),
        funding_fee=float(position.unrealised_funding_fee),
        loss_protection_p=pair_info.loss_protection_multiplier.get(
            str(int(position.loss_protection_raw or 0)), 0.0
        ),
        pnl_tier_p=pair_info.pnl_fees.tier_p,
        pnl_fees_p=pair_info.pnl_fees.fees_p,
    )
