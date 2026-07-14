"""Open-interest headroom / max position size.

Mirrors avantis-ui-v2 lib/trade.ts ``availableLiquidity``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Liquidity:
    long: float
    short: float


def available_liquidity(
    *,
    max_open_interest: float,
    total_oi: float,
    max_group_oi: float,
    group_oi: float,
    max_wallet_oi: float,
    wallet_oi: float,
    group_open_interest_percentage_p: float,
    max_long_oi_p: float,
    max_short_oi_p: float,
    pair_max_oi: float,
    long_oi: float,
    short_oi: float,
    liquidity_buy: float,
    liquidity_sell: float,
) -> Liquidity:
    """Max additional notional (USDC) per side given all OI constraints."""
    max_open_left = max(max_open_interest - total_oi, 0)
    group_left = max(max_group_oi - group_oi, 0)
    wallet_left = max(max_wallet_oi - wallet_oi, 0)

    valid_long = (max_group_oi * group_open_interest_percentage_p / 100) * (max_long_oi_p / 100)
    pair_long_left = min(
        max(pair_max_oi - long_oi - short_oi, 0), max(valid_long - long_oi, 0)
    )
    valid_short = (max_group_oi * group_open_interest_percentage_p / 100) * (
        max_short_oi_p / 100
    )
    pair_short_left = min(
        max(pair_max_oi - long_oi - short_oi, 0), max(valid_short - short_oi, 0)
    )

    return Liquidity(
        long=max(min(max_open_left, group_left, wallet_left, pair_long_left, liquidity_buy), 0),
        short=max(
            min(max_open_left, group_left, wallet_left, pair_short_left, liquidity_sell), 0
        ),
    )


def max_position_size(pair_info, snapshot, *, is_long: bool, wallet_oi: float = 0.0) -> float:
    """Max notional for a new position from live snapshot models.

    ``pair_info``/``snapshot`` are markets.models types; ``wallet_oi`` is the
    trader's current total notional (sum of collateral * leverage).
    """
    group = snapshot.group_info.get(str(pair_info.group_index))
    group_max = getattr(group, "max_open_interest", None) or 0.0
    group_oi_data = getattr(group, "open_interest", None) or {}
    group_oi = float(group_oi_data.get("long", 0)) + float(group_oi_data.get("short", 0))
    extra = pair_info.model_extra or {}
    group_pct = float(
        (extra.get("values") or {}).get("groupOpenInterestPercentageP", 100)
        if isinstance(extra.get("values"), dict)
        else 100
    )
    liq = available_liquidity(
        max_open_interest=snapshot.max_open_interest,
        total_oi=snapshot.total_oi,
        max_group_oi=group_max,
        group_oi=group_oi,
        max_wallet_oi=pair_info.max_wallet_oi,
        wallet_oi=wallet_oi,
        group_open_interest_percentage_p=group_pct,
        max_long_oi_p=pair_info.values.max_long_oi_p,
        max_short_oi_p=pair_info.values.max_short_oi_p,
        pair_max_oi=pair_info.pair_max_oi,
        long_oi=pair_info.open_interest.long,
        short_oi=pair_info.open_interest.short,
        liquidity_buy=pair_info.liquidity.get("buy", float("inf")),
        liquidity_sell=pair_info.liquidity.get("sell", float("inf")),
    )
    return liq.long if is_long else liq.short
