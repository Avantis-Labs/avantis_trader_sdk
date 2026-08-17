"""Fee math: skew-adjusted open fee and maker/taker classification.

Mirrors avantis-ui-v2 hooks/trade/useOpeningFee.ts and useMakerTakerFee.ts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


def skew_adjusted_open_fee(
    *,
    position_size: float,
    is_long: bool,
    oi_long: float,
    oi_short: float,
    skew_eq_params: list[list[float]],
    fee_discount_p: float = 0.0,
) -> tuple[float, float]:
    """(feeP, fee USDC) for opening, adjusted for post-trade OI skew.

    After the hypothetical OI shift, ``oiPct = floor(100 * oppositeOI /
    (newSameSideOI + oppositeOI))``; the pair's skewEqParams line for that
    decile gives ``feeP = (a * oiPct + b) / 10000``.
    """
    if is_long:
        new_same = oi_long + position_size
        oi_pct = math.floor(100 * oi_short / ((new_same + oi_short) or 1))
    else:
        new_same = oi_short + position_size
        oi_pct = math.floor(100 * oi_long / ((new_same + oi_long) or 1))

    pct_index = min(oi_pct // 10, len(skew_eq_params) - 1)
    a, b = skew_eq_params[pct_index][0], skew_eq_params[pct_index][1]
    skew_fee_p = (a * oi_pct + b) / 10000
    fee_p = skew_fee_p * (1 - fee_discount_p / 100)
    return fee_p, position_size * fee_p / 100


@dataclass
class MakerTakerFee:
    fee_p: float
    kind: Literal["maker", "taker", "mixed"]

    @property
    def fee_usdc_for(self) -> float:  # pragma: no cover - convenience only
        return self.fee_p


def maker_or_taker_fee_p(
    coin_oi_long: float,
    coin_oi_short: float,
    initial_coin_oi_long: float,
    initial_coin_oi_short: float,
    position_size_coin_oi: float,
    maker_fee_p: float,
    taker_fee_p: float,
) -> MakerTakerFee:
    """Classify a trade as maker/taker/mixed based on coin-OI skew before/after."""
    if initial_coin_oi_long + initial_coin_oi_short == 0 or coin_oi_long + coin_oi_short == 0:
        return MakerTakerFee(taker_fee_p, "taker")

    pct_before = initial_coin_oi_long / (initial_coin_oi_long + initial_coin_oi_short)
    pct_after = coin_oi_long / (coin_oi_long + coin_oi_short)

    if pct_before > 0.5:
        if pct_after > pct_before:
            return MakerTakerFee(taker_fee_p, "taker")
        if pct_after >= 0.5:
            return MakerTakerFee(maker_fee_p, "maker")
        mixed = (
            maker_fee_p * (initial_coin_oi_long - initial_coin_oi_short)
            + taker_fee_p
            * (position_size_coin_oi - initial_coin_oi_long + initial_coin_oi_short)
        ) / position_size_coin_oi
        return MakerTakerFee(mixed, "mixed")

    if pct_before < 0.5:
        if pct_after < pct_before:
            return MakerTakerFee(taker_fee_p, "taker")
        if pct_after <= 0.5:
            return MakerTakerFee(maker_fee_p, "maker")
        mixed = (
            maker_fee_p * (initial_coin_oi_short - initial_coin_oi_long)
            + taker_fee_p
            * (position_size_coin_oi - initial_coin_oi_short + initial_coin_oi_long)
        ) / position_size_coin_oi
        return MakerTakerFee(mixed, "mixed")

    return MakerTakerFee(taker_fee_p, "taker")


def pair_open_maker_taker_fee_p(
    *,
    initial_coin_oi_long: float,
    initial_coin_oi_short: float,
    position_size_coin_oi: float,
    is_long: bool,
    open_maker_fee_p: float,
    open_taker_fee_p: float,
) -> MakerTakerFee:
    return maker_or_taker_fee_p(
        initial_coin_oi_long + position_size_coin_oi if is_long else initial_coin_oi_long,
        initial_coin_oi_short if is_long else initial_coin_oi_short + position_size_coin_oi,
        initial_coin_oi_long,
        initial_coin_oi_short,
        position_size_coin_oi,
        open_maker_fee_p,
        open_taker_fee_p,
    )


def pair_close_maker_taker_fee_p(
    *,
    initial_coin_oi_long: float,
    initial_coin_oi_short: float,
    position_size_coin_oi: float,
    is_long: bool,
    close_maker_fee_p: float,
    close_taker_fee_p: float,
) -> MakerTakerFee:
    return maker_or_taker_fee_p(
        max(initial_coin_oi_long - position_size_coin_oi, 0)
        if is_long
        else initial_coin_oi_long,
        initial_coin_oi_short
        if is_long
        else max(initial_coin_oi_short - position_size_coin_oi, 0),
        initial_coin_oi_long,
        initial_coin_oi_short,
        position_size_coin_oi,
        close_maker_fee_p,
        close_taker_fee_p,
    )
