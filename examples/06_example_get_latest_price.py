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


if __name__ == "__main__":
    asyncio.run(main())
