import asyncio
from avantis_trader_sdk import FeedClient, TraderClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():
    # Initialize the feed client
    feed_client = FeedClient()

    # Get price update data for a pair by index
    # pair_index: 0 = BTC/USD, 1 = ETH/USD, etc.

    # Get BTC price data
    btc_price_data = await feed_client.get_price_update_data(pair_index=0)
    print(f"BTC/USD: {btc_price_data.pro.price}")

    # Get ETH price data
    eth_price_data = await feed_client.get_price_update_data(pair_index=1)
    print(f"ETH/USD: {eth_price_data.pro.price}")

    # ============================================================
    # Using TraderClient with pair cache
    # ============================================================
    print("\n--- Using TraderClient Example ---")

    # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453
    # or use a dedicated node (Alchemy, Infura, etc.)
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    # Get Lazer feed ID for a pair (useful for real-time streaming)
    lazer_feed_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index=0)
    print(f"BTC/USD Lazer Feed ID: {lazer_feed_id}")

    lazer_feed_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index=1)
    print(f"ETH/USD Lazer Feed ID: {lazer_feed_id}")


if __name__ == "__main__":
    asyncio.run(main())
