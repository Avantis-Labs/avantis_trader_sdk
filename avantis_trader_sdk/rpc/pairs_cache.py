from ..types import PairInfo
class PairsCache:
    def __init__(self, client):
        self.client = client
        self._pair_info_cache = {}

    async def get_pairs_info(self):
        if not self._pair_info_cache:
            Multicall = self.client.contracts.get('Multicall')
            PairStorage = self.client.contracts.get('PairStorage') 
            pairs_count = await self.get_pairs_count()
            
            calls = []
            for pair_index in range(pairs_count):          
                call_data = PairStorage.encodeABI(fn_name='pairs', args=[pair_index])
                calls.append((PairStorage.address, call_data))

            _, raw_data = await Multicall.functions.aggregate(calls).call()
            
            decoded_data = []
            for data in raw_data:
                decoded = self.client.utils['decoder'](PairStorage, 'pairs', data)
                decoded_data.append(PairInfo(**decoded))
            
            for index, pair_info in enumerate(decoded_data):
                self._pair_info_cache[index] = pair_info
            
        return self._pair_info_cache

    async def get_pairs_count(self):
        PairStorage = self.client.contracts.get('PairStorage')
        return await PairStorage.functions.pairsCount().call()
