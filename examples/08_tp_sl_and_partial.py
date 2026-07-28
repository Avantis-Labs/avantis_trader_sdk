"""Update TP/SL and create partial take-profit triggers.

- Full TP/SL update is intent-only in v2 (no public contract entry point);
  the SDK routes it through the relayer even in direct mode.
- Partial TP/SL are trigger orders stored with the operator (off-chain) and
  executed on-chain when the price hits.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        data = await client.account.positions()
        pos = data.positions[0]

        # full-position TP/SL (0 = remove)
        await client.trade.update_tp_sl(
            pos.pair_index, pos.index, take_profit=4200, stop_loss=2900
        )

        # partial TP: close 25% of the coin exposure at a fixed price.
        # The signed order is stored off-chain; the response carries its
        # documentId; keep it to update or cancel later.
        price = await client.markets.price(pos.pair_index)
        coin_exposure = float(pos.position_size) / price * 0.25
        order = await client.trade.partial_tp_sl(
            pos.pair_index,
            pos.index,
            side=pos.side,
            kind="take_profit",
            coin_exposure=coin_exposure,
            trigger="fixed",
            price=price * 1.05,
        )
        print("stored partial TP:", order["price"], "documentId:", order["documentId"])

        # move the trigger: atomic in-place replacement (pass the FULL order)
        order = await client.trade.update_partial_tp_sl(
            order["documentId"],
            pos.pair_index,
            pos.index,
            side=pos.side,
            kind="take_profit",
            coin_exposure=coin_exposure,
            trigger="fixed",
            price=price * 1.10,
        )
        print("updated partial TP:", order["price"])

        # cancel it again (signs CancelOffchainOrder over the documentId)
        await client.trade.cancel_partial_tp_sl(order)
        print("cancelled")


if __name__ == "__main__":
    asyncio.run(main())
