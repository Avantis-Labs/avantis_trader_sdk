import asyncio
from avantis_trader_sdk import FeedClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


def ws_error_handler(e):
    print(f"Websocket error: {e}")
    # You can add your custom error handling logic here
    # For example, you can send an email to the dev team or restart the websocket connection


async def main():
    ws_url = "wss://hermes.pyth.network/ws"

    feed_client = FeedClient(
        ws_url, on_error=ws_error_handler, on_close=ws_error_handler
    )

    # You can use the feed id or pair name to register callbacks
    # Get the feed ID from https://pyth.network/developers/price-feed-ids
    feed_client.register_price_feed_callback(
        "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723",
        lambda data: print(data),
    )
    feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))

    await feed_client.listen_for_price_updates()

    # Optionally, you can run the websocket in a separate (background) task
    # asyncio.create_task(feed_client.listen_for_price_updates())


if __name__ == "__main__":
    asyncio.run(main())
