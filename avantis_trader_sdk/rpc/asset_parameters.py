from .rpc_helpers import map_output_to_pairs
from ..types import OpenInterest, OpenInterestLimits
class AssetParametersRPC:
    def __init__(self, client):
        self.client = client

    async def get_oi_limits(self):
        PairStorage = self.client.contracts.get('PairStorage')
        Multicall = self.client.contracts.get('Multicall')
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        calls = []
        for pair_index in range(len(pairs_info)):  
            call_data = PairStorage.encodeABI(fn_name='pairMaxOI', args=[pair_index])
            calls.append((PairStorage.address, call_data))

        response = await Multicall.functions.aggregate(calls).call()
        decoded_response = [int.from_bytes(value, byteorder='big') / 10 ** 6 for value in response[1]]
        
        return OpenInterestLimits(limits = map_output_to_pairs(pairs_info, decoded_response))
    
    
    async def get_oi(self):
        Multicall = self.client.contracts.get('Multicall')
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        raw_data = await Multicall.functions.getLongShortRatios().call()
        decoded = self.client.utils['decoder'](Multicall, 'getLongShortRatios', raw_data)
        return OpenInterest(longRatio= map_output_to_pairs(pairs_info, decoded["longRatio"]), shortRatio = map_output_to_pairs(pairs_info, decoded['shortRatio']))

    # def calculate_asset_utilization(self, pair_index):
    #     # ...

    # def calculate_asset_skew(self, pair_index):
    #     # ...
