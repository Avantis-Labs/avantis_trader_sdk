from avantis_trader_sdk import TraderClient

provider_url = 'https://base-mainnet.g.alchemy.com/v2/CHctvvwxXGqOKG_GbRN9yw4hyw217PX_'
client = TraderClient(provider_url)

print('----- GETTING PAIR INFO -----')
result = client.pairs_cache.get_pairs_info()
print(result)

print('----- GETTING ASSET OI LIMITS -----')
result = client.asset_parameters.get_oi_limits()
print(result)

print('----- GETTING ASSET OI -----')
result = client.asset_parameters.get_oi()
print(result)
