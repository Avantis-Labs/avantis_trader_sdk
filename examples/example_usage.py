import asyncio
from avantis_trader_sdk import TraderClient, FeedClient, __version__
from avantis_trader_sdk.types import TradeInput

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    print("----- GETTING PAIR INFO -----")
    result = await trader_client.pairs_cache.get_pairs_info()
    print(result)

    print("----- GETTING SNAPSHOT -----")
    result = await trader_client.snapshot.get_snapshot()
    print(result)

    # Optionally, you can convert the result to a JSON string
    # json_response = json.dumps(result, default=lambda x: x.__dict__)
    # print(json_response)

    print("----- GETTING DATA -----")
    (
        oi_limits,
        oi,
        utilization,
        skew,
        margin_fee,
        depth,
        group_oi_limits,
        group_oi,
        group_utilization,
        group_skew,
        price_impact_spread,
        skew_impact_spread,
        opening_price_impact_spread,
        opening_fee,
        loss_protection_tier,
    ) = await asyncio.gather(
        trader_client.asset_parameters.get_oi_limits(),
        trader_client.asset_parameters.get_oi(),
        trader_client.asset_parameters.get_utilization(),
        trader_client.asset_parameters.get_asset_skew(),
        trader_client.fee_parameters.get_margin_fee(),
        trader_client.asset_parameters.get_one_percent_depth(),
        trader_client.category_parameters.get_oi_limits(),
        trader_client.category_parameters.get_oi(),
        trader_client.category_parameters.get_utilization(),
        trader_client.category_parameters.get_category_skew(),
        trader_client.asset_parameters.get_price_impact_spread(1000.5),
        trader_client.asset_parameters.get_skew_impact_spread(1000.5),
        trader_client.asset_parameters.get_opening_price_impact_spread(
            "ETH/USD", 100.5, 3200, True
        ),
        trader_client.fee_parameters.get_opening_fee(1000),
        trader_client.trading_parameters.get_loss_protection_tier(
            TradeInput(
                pair_index=await trader_client.pairs_cache.get_pair_index("ARB/USD"),
                collateral=1,
                is_long=False,
                leverage=2,
            )
        ),
    )
    print("-------------------------")
    print("OI Limits:", oi_limits)
    print("-------------------------")
    print("OI:", oi)
    print("-------------------------")
    print("Utilization:", utilization)
    print("-------------------------")
    print("Skew:", skew)
    print("-------------------------")
    print("Margin Fee:", margin_fee)
    print("-------------------------")
    print("One Percent Depth:", depth)
    print("-------------------------")
    print("Group OI Limits:", group_oi_limits)
    print("-------------------------")
    print("Group OI:", group_oi)
    print("-------------------------")
    print("Group Utilization:", group_utilization)
    print("-------------------------")
    print("Group Skew:", group_skew)
    print("-------------------------")
    print("Price Impact Spread:", price_impact_spread)
    print("-------------------------")
    print("Skew Impact Spread:", skew_impact_spread)
    print("-------------------------")
    print("Opening Price Impact Spread:", opening_price_impact_spread)
    print("-------------------------")
    print("Opening Fee:", opening_fee)
    print("-------------------------")
    print("Loss Protection Tier:", loss_protection_tier)
    print("-------------------------")

    ws_url = "<YOUR WEBSOCKET URL>"

    feed_client = FeedClient(
        ws_url, on_error=ws_error_handler, on_close=ws_error_handler
    )

    # You can use the feed id or pair name to register callbacks
    feed_client.register_price_feed_callback(
        "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723",
        lambda data: print(data),
    )
    feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))

    await feed_client.listen_for_price_updates()

    # Optionally, you can run the websocket in a separate task
    # asyncio.create_task(feed_client.listen_for_price_updates())


def ws_error_handler(e):
    print(f"Websocket error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
