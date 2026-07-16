"""Market-maker fast path: zero HTTP round-trips to build and sign orders.

The LocalIntentBuilder mirrors the on-chain EIP-712 schemas (proven by the
golden-vector test suite), so the hot path is: local build -> local sign ->
relayer queue. Combine with the SSE price stream for quote-to-order latency
bounded only by the relayer POST.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.types import AggregatorOrderType


async def main() -> None:
    async with AsyncAvantis() as client:
        builder = await client.local_intents()   # one-time meta bootstrap
        engine = client.engine
        eth = await client.markets.pair("ETH/USD")

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
            stream.stop()

        stream = client.lazer_price_stream([eth.lazer_feed.feed_id])
        await stream.run(on_price)


if __name__ == "__main__":
    asyncio.run(main())
