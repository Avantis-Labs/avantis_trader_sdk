import asyncio
from avantis_trader_sdk import TraderClient


async def main():
    provider_url = "https://mainnet.base.org"
    client = TraderClient(provider_url)

    print("----- GETTING PAIR INFO -----")
    result = await client.pairs_cache.get_pairs_info()
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
    ) = await asyncio.gather(
        client.asset_parameters.get_oi_limits(),
        client.asset_parameters.get_oi(),
        client.asset_parameters.get_utilization(),
        client.asset_parameters.get_asset_skew(),
        client.fee_parameters.get_pair_spread(),
        client.fee_parameters.get_margin_fee(),
        client.category_parameters.get_oi_limits(),
        client.category_parameters.get_oi(),
        client.category_parameters.get_utilization(),
        client.category_parameters.get_category_skew(),
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


if __name__ == "__main__":
    asyncio.run(main())
