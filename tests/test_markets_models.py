"""Markets snapshot models validated against the REAL testnet /v2/trading
payload (112 pairs, captured 2026-07)."""

import json
from pathlib import Path

import pytest

from avantis_trader_sdk_v2.markets.models import TradingSnapshot

RAW = json.loads((Path(__file__).parent / "vectors" / "trading_snapshot.json").read_text())


@pytest.fixture(scope="module")
def snapshot() -> TradingSnapshot:
    return TradingSnapshot.model_validate(RAW)


def test_full_snapshot_parses(snapshot):
    assert snapshot.pair_count == 112
    assert len(snapshot.pairs) == 112
    assert snapshot.max_trades_per_pair == 40
    assert snapshot.total_oi > 0


def test_eth_pair_fields(snapshot):
    eth = snapshot.pair_by_symbol("ETH/USD")
    assert eth.index == 0
    assert eth.leverages.max_leverage == 75
    assert eth.leverages.pnl_max_leverage == 500
    assert eth.open_fee_p == 0.045
    assert eth.min_lev_pos_usdc == 100
    assert eth.open_interest.long > 0
    assert eth.funding_rate.long != 0 or eth.funding_rate.short != 0
    assert eth.pnl_fees.tier_p and len(eth.pnl_fees.tier_p) == len(eth.pnl_fees.fees_p)
    assert eth.twap_params.frequency > 0
    assert eth.additional_params.open_taker_fee_p > 0
    assert eth.is_market_open  # crypto: always


def test_listed_pairs_have_symbols_and_leverage(snapshot):
    listed = [p for p in snapshot.pairs.values() if p.is_pair_listed]
    assert len(listed) > 100
    for info in listed:
        assert info.from_symbol and info.to_symbol
        assert info.leverages.max_leverage >= info.leverages.min_leverage


def test_delisted_pairs_parse_without_error(snapshot):
    # delisted slots (e.g. index 32) come back with empty symbols — must not crash
    delisted = [p for p in snapshot.pairs.values() if not p.is_pair_listed]
    for p in delisted:
        assert p.index >= 0


def test_symbol_normalization(snapshot):
    a = snapshot.pair_by_symbol("btc/usd")
    b = snapshot.pair_by_symbol("BTC-USD")
    c = snapshot.pair_by_symbol("btc_usd")
    assert a.index == b.index == c.index


def test_forex_market_hours_fields(snapshot):
    forex = [p for p in snapshot.pairs.values() if p.group_index in (2, 3, 6)]
    assert forex, "expected forex/commodity pairs in snapshot"
    for p in forex[:5]:
        assert p.feed.attributes.schedule is not None
