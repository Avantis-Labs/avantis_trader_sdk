"""Update TP/SL and create partial take-profit triggers.

- Full (global) TP/SL update is intent-only in v2 (no public contract entry
  point): the SDK signs an UpdateTpSlReq and submits it to the core API
  price-triggers endpoint, which executes it through the Avantis operator
  (the same path in relayer and direct mode). None keeps a leg, 0 clears it
  (a TP of 0 resets to the pair's max-gain cap; a position always has a TP).
- Partial TP/SL are trigger orders stored with the operator (off-chain) and
  executed on-chain when the price hits.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        data = await client.account.positions()
        pos = data.positions[0]

        # full-position TP/SL (None = keep the current level, 0 = clear)
        await client.trade.update_tp_sl(
            pos.pair_index, pos.index, take_profit=4200, stop_loss=2900
        )

        # partial TP: close 25% of the coin exposure at a fixed price.
        # The signed order is stored off-chain; the response carries its
        # entityId; keep it to update or cancel later.
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
        print("stored partial TP:", order["price"], "entityId:", order["entityId"])

        # move the trigger: atomic in-place replacement (pass the FULL order).
        # The backend mints a NEW entityId on update; adopt the returned one.
        order = await client.trade.update_partial_tp_sl(
            order["entityId"],
            pos.pair_index,
            pos.index,
            side=pos.side,
            kind="take_profit",
            coin_exposure=coin_exposure,
            trigger="fixed",
            price=price * 1.10,
        )
        print("updated partial TP:", order["price"], "new entityId:", order["entityId"])

        # cancel it again (signs CancelOffchainOrder over the entityId)
        await client.trade.cancel_partial_tp_sl(order)
        print("cancelled")


if __name__ == "__main__":
    asyncio.run(main())
