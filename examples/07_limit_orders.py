"""Place, update, and cancel a limit order.

Limit opens escrow USDC on placement. On the relayer route they go through
the gasless TX_RELAY passthrough (same as the Avantis UI).
"""

import asyncio

from avantis_trader_sdk_v2 import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        price = await client.markets.price("ETH/USD")

        await client.trade.limit_open(
            "ETH/USD", "long", collateral=100, leverage=10, price=price * 0.97
        )

        data = await client.account.positions()
        order = data.limit_orders[-1]
        print("placed order index:", order.index, "at", float(order.price))

        await client.trade.update_limit_order(
            order.pair_index, order.index, price=price * 0.95, take_profit=price * 1.1
        )
        await client.trade.cancel_limit_order(order.pair_index, order.index)
        print("order cancelled, USDC refunded")


if __name__ == "__main__":
    asyncio.run(main())
