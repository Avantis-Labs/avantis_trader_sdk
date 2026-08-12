"""Latest prices, execution-price estimate, and OHLCV candles."""

import asyncio
import time

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        price = await client.markets.price("ETH/USD")
        print("ETH/USD last price:", price)

        # risk-engine v2 spread (what the v2 UI quotes; coin-sized request).
        spread = await client.markets.spread(
            "ETH/USD", collateral=1000, leverage=10, is_long=True
        )
        spread_p = spread["spreadPct"]
        print(f"spread (SM{spread['spreadMechanism']:03d}): {spread_p:.4f}%"
              " -> est. execution price:", price * (1 + spread_p / 100))

        # Legacy risk-engine (still what mainnet serves until the v2 cutover).
        # spread = await client.markets.dynamic_spread(
        #     "ETH/USD", collateral=1000, leverage=10, is_long=True
        # )

        now = int(time.time())
        candles = await client.markets.candles("Crypto.ETH/USD", "60", now - 6 * 3600, now)
        print("candles:", len(candles.get("t", [])) if isinstance(candles, dict) else candles)


if __name__ == "__main__":
    asyncio.run(main())
