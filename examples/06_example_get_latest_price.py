import asyncio
from avantis_trader_sdk import FeedClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():
    feed_client = FeedClient()

    # You can use the feed id or pair name
    price_data = await feed_client.get_latest_price_updates(["ETH/USD", "BTC/USD"])
    print("ETH/USD: ", price_data.parsed[0])
    print("BTC/USD: ", price_data.parsed[1])

    # If you would like to use the feed ids instead
    # Get the feed ID from https://pyth.network/developers/price-feed-ids
    price_data = await feed_client.get_latest_price_updates(
        ["0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723"]
    )
    print("ETH/USD: ", price_data.parsed[0])


if __name__ == "__main__":
    asyncio.run(main())
