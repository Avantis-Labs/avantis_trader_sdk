"""Provide liquidity to the Avantis vault (ERC-4626 tranche, avUSDC)."""

import asyncio

from avantis_trader_sdk_v2 import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:  # trader-key mode (LP is caller-scoped)
        state = await client.lp.state()
        print("vault state:", state)

        apy = await client.info.vault_share_rate_returns()
        print("share-rate returns:", apy)

        # one-time approval of USDC to the tranche, then deposit
        meta = await client.meta()
        await client.account.approve_usdc(1000, spender=meta["addresses"]["tranche"])
        await client.lp.deposit(1000)

        # withdrawals are immediate in v2 (utilization-gated, no epochs)
        await client.lp.withdraw(500)


if __name__ == "__main__":
    asyncio.run(main())
