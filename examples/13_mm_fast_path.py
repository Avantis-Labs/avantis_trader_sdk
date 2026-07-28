"""Market-maker fast path: zero HTTP round-trips to build and sign orders.

The LocalIntentBuilder mirrors the on-chain EIP-712 schemas (proven by the
golden-vector test suite), so the hot path is: local build -> local sign ->
relayer queue. Combine with the SSE price stream for quote-to-order latency
bounded only by the relayer POST.

With ``wait=False`` the SDK returns as soon as the relayer accepts the
request — but a queued relay can still fail (on-chain revert, relayer
timeout), so YOU own the settlement check. Reconcile off the hot path with
``engine.relayer.wait(request_id)`` (or ``.status()`` for a single poll).

Beyond ``open_trade``/``close_trade`` the builder covers the whole intent
surface: ``open_trade_coin``/``close_trade_coin`` (coin-sized, pair with
AggregatorOrderType.*_WITH_COIN_EXPOSURE), ``increase_position[_coin]``,
``update_tp_sl``, ``partial_tp_sl`` (stored off-chain, not relayed),
``twap_open``/``twap_close``, ``delegate_req``, and the referral intents.
Prices are always caller-supplied — there is no feed lookup locally.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.errors import RelayError, RelayTimeoutError
from avantis_trader_sdk.types import AggregatorOrderType


async def main() -> None:
    async with AsyncAvantis() as client:
        builder = await client.local_intents()   # one-time meta bootstrap
        engine = client.engine
        eth = await client.markets.pair("ETH/USD")
        queued: list[str] = []

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
            # submit as a relayer batch (no calldata round-trip)
            receipt = await engine.submit_intent_batch(
                payload, AggregatorOrderType.MARKET_OPEN, wait=False
            )
            print("queued:", receipt.request_id, "at price", update.price)
            queued.append(receipt.request_id)
            stream.stop()

        stream = client.lazer_price_stream([eth.lazer_feed.feed_id])
        await stream.run(on_price)

        # --- off the hot path: settle every queued relay ---
        for request_id in queued:
            try:
                status = await engine.relayer.wait(request_id)
                print("mined:", status.tx_hash)
            except RelayTimeoutError:
                # not settled within the polling window — it may still land,
                # so check positions before assuming failure
                print("relay", request_id, "still pending; check positions")
            except RelayError as exc:
                # rejected by the relayer or reverted on-chain
                print("relay", request_id, "failed:", exc)


if __name__ == "__main__":
    asyncio.run(main())
