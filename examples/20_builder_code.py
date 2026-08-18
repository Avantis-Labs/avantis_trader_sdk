"""Builder codes: register a per-trade partner fee and attach it to order flow.

A builder code is an on-chain fee config in the BuilderCode registry: trades
attached to your code charge a fee (a percent of the trade's collateral or a
fixed USDC amount per trade), paid by the trader to your fee collector. The
fee is charged on top of the trade's collateral, as a separate USDC transfer
from the trader's wallet in the same transaction.

Fee-eligible actions (the ones that open or add exposure):
    market_open / market_open_coin, limit_open,
    increase_position / increase_position_coin, twap_open
Closes, cancels, margin updates, and TP/SL changes never charge builder fees.

Registration is caller-scoped (msg.sender becomes the code owner) so it cannot
be routed through a delegate key; run the register/modify part with the wallet
that should own the code. Non-developers can use the same flow at
https://delegate.avantisfi.com. Docs: /builders/builder-codes.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis

CODE = "MYAPP"


async def register_and_manage() -> str:
    """Owner-side: check, register, and (optionally) update your code."""
    async with AsyncAvantis() as client:
        # 1. Check availability. registered=False means free to claim; the
        #    response also carries the protocol caps for the fee params.
        info = await client.account.builder_code(CODE)
        print(
            f"registered: {info['registered']}  "
            f"caps: {info['maxFeePercentHuman']}% / {info['maxFixedFeeUsdc']} USDC"
        )

        # 2. Register: 0.05% of each trade's collateral to your collector.
        if not info["registered"]:
            await client.account.register_builder_code(
                CODE,
                fee_collector=client.trade.trader,
                is_percent_fee=True,
                fee_percent=0.05,  # 1 = 1% of collateral
            )

        # (owner only) fees are read live from the registry, so updates apply
        # to all future trades immediately, no redeploys:
        # await client.account.modify_builder_code(
        #     CODE, fee_collector=client.trade.trader,
        #     is_percent_fee=False, fixed_fee_usdc=0.25,
        # )

        # 3. The normalized 32-byte form is what gets attached to order flow.
        info = await client.account.builder_code(CODE)
        print("bytes32 code:", info["code"])
        return str(info["code"])


async def trade_with_code(code_bytes32: str) -> None:
    """User-side: tag the order flow your integration sends for a user.

    `builder_code` is appended as a calldata suffix to every EIP-7702
    transaction the SDK builds (market opens/closes/increases and all
    relayer-passthrough actions) for order-flow attribution. On-chain fee
    charging runs through a builder-specific delegation template wired by
    the Avantis team once your code is registered.
    """
    async with AsyncAvantis(
        # private_key=<your user's delegate/API key>,
        # trader_address=<your user's wallet>,
        builder_code=code_bytes32,
    ) as client:
        # All fee-eligible actions work unchanged; the code rides along:
        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
        # await client.trade.limit_open("ETH/USD", "long", collateral=100,
        #                               leverage=10, price=3000)
        # await client.trade.increase_position("ETH/USD", 0, collateral=50, leverage=10)
        # await client.trade.twap_open("ETH/USD", "long", collateral=500,
        #                              leverage=5, run_time_seconds=3600)


async def main() -> None:
    code = await register_and_manage()
    await trade_with_code(code)


if __name__ == "__main__":
    asyncio.run(main())
