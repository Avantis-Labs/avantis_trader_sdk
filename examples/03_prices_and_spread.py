"""Latest prices, execution-price estimate, and OHLCV candles."""

import asyncio
import time

from avantis_trader_sdk_v2 import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        price = await client.markets.price("ETH/USD")
        print("ETH/USD last price:", price)

        spread = await client.markets.dynamic_spread(
            "ETH/USD", collateral=1000, leverage=10, is_long=True
        )
        spread_p = spread["dynamicSpreadPct"]
        print(f"dynamic spread: {spread_p:.4f}% -> est. execution price:",
              price * (1 + spread_p / 100))

        now = int(time.time())
        candles = await client.markets.candles("Crypto.ETH/USD", "60", now - 6 * 3600, now)
        print("candles:", len(candles.get("t", [])) if isinstance(candles, dict) else candles)


if __name__ == "__main__":
    asyncio.run(main())
