"""Compute-layer tests: formulas verified against hand-computed values that
mirror the avantis-ui-v2 implementations."""

import pytest

from avantis_trader_sdk.compute import (
    adjusted_max_gain_p,
    available_liquidity,
    estimate_liquidation_price,
    gross_pnl,
    maker_or_taker_fee_p,
    net_pnl,
    pnl_fee_by_gross_profit_p,
    pnl_order_min_sl,
    skew_adjusted_open_fee,
    sl_percent_to_price,
    tp_percent_to_price,
    tp_price_to_percent,
    validate_order,
)
from avantis_trader_sdk.markets.models import TradingSnapshot

# ETH/USD pair snapshot subset (from the testnet /v2/trading payload)
ETH_PAIR = {
    "index": 0,
    "from": "ETH",
    "to": "USD",
    "groupIndex": 0,
    "isPairListed": True,
    "leverages": {"minLeverage": 1, "maxLeverage": 75, "pnlMinLeverage": 75, "pnlMaxLeverage": 500},
    "spreadP": 0.01,
    "openFeeP": 0.045,
    "closeFeeP": 0.045,
    "minLevPosUSDC": 100,
    "openInterest": {"long": 312589.24, "short": 417641.1},
    "pairOI": 730230.34,
    "pairMaxOI": 26118551.95,
    "maxWalletOI": 45205186.06,
    "values": {
        "maxGainP": 2500,
        "maxSlP": 80,
        "maxLongOiP": 50,
        "maxShortOiP": 50,
        "groupOpenInterestPercentageP": 100,
    },
    "pnlFees": {
        "numTiers": 10,
        "tierP": [1, 5, 25, 50, 100, 250, 500, 1500, 2500, 3000],
        "feesP": [80, 50, 45, 37.5, 27.5, 25, 25, 22.5, 15, 2.5],
    },
    "skewEqParams": [[0, 450]] * 10,
    "liquidity": {"buy": 26118551.95, "sell": 26118551.95},
    "additionalPairParams2": {
        "openMakerFeeP": 0.01,
        "closeMakerFeeP": 0.01,
        "openTakerFeeP": 0.05,
        "closeTakerFeeP": 0.05,
        "closeOnlyMode": False,
    },
}

SNAPSHOT = TradingSnapshot.model_validate(
    {
        "pairCount": 1,
        "maxTradesPerPair": 40,
        "totalOi": 7397826.55,
        "maxOpenInterest": 90410372.13,
        "pairInfos": {"0": ETH_PAIR},
        # live payload shape: group totals are groupMaxOI/groupOI scalars
        "groupInfo": {"0": {"name": "CRYPTO1", "groupMaxOI": 50000000, "groupOI": 7e6}},
    }
)
PAIR = SNAPSHOT.pairs[0]


def test_gross_pnl_long_and_short():
    # +10% price move at 10x on 100 collateral = +100
    assert gross_pnl(3300, 3000, 100, 10, True) == pytest.approx(100)
    assert gross_pnl(3300, 3000, 100, 10, False) == pytest.approx(-100)


def test_pnl_fee_tiers():
    tiers = ETH_PAIR["pnlFees"]["tierP"]
    fees = ETH_PAIR["pnlFees"]["feesP"]
    assert pnl_fee_by_gross_profit_p(tiers, 0.5, fees) == 80  # below first tier -> feesP[0]
    assert pnl_fee_by_gross_profit_p(tiers, 5, fees) == 50
    assert pnl_fee_by_gross_profit_p(tiers, 120, fees) == 27.5
    assert pnl_fee_by_gross_profit_p(tiers, 5000, fees) == 2.5


def test_adjusted_max_gain():
    tiers = ETH_PAIR["pnlFees"]["tierP"]
    fees = ETH_PAIR["pnlFees"]["feesP"]
    # at 2500% the fee tier is 15 -> adjusted = 2500 * 0.85
    assert adjusted_max_gain_p(2500, tiers, fees) == pytest.approx(2125)


