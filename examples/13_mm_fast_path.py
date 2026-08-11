"""Market-maker fast path: build and sign orders locally.

The LocalIntentBuilder mirrors the on-chain EIP-712 schemas (proven by the
golden-vector test suite), so intents are built and signed in microseconds
with no I/O. The batched-market service's EIP-7702 leg is OPTIONAL: a
signed intent alone executes, so the hot path is local build+sign -> POST,
with zero API round-trips before submission. (Passing ``calldata=`` still
attaches the EIP-7702 leg if you want the server-side mechanism switch.)

With ``wait=False`` the SDK returns at ``MarketOrderAccepted``, but an
accepted order can still fail (declined fill, revert), so YOU own the
settlement check. Reconcile off the hot path with
``engine.batched_market.wait(tracking_id)`` (or ``.status()`` for a single,
seq-resumable poll). Prefer keeping ``wait=True`` and still seeing the order
journey (AttemptFailed diagnostics etc.) live? Pass ``on_event=`` — the SDK
settles as usual and calls your hook per lifecycle event; it also works on
``wait()`` below.

Beyond ``open_trade``/``close_trade`` the builder covers the whole intent
surface: ``open_trade_coin``/``close_trade_coin`` (coin-sized, pair with
AggregatorOrderType.*_WITH_COIN_EXPOSURE), ``increase_position[_coin]``,
``update_tp_sl`` and ``partial_tp_sl`` (both submitted to the core API
/price-triggers endpoint — what ``trade.update_tp_sl`` / ``partial_tp_sl``
do — not to batched-market), ``twap_open``/``twap_close``/``twap_cancel``,
``cancel_offchain_order``, ``delegate_req``, and the referral intents.
Prices are always caller-supplied; there is no feed lookup locally.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.errors import RelayError
from avantis_trader_sdk.types import AggregatorOrderType


async def main() -> None:
    async with AsyncAvantis() as client:
        builder = await client.local_intents()   # one-time meta bootstrap
        engine = client.engine
        eth = await client.markets.pair("ETH/USD")
        accepted: list[str] = []

        async def on_price(update) -> None:
            # build + sign locally (microseconds, no I/O)
            payload = builder.open_trade(
                trader=client.trade.trader,
                pair_index=eth.index,
                is_long=True,
                collateral_usdc=100,
                leverage=10,
                open_price=update.price,
                slippage_percent=0.3,
            )
            # submit the signed intent directly — the EIP-7702 leg is
            # optional, so no tx-builder call is needed on the hot path
            receipt = await engine.submit_intent_batch(
                payload, AggregatorOrderType.MARKET_OPEN, wait=False
            )
            print("accepted:", receipt.tracking_id, "at price", update.price)
            accepted.append(receipt.tracking_id)
            stream.stop()

        stream = client.lazer_price_stream([eth.lazer_feed.feed_id])
        await stream.run(on_price)

        # --- off the hot path: settle every accepted order ---
        # on_event logs the replayed journey live (AttemptFailed diagnostics
        # included) while wait() still settles the outcome
        for tracking_id in accepted:
            try:
                outcome = await engine.batched_market.wait(
                    tracking_id,
                    on_event=lambda ev: print(f"    seq={ev.seq} {ev.type}"),
                )
                print("executed:", outcome.tx_hash)
            except RelayError as exc:
                # MarketOrderCanceled: the protocol declined the fill
                # (e.g. price moved beyond slippage); nothing landed on-chain
                print("order", tracking_id, "declined:", exc)


if __name__ == "__main__":
    asyncio.run(main())
