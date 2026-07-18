"""Real-time streams: prices (SSE), pair data (Socket.IO), order events (Pusher)."""

import asyncio

from avantis_trader_sdk_v2 import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        eth = await client.markets.pair("ETH/USD")
        btc = await client.markets.pair("BTC/USD")

        # --- price stream (Pyth Lazer via feed-v3 SSE) ---
        prices = client.lazer_price_stream(
            [eth.lazer_feed.feed_id, btc.lazer_feed.feed_id]
        )

        count = 0

        async def on_price(update) -> None:
            nonlocal count
            print(f"feed {update.feed_id}: {update.price:.2f}")
            count += 1
            if count >= 10:
                prices.stop()

        await prices.run(on_price)

        # --- pair data stream (funding/OI/spread updates) ---
        # needs the extra: pip install 'avantis-trader-sdk-v2[streams]'
        # pairdata = client.pair_data_stream()
        # await pairdata.run(lambda payload: print("pairs updated:", list(payload)[:3]))

        # --- order execution events (Pusher; fires when the operator fills
        #     / cancels one of YOUR orders — idle otherwise) ---
        # orders = client.order_event_stream()
        # await orders.run(lambda ev: print(ev.event, ev.data))


if __name__ == "__main__":
    asyncio.run(main())
