"""Deposit/withdraw collateral and increase position size."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        data = await client.account.positions()
        pos = data.positions[0]

        # add 50 USDC margin (reduces leverage / moves liq price away)
        await client.trade.update_margin(pos.pair_index, pos.index, "deposit", 50)

        # withdraw 20 USDC back
        await client.trade.update_margin(pos.pair_index, pos.index, "withdraw", 20)

        # add 100 USDC at 10x on top of the existing position
        await client.trade.increase_position(
            pos.pair_index, pos.index, collateral=100, leverage=10
        )


if __name__ == "__main__":
    asyncio.run(main())
