import asyncio
from avantis_trader_sdk import FeedClient, TraderClient


async def main():
    feed_client = FeedClient()

    # ============================================================
    # Method 1: get_latest_lazer_price - Get latest price by Lazer feed ID
    # ============================================================
    print("--- get_latest_lazer_price ---")

    # Lazer feed IDs: 1 = BTC/USD, 2 = ETH/USD, etc.
    price_data = await feed_client.get_latest_lazer_price([1, 2])

    for feed in price_data.price_feeds:
        print(f"Feed {feed.price_feed_id}: {feed.converted_price}")

    # ============================================================
    # Method 2: get_price_update_data - Get price + priceUpdateData by pair index
    # Use this when you need priceUpdateData for contract calls
    # ============================================================
    print("\n--- get_price_update_data ---")

    # pair_index: 0 = BTC/USD, 1 = ETH/USD, etc.
    btc_price_data = await feed_client.get_price_update_data(pair_index=0)
    print(f"BTC/USD: {btc_price_data.pro.price}")

    eth_price_data = await feed_client.get_price_update_data(pair_index=1)
    print(f"ETH/USD: {eth_price_data.pro.price}")

    # ============================================================
    # Using TraderClient to get Lazer feed IDs
    # ============================================================
    print("\n--- Get Lazer Feed IDs ---")

    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    btc_lazer_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index=0)
    eth_lazer_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index=1)

    print(f"BTC/USD Lazer Feed ID: {btc_lazer_id}")
    print(f"ETH/USD Lazer Feed ID: {eth_lazer_id}")


if __name__ == "__main__":
    asyncio.run(main())
