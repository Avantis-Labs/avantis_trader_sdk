from ..types import PairInfo
class PairsCache:
    """
    This class provides methods to retrieve pairs information from the blockchain.
    """
    
    def __init__(self, client):
        """
        Constructor for the PairsCache class.
        
        Args:
            client: The TraderClient object.
        """
        self.client = client
        self._pair_info_cache = {}

    async def get_pairs_info(self, force_update=False):
        """
        Retrieves the pairs information from the blockchain. The information is cached and will be returned from the cache if it is available and force_update is False. This is to avoid unnecessary calls to the blockchain.

        Args:
            force_update: If True, the cache will be ignored and the information will be retrieved from the blockchain. Defaults to False.

        Returns:
            A dictionary containing the pairs information.
        """
        if not force_update and not self._pair_info_cache:
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
        """
        Retrieves the number of pairs from the blockchain.

        Returns:
            The number of pairs as an integer.
        """
        PairStorage = self.client.contracts.get('PairStorage')
        return await PairStorage.functions.pairsCount().call()
