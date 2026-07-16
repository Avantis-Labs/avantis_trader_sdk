"""Open, then fully close a position (partial closes: pass less collateral).

Also shows coin-exposure sizing: target an exact base-asset amount
(e.g. exactly 0.5 ETH) instead of a USD notional.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        pair_index = await client.markets.pair_index("ETH/USD")

        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
        await asyncio.sleep(5)  # wait for operator fill

        data = await client.account.positions()
        pos = next(p for p in data.positions if p.pair_index == pair_index)

        receipt = await client.trade.market_close(
            pos.pair_index,
            pos.index,
            collateral_to_close=float(pos.collateral),  # full close
            is_pnl=pos.is_pnl,
        )
        print("close tx:", receipt.tx_hash)

        # --- coin-exposure variant: open exactly 0.5 ETH of exposure ---
        # leverage is the target; the fill floats within [min, max] bounds
        # await client.trade.market_open_coin(
        #     "ETH/USD", "long", collateral=100, coin_exposure=0.5,
        #     leverage=10, min_leverage=5, max_leverage=15,
        # )
        # ...and close by coin amount:
        # await client.trade.market_close_coin(pair_index, pos.index, coin_exposure=0.5)


if __name__ == "__main__":
    asyncio.run(main())
