"""TWAP and RFQ orders (institutional execution styles)."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        pair = await client.markets.pair("ETH/USD")
        print("TWAP window:", pair.twap_params.min_run_time, "-", pair.twap_params.max_run_time,
              "s, slice every", pair.twap_params.frequency, "s")

        # TWAP: spread 1000 USDC at 10x over 10 minutes
        receipt = await client.trade.twap_open(
            "ETH/USD", "long", collateral=1000, run_time_seconds=600, default_leverage=10,
            max_leverage=15,
        )
        print("twap open tx:", receipt.tx_hash)

        # list active TWAPs / cancel
        twaps = await client.account.twaps()
        print("twaps:", twaps)
        # await client.trade.twap_cancel(twap_id=...)

        # RFQ: request a fill at a wanted price with bounded slippage
        price = await client.markets.price("ETH/USD")
        await client.trade.rfq_open(
            "ETH/USD", "long", collateral=1000, default_leverage=10, max_leverage=15,
            wanted_price=price, max_slippage_percent=0.5,
        )


if __name__ == "__main__":
    asyncio.run(main())
