import asyncio
from avantis_trader_sdk import FeedClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


def error_handler(e):
    print(f"Stream error: {e}")
    # You can add your custom error handling logic here
    # For example, you can send an email to the dev team or restart the connection


async def main():
    feed_client = FeedClient(on_error=error_handler, on_close=error_handler)

    # Lazer feed IDs correspond to pair indexes:
    # 1 = BTC/USD, 2 = ETH/USD, etc.
    # You can get the Lazer feed ID using pairs_cache.get_lazer_feed_id(pair_index)
    lazer_feed_ids = [1, 2]  # BTC and ETH

    def handle_price_update(data):
        for feed in data.price_feeds:
            print(
                f"Feed {feed.price_feed_id}: {feed.converted_price} "
                f"(timestamp: {data.timestamp_ms}ms)"
            )

    await feed_client.listen_for_lazer_price_updates(
        lazer_feed_ids=lazer_feed_ids,
        callback=handle_price_update,
    )

    # Optionally, you can run the stream in a separate (background) task
    # asyncio.create_task(feed_client.listen_for_lazer_price_updates(...))


if __name__ == "__main__":
    asyncio.run(main())
