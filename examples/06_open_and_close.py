"""Open, then fully close a position (partial closes: pass less collateral).

Also shows coin-exposure sizing: target an exact base-asset amount
(e.g. exactly 0.5 ETH) instead of a USD notional.
"""

import asyncio

from veranta_sdk import AsyncVeranta


async def main() -> None:
    async with AsyncVeranta() as client:
        pair_index = await client.markets.pair_index("ETH/USD")

        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

        # Wait for the operator fill to show up in positions. Base has had 200 ms
        # blocks since Denim, so this takes about a second: poll every 0.25 s
        # instead of sleeping for seconds.
        pos = None
        for _ in range(20):  # up to about 5 s
            data = await client.account.positions()
            pos = next((p for p in data.positions if p.pair_index == pair_index), None)
            if pos is not None:
                break
            await asyncio.sleep(0.25)
        if pos is None:
            raise SystemExit("the new position is not listed yet; poll for longer")

        receipt = await client.trade.market_close(
            pos.pair_index,
            pos.index,
            collateral_to_close=float(pos.collateral),  # full close
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
