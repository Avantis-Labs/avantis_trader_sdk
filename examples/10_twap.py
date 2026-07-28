"""TWAP orders: spread a large entry over time in operator-executed slices."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        pair = await client.markets.pair("ETH/USD")
        print("TWAP window:", pair.twap_params.min_run_time, "-", pair.twap_params.max_run_time,
              "s, slice every", pair.twap_params.frequency, "s")

        # TWAP: spread 1000 USDC at 10x over 10 minutes. The SDK signs a
        # TwapOpenOrder intent and submits it to the twap-app API, which sends
        # the registration tx itself and responds with the on-chain twapId.
        # Sizing gotcha: the order executes in run_time/frequency slices and
        # EACH slice must clear the pair's min position
        # (collateral/slices * leverage >= pair.min_lev_pos_usdc),
        # otherwise the contract reverts with BelowMinPosition.
        receipt = await client.trade.twap_open(
            "ETH/USD", "long", collateral=1000, run_time_seconds=600, leverage=10,
            max_leverage=15,
        )
        print("twap open tx:", receipt.tx_hash, "twapId:", receipt.order_id)

        # list active TWAPs (twap-app API; page is 0-based)
        twaps = await client.account.twaps()
        print("twaps:", twaps)

        # cancel by twapId (signed TwapCancelReq)
        if receipt.order_id is not None:
            await client.trade.twap_cancel(receipt.order_id)
            print("cancelled twap", receipt.order_id)


if __name__ == "__main__":
    asyncio.run(main())
