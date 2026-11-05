"""Upside markets (formerly "ZFP"/zero-fee): discover and trade them.

Upside markets are separate pairs suffixed _UPSIDE (BTC_UPSIDE/USD trades
next to BTC/USD on the same price feed). They charge no open/close fee and
take a tiered profit share on gains instead.

Routing is automatic: opening or closing on an upside pair sends the PnL
(Upside) order type; there is no flag to pass, the pair determines the
type. Upside pairs are market-only (no limit/stop opens, no TWAP; the SDK
raises a ValidationError before any network call).
"""

import asyncio

from veranta_sdk import AsyncVeranta


async def main() -> None:
    async with AsyncVeranta() as client:
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

        # Wait for the operator fill to show up in positions. Base has had 200 ms
        # blocks since Denim, so this takes about a second: poll every 0.25 s
        # instead of sleeping for seconds.
        pos = None
        for _ in range(20):  # up to about 5 s
            data = await client.account.positions()
            pos = next((p for p in data.positions if p.pair_index == btc_upside.index), None)
            if pos is not None:
                break
            await asyncio.sleep(0.25)
        if pos is None:
            raise SystemExit("the new position is not listed yet; poll for longer")

        # -- close: also routes automatically ----------------------------
        print("position is_upside:", pos.is_upside)

        receipt = await client.trade.market_close(
            pos.pair_index,
            pos.index,
            collateral_to_close=float(pos.collateral),  # full close
        )
        print("close tx:", receipt.tx_hash)


if __name__ == "__main__":
    asyncio.run(main())
