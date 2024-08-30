import asyncio
from avantis_trader_sdk import TraderClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    print("----- GETTING PAIR INFO -----")
    result = await trader_client.pairs_cache.get_pairs_info()
    print(result)

    print("----- PAIR CONSTANT SPREAD -----")
    for index in result:
        print(result[index].constant_spread_bps)

    constant_spread = await trader_client.fee_parameters.constant_spread_parameter()
    print(constant_spread)


if __name__ == "__main__":
    asyncio.run(main())
