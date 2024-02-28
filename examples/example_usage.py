import asyncio
from avantis_trader_sdk import TraderClient, FeedClient


async def main():
    provider_url = "https://mainnet.base.org"
    ws_url = "wss://<YOUR-WEBSOCKET-ENDPOINT>"
    trader_client = TraderClient(provider_url)
    feed_client = FeedClient(
        ws_url, on_error=ws_error_handler, on_close=ws_error_handler
    )

    print("----- GETTING PAIR INFO -----")
    result = await trader_client.pairs_cache.get_pairs_info()
    print(result)

    print("----- GETTING DATA -----")
    (
        oi_limits,
        oi,
        utilization,
        skew,
        spread,
        margin_fee,
        group_oi_limits,
        group_oi,
        group_utilization,
        group_skew,
        price_impact_spread,
    ) = await asyncio.gather(
        trader_client.asset_parameters.get_oi_limits(),
        trader_client.asset_parameters.get_oi(),
        trader_client.asset_parameters.get_utilization(),
        trader_client.asset_parameters.get_asset_skew(),
        trader_client.fee_parameters.get_pair_spread(),
        trader_client.fee_parameters.get_margin_fee(),
        trader_client.category_parameters.get_oi_limits(),
        trader_client.category_parameters.get_oi(),
        trader_client.category_parameters.get_utilization(),
        trader_client.category_parameters.get_category_skew(),
        trader_client.asset_parameters.get_price_impact_spread(1000.5),
    )
    print("OI Limits:", oi_limits)
    print("OI:", oi)
    print("Utilization:", utilization)
    print("Skew:", skew)
    print("Spread:", spread)
    print("Margin Fee:", margin_fee)
    print("Group OI Limits:", group_oi_limits)
    print("Group OI:", group_oi)
    print("Group Utilization:", group_utilization)
    print("Group Skew:", group_skew)
    print("Price Impact Spread:", price_impact_spread)

    feed_client.register_price_feed_callback(
        "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723",
        lambda data: print(data),
    )
    feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))

    await feed_client.listen_for_price_updates()
    # asyncio.create_task(feed_client.listen_for_price_updates())


def ws_error_handler(e):
    print(f"Websocket error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
