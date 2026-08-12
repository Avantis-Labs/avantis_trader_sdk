"""Pair catalog: leverage envelopes, fees, funding rates, OI, market hours."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        eth = await client.markets.pair("ETH/USD")
        print(f"{eth.symbol} (pair {eth.index})")
        print("  leverage:", eth.leverages.min_leverage, "-", eth.leverages.max_leverage, "x")
        print("  open/close fee %:", eth.open_fee_p, "/", eth.close_fee_p)
        print("  funding rate (long/short):", eth.funding_rate.long, "/", eth.funding_rate.short)
        print("  OI long/short:", eth.open_interest.long, "/", eth.open_interest.short)
        print("  min position USDC:", eth.min_lev_pos_usdc)
        print("  market open:", eth.is_market_open)

        snapshot = await client.markets.snapshot()
        print("\ntotal pairs:", snapshot.pair_count, "| protocol OI:", snapshot.total_oi)


if __name__ == "__main__":
    asyncio.run(main())
