"""Builder codes: register per-order fee caps and charge a rate per order.

A builder code is an on-chain identity in the BuilderCode registry carrying
your fee collector and three PUBLIC per-order fee-rate caps (open/increase,
close, and PnL-pair close), each a percent of the order's NOTIONAL
(collateral x leverage). Your integration then chooses the actual rate per
order, up to the applicable cap; fees are pulled from the trader's USDC
allowance to the registry (never from an allowance to your wallet) and sent
to your collector, atomically with the order placement.

Registration is caller-scoped (msg.sender becomes the code owner) so it
cannot be routed through a delegate key; run the register/modify part with
the wallet that should own the code. Non-developers can use the same flow at
https://delegate.veranta.xyz. Docs: /builders/builder-codes.
"""

import asyncio

from veranta_sdk import AsyncVeranta

CODE = "MYAPP"


async def register_and_manage() -> str:
    """Owner-side: check, register, and (optionally) update your code."""
    async with AsyncVeranta() as client:
        # 1. Check availability. registered=False means free to claim; the
        #    response also carries the governance ceiling every cap obeys.
        info = await client.account.builder_code(CODE)
        print(
            f"registered: {info['registered']}  "
            f"caps: open {info['maxOpenFeePercent']}% / close {info['maxCloseFeePercent']}% "
            f"/ pnl-close {info['maxPnlCloseFeePercent']}%  "
            f"(ceiling {info['globalCapPercent']}%)"
        )

        # 2. Register with your caps. These are MAXIMA the registry enforces
        #    per order; you charge any rate up to them (users see the caps
        #    before approving, so tighter caps build more trust).
        if not info["registered"]:
            await client.account.register_builder_code(
                CODE,
                fee_collector=client.trade.trader,
                max_open_fee_percent=0.1,  # 0.1% of notional per open/increase
                max_close_fee_percent=0.05,
                max_pnl_close_fee_percent=0.05,
            )

        # (owner only) caps/collector are read live from the registry, so
        # updates apply to all future orders immediately, no redeploys:
        # await client.account.modify_builder_code(
        #     CODE, fee_collector=client.trade.trader,
        #     max_open_fee_percent=0.1, max_close_fee_percent=0.05,
        #     max_pnl_close_fee_percent=0,
        # )

        info = await client.account.builder_code(CODE)
        print("bytes32 code:", info["code"])
        return str(info["code"])


async def trade_with_code(code: str) -> None:
    """User-side: attach the code + a per-order rate to the flow you route.

    The tx-builder appends the signed suffix ``code || rate || tag`` to the
    inner trading calldata; the canonical Veranta EIP-7702 template executes
    the trade and charges the fee against the exact order it placed. Builder
    orders relay via blitz (no SSE lifecycle stream), and PnL/Upside pairs
    auto-zero the open rate (their opens are always fee-free on-chain).
    """
    async with AsyncVeranta(
        # private_key=<your user's delegate/API key>,
        # trader_address=<your user's wallet>,
        builder_code=code,  # "MYAPP" or the normalized 32-byte value
        builder_fee_percent=0.05,  # default rate: 0.05% of notional per order
    ) as client:
        # One-time onboarding per user: collateral + builder-fee allowances,
        # both to audited protocol contracts (never to your own wallet):
        # await client.account.approve_usdc()
        # await client.account.approve_builder_fees()

        # 100 x 10 = 1,000 USDC notional -> 0.5 USDC fee at 0.05%:
        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

        # Per-order override, e.g. a cheaper close (must stay <= your cap):
        # await client.trade.market_close("ETH/USD", 0, collateral_to_close=100,
        #                                 builder_fee_percent=0.02)
        # await client.trade.increase_position("ETH/USD", 0, collateral=50,
        #                                      leverage=10)  # default rate


async def main() -> None:
    code = await register_and_manage()
    await trade_with_code(code)


if __name__ == "__main__":
    asyncio.run(main())
