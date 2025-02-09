import asyncio
from avantis_trader_sdk import FeedClient, TraderClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():

    # This will initialize the feed client with the default pair fetcher which is the Avantis API
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

    # If you would like to use contracts to get pair feed info
    # You can use the trader client
    provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # This will initialize the feed client with the trader client's pair fetcher
    # This is useful if you want to use the pair info from the trader client's cache
    # You can also pass in a custom pair fetcher to the feed client
    feed_client = FeedClient(pair_fetcher=trader_client.pairs_cache.get_pairs_info)

    price_data = await feed_client.get_latest_price_updates(["ETH/USD", "BTC/USD"])
    print("ETH/USD: ", price_data.parsed[0])
    print("BTC/USD: ", price_data.parsed[1])


if __name__ == "__main__":
    asyncio.run(main())