def test_net_pnl_fixed_fee():
    out = net_pnl(
        current_price=3300,
        open_price=3000,
        collateral=100,
        leverage=10,
        is_long=True,
        close_fee_p=0.045,
        rollover_fee=1.5,
        funding_fee=0.5,
    )
    assert out.gross == pytest.approx(100)
    # closing fee = (1000 + 100) * 0.045% = 0.495
    assert out.closing_fee == pytest.approx(0.495)
    assert out.net == pytest.approx(100 - 0.495 - 1.5 - 0.5)


def test_net_pnl_upside_profit_share():
    out = net_pnl(
        current_price=3300,
        open_price=3000,
        collateral=100,
        leverage=10,
        is_long=True,
        is_upside=True,
        pnl_tier_p=ETH_PAIR["pnlFees"]["tierP"],
        pnl_fees_p=ETH_PAIR["pnlFees"]["feesP"],
    )
    # grossP = 100% -> tier fee 27.5% of profit
    assert out.profit_share_fee == pytest.approx(27.5)
    assert out.net == pytest.approx(72.5)


def test_net_pnl_loss_protection():
    out = net_pnl(
        current_price=2700,
        open_price=3000,
        collateral=100,
        leverage=10,
        is_long=True,
        close_fee_p=0.045,
        loss_protection_p=8,
    )
    assert out.gross == pytest.approx(-100)
    assert out.loss_protection == pytest.approx(8)  # min(8, 8) of 100 loss / collateral cap


def test_liquidation_price():
    # long: distance = 3000 * (100*0.85) / 1000 = 255
    assert estimate_liquidation_price(
        open_price=3000, collateral=100, leverage=10, is_long=True
    ) == pytest.approx(2745)
    assert estimate_liquidation_price(
        open_price=3000, collateral=100, leverage=10, is_long=False
    ) == pytest.approx(3255)


def test_skew_adjusted_open_fee():
    fee_p, fee = skew_adjusted_open_fee(
        position_size=10000,
        is_long=True,
        oi_long=ETH_PAIR["openInterest"]["long"],
        oi_short=ETH_PAIR["openInterest"]["short"],
        skew_eq_params=ETH_PAIR["skewEqParams"],
    )
    # flat skewEqParams [0, 450] -> feeP = 450/10000 = 0.045%
    assert fee_p == pytest.approx(0.045)
    assert fee == pytest.approx(4.5)


def test_maker_taker():
    # balanced book, long trade pushes long side -> taker
    r = maker_or_taker_fee_p(110, 100, 100, 100, 10, 0.01, 0.05)
    assert r.kind == "taker"
    # short-heavy book, long trade balances -> maker
    r = maker_or_taker_fee_p(110, 120, 100, 120, 10, 0.01, 0.05)
    assert r.kind == "maker"
    # crossing the 0.5 boundary -> mixed
    r = maker_or_taker_fee_p(140, 120, 100, 120, 40, 0.01, 0.05)
    assert r.kind == "mixed"
    assert 0.01 < r.fee_p < 0.05


def test_available_liquidity_constraints():
    liq = available_liquidity(
        max_open_interest=1000,
        total_oi=900,
        max_group_oi=10000,
        group_oi=0,
        max_wallet_oi=10000,
        wallet_oi=0,
        group_open_interest_percentage_p=100,
        max_long_oi_p=50,
        max_short_oi_p=50,
        pair_max_oi=10000,
        long_oi=0,
        short_oi=0,
        liquidity_buy=1e9,
        liquidity_sell=1e9,
    )
    assert liq.long == 100  # bound by protocol max OI headroom


