"""Referral: register a code, join a code, view stats, claim rebates.

Referral actions execute as your own address (they cannot be routed through a
delegate key); run with the trader key.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        # gasless registration (signs a RegisterCodeReq intent)
        await client.referral.register_code_gasless("MYCODE")

        # a trader joins your code
        # await client.referral.set_code_gasless("SOMEONES_CODE")

        stats = await client.info.referral_stats(client.trade.trader)
        print("referral stats:", stats)

        # claim accumulated USDC rebates (as referrer)
        await client.account.claim_rebate()


if __name__ == "__main__":
    asyncio.run(main())
