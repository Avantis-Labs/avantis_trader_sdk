"""Upside markets (formerly "ZFP"/zero-fee): discover and trade them.

Upside markets are separate pairs suffixed _UPSIDE (BTC_UPSIDE/USD trades
next to BTC/USD on the same price feed). They charge no open/close fee and
take a tiered profit share on gains instead.

Routing is automatic: opening or closing on an upside pair sends the PnL
(Upside) order type — there is no flag to pass, the pair determines the
type. Upside pairs are market-only (no limit/stop opens, no TWAP; the SDK
raises a ValidationError before any network call).
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        # -- discover upside markets ------------------------------------
        upside = await client.markets.upside_pairs()
        for index, pair in upside.items():
            print(f"{index:>4}  {pair.symbol:<20} (base market {pair.base_symbol})")

        # ...or jump from a fixed-fee market to its upside twin
        btc_upside = await client.markets.upside_pair_for("BTC/USD")
        print("BTC/USD upside twin:", btc_upside.index, btc_upside.symbol)

        # -- open: by symbol or by pair index, no flag needed ------------
        receipt = await client.trade.market_open(
            "BTC_UPSIDE",          # or btc_upside.index
            "long",
            collateral=100,
            leverage=10,
        )
        print("open tx:", receipt.tx_hash)

        await asyncio.sleep(5)  # wait for the operator fill

        # -- close: also routes automatically ----------------------------
        data = await client.account.positions()
        pos = next(p for p in data.positions if p.pair_index == btc_upside.index)
        print("position is_upside:", pos.is_upside)

        receipt = await client.trade.market_close(
            pos.pair_index,
            pos.index,
            collateral_to_close=float(pos.collateral),  # full close
        )
        print("close tx:", receipt.tx_hash)


if __name__ == "__main__":
    asyncio.run(main())