def test_tp_sl_conversions_roundtrip():
    # 100% profit at 10x = 10% price move
    price = tp_percent_to_price(3000, 100, 10, True)
    assert price == pytest.approx(3300)
    assert tp_price_to_percent(3000, price, 10, True) == pytest.approx(100)
    # 50% loss at 10x = 5% price move
    assert sl_percent_to_price(3000, 50, 10, True) == pytest.approx(2850)
    # short mirrors
    assert tp_percent_to_price(3000, 100, 10, False) == pytest.approx(2700)


def test_pnl_order_min_sl_piecewise():
    assert pnl_order_min_sl(10) == pytest.approx(1.5)
    assert pnl_order_min_sl(25) == pytest.approx(3.75)
    assert pnl_order_min_sl(100) == pytest.approx(11.25)
    assert pnl_order_min_sl(500) == pytest.approx(45)
    assert pnl_order_min_sl(5000) == 54


def test_validate_order_happy_path():
    v = validate_order(
        PAIR, SNAPSHOT, collateral=100, leverage=10, is_long=True, take_profit_percent=100
    )
    assert v.ok, v.errors


def test_validate_order_failures():
    v = validate_order(PAIR, SNAPSHOT, collateral=5, leverage=10, is_long=True)
    assert any("below minimum" in e for e in v.errors)

    v = validate_order(PAIR, SNAPSHOT, collateral=100, leverage=100, is_long=True)
    assert any("outside" in e for e in v.errors)

    v = validate_order(
        PAIR, SNAPSHOT, collateral=100, leverage=10, is_long=True, take_profit_percent=3000
    )
    assert any("take profit" in e for e in v.errors)

    v = validate_order(
        PAIR,
        SNAPSHOT,
        collateral=100,
        leverage=75,
        is_long=True,
        stop_loss_percent=1,
        dynamic_spread_p=0.05,
    )
    # slLimit = (0.05 + 0.01) * 75 = 4.5 > 1
    assert any("guarantee execution" in e for e in v.errors)


def test_validate_order_upside_rules_derive_from_pair():
    """is_upside=None (default) derives the Upside rule set from the pair
    itself — matching the SDK's automatic order-type routing."""
    import json

    upside_raw = json.loads(json.dumps(ETH_PAIR))
    upside_raw.update({"index": 116, "from": "ETH_UPSIDE"})
    upside_raw["storagePairParams"] = {"isPnlTypeAllowed": 1}
    upside_snap = TradingSnapshot.model_validate(
        {
            "pairCount": 1,
            "maxTradesPerPair": 40,
            "totalOi": 7397826.55,
            "maxOpenInterest": 90410372.13,
            "pairInfos": {"116": upside_raw},
            "groupInfo": {"0": {"name": "CRYPTO1", "groupMaxOI": 50000000, "groupOI": 7e6}},
        }
    )
    upside_pair = upside_snap.pairs[116]
    assert upside_pair.is_upside
    assert upside_pair.storage_pair_params.is_pnl_type_allowed == 1

    # PnL leverage envelope [75, 500] applies automatically
    v = validate_order(upside_pair, upside_snap, collateral=100, leverage=10, is_long=True)
    assert any("outside [75" in e for e in v.errors)

    # Upside SL floor: max(MIN_UPSIDE_SL_P, pnl_order_min_sl) applies
    v = validate_order(
        upside_pair, upside_snap,
        collateral=100, leverage=100, is_long=True, stop_loss_percent=2,
    )
    assert any("Upside stop loss" in e for e in v.errors)

    # explicit override still wins (fixed-fee rules on the upside pair)
    v = validate_order(
        upside_pair, upside_snap,
        collateral=100, leverage=10, is_long=True, is_upside=False,
    )
    assert not any("outside" in e for e in v.errors)


def test_market_hours_crypto_always_open():
    assert PAIR.is_market_open


def test_pair_lookup_by_symbol():
    assert SNAPSHOT.pair_by_symbol("eth-usd").index == 0
    assert SNAPSHOT.pair_by_symbol("ETH/USD").symbol == "ETH/USD"
