"""Open, then fully close a position (partial closes: pass less collateral)."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
        await asyncio.sleep(5)  # wait for operator fill

        data = await client.account.positions()
        pos = next(p for p in data.positions if p.pair_index == 0)

        receipt = await client.trade.market_close(
            pos.pair_index,
            pos.index,
            collateral_to_close=float(pos.collateral),  # full close
            is_pnl=pos.is_pnl,
        )
        print("close tx:", receipt.tx_hash)


if __name__ == "__main__":
    asyncio.run(main())
