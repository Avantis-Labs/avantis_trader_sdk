from avantis_trader_sdk import TraderClient

provider_url = '<YOUR RPC HERE>'
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
