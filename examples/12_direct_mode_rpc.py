"""Direct execution: sign and broadcast transactions yourself (no relayer).

For market makers / power users who run their own key + RPC. Market fills are
still operator-driven (two-step), so poll positions after the tx confirms.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis(
        execution="direct",
        rpc_url="https://your-base-rpc.example",
        # trader-key mode: AVANTIS_PRIVATE_KEY is the trader's own key,
        # AVANTIS_TRADER_ADDRESS unset (or equal to the key's address)
    ) as client:
        receipt = await client.trade.market_open(
            "BTC/USD", "short", collateral=250, leverage=5
        )
        print("mined tx:", receipt.tx_hash)

        data = await client.account.positions()
        print("positions:", len(data.positions))


if __name__ == "__main__":
    asyncio.run(main())
