"""Builder codes: look up, register, and attach a per-trade partner fee.

A builder code is an on-chain fee config in the BuilderCode registry: trades
attached to your code charge either a percent of the trade's collateral or a
fixed USDC amount, paid by the trader to your fee collector. Registration is
caller-scoped (msg.sender becomes the code owner) so it cannot be routed
through a delegate key; run with the trader key. Non-developers can use the
same flow at https://delegate.avantisfi.com.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        # 1. Check availability (registered=False means free to claim). The
        #    response also carries the protocol caps for the fee params.
        info = await client.account.builder_code("MYAPP")
        print("registered:", info["registered"], "caps:", info["maxFeePercentHuman"], "% /",
              info["maxFixedFeeUsdc"], "USDC")

        # 2. Register: 0.05% of each trade's collateral to your collector.
        if not info["registered"]:
            await client.account.register_builder_code(
                "MYAPP",
                fee_collector=client.trade.trader,
                is_percent_fee=True,
                fee_percent=0.05,  # 1 = 1% of collateral
            )

        # (owner only) switch to a fixed 0.25 USDC per trade later:
        # await client.account.modify_builder_code(
        #     "MYAPP", fee_collector=client.trade.trader,
        #     is_percent_fee=False, fixed_fee_usdc=0.25,
        # )

        # 3. Attach the code to outgoing orders: pass the normalized 32-byte
        #    value as `builder_code` when constructing the client, e.g.
        #    AsyncAvantis(builder_code=info["code"]).
        info = await client.account.builder_code("MYAPP")
        print("attach with: AsyncAvantis(builder_code=", info["code"], ")")


if __name__ == "__main__":
    asyncio.run(main())
