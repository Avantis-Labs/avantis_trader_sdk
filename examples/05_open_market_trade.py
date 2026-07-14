"""Open a market position — the default gasless relayer route.

The SDK fetches the intent from the tx-builder API, signs it locally (with a
digest correctness check), and queues it with the Avantis relayer. No RPC, no
ETH needed.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        receipt = await client.trade.market_open(
            "ETH/USD",
            "long",
            collateral=100,       # 100 USDC
            leverage=10,          # 10x
            take_profit=4000,     # optional; omit for none
            stop_loss=2800,       # optional
            slippage_percent=1,
        )
        print("route:", receipt.route)
        print("tx:", receipt.tx_hash)
        # A confirmed tx != a filled trade: market orders are fulfilled by the
        # operator. Poll positions to see the fill:
        await asyncio.sleep(3)
        data = await client.account.positions()
        print("open positions:", len(data.positions))


if __name__ == "__main__":
    asyncio.run(main())
