import asyncio
from avantis_trader_sdk import TraderClient

async def main():
    provider_url = 'https://mainnet.base.org'
    client = TraderClient(provider_url)

    print('----- GETTING PAIR INFO -----')
    result = await client.pairs_cache.get_pairs_info()
    print(result)
    
    print('----- GETTING ASSET OI LIMITS AND OI -----')
    oi_limits, oi = await asyncio.gather(
        client.asset_parameters.get_oi_limits(),
        client.asset_parameters.get_oi()
    )
    print('OI Limits:', oi_limits)
    print('OI:', oi)
    

if __name__ == "__main__":
    asyncio.run(main())