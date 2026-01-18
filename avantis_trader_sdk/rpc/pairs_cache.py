from ..types import PairInfoWithData
from ..config import AVANTIS_SOCKET_API
import requests
from pydantic import ValidationError


class PairsCache:
    """
    This class provides methods to retrieve pairs information from the blockchain.
    """

    def __init__(
        self,
        client,
        socket_api: str = AVANTIS_SOCKET_API,
    ):
        """
        Constructor for the PairsCache class.

        Args:
            client: The TraderClient object.
        """
        self.client = client
        self.socket_api = socket_api

        self._pair_info_cache = {}
        self._group_indexes_cache = {}
        self._pair_mapping = {}

        self._pair_info_from_socket_cache = {}
        self._socket_info_cache = {}

    async def get_pairs_info(self, force_update=False):
        """
        Retrieves the pairs information from the blockchain. The information is cached and will be returned from the cache if it is available and force_update is False. This is to avoid unnecessary calls to the blockchain.

        Args:
            force_update: If True, the cache will be ignored and the information will be retrieved from the blockchain. Defaults to False.

        Returns:
            A dictionary containing the pairs information.
        """
        if not force_update and not self._pair_info_cache:
            Multicall = self.client.contracts.get("Multicall")
            PairStorage = self.client.contracts.get("PairStorage")
            pairs_count = await self.get_pairs_count()

            calls = []
            for pair_index in range(pairs_count):
                core_call_data = PairStorage.encodeABI(
                    fn_name="pairs", args=[pair_index]
                )
                pair_data_call_data = PairStorage.encodeABI(
                    fn_name="getPairData", args=[pair_index]
                )
                calls.extend(
                    [
                        (PairStorage.address, core_call_data),
                        (PairStorage.address, pair_data_call_data),
                    ]
                )

            _, raw_data = await Multicall.functions.aggregate(calls).call()

            decoded_data = []
            for i in range(0, len(raw_data), 2):
                pair_info = self.client.utils["decoder"](
                    PairStorage, "pairs", raw_data[i]
                )
                pair_data = self.client.utils["decoder"](
                    PairStorage, "getPairData", raw_data[i + 1]
                )
                pair_info.update(pair_data)
                decoded_data.append(PairInfoWithData(**pair_info))

            for index, pair_info in enumerate(decoded_data):
                if not pair_info.from_:
                    pair_info.from_ = f"DELISTED_{index}"
                    pair_info.to = f"DELISTED_{index}"
                self._pair_info_cache[index] = pair_info

            group_indexes = set([pair.group_index for pair in decoded_data])
            self._group_indexes_cache = group_indexes
            self._pair_mapping = {
                f"{info.from_}/{info.to}": index
                for index, info in self._pair_info_cache.items()
            }

        return self._pair_info_cache

    async def get_pair_info_from_socket(self, pair_index=None, use_cache=False):
        """
        Retrieves the pair information from the socket.
        """
        if not use_cache and self._pair_info_from_socket_cache:
            return self._pair_info_from_socket_cache[str(pair_index)]

        if not self.socket_api:
            raise ValueError("socket_api is not set")
        try:
            response = requests.get(self.socket_api)
            response.raise_for_status()

            result = response.json()
            self._socket_info_cache = result["data"]
            pairs = self._socket_info_cache["pairInfos"]
            self._pair_info_from_socket_cache = pairs
        except (requests.RequestException, ValidationError) as e:
            print(f"Error fetching pair feeds: {e}")
            return {}

        if pair_index is not None:
            return self._pair_info_from_socket_cache[str(pair_index)]
        return self._pair_info_from_socket_cache

    async def get_info_from_socket(self, force_update=False):
        """
        Retrieves the socket information.
        """
        if not force_update and self._socket_info_cache:
            return self._socket_info_cache

        if not self.socket_api:
            raise ValueError("socket_api is not set")
        try:
            response = requests.get(self.socket_api)
            response.raise_for_status()

            result = response.json()
            self._socket_info_cache = result["data"]
            self._pair_info_from_socket_cache = self._socket_info_cache["pairInfos"]
        except (requests.RequestException, ValidationError) as e:
            print(f"Error fetching pair feeds: {e}")
            return {}

        return self._socket_info_cache

    async def get_pairs_count(self):
        """
        Retrieves the number of pairs from the blockchain.

        Returns:
            The number of pairs as an integer.
        """
        PairStorage = self.client.contracts.get("PairStorage")
        return await PairStorage.functions.pairsCount().call()

    async def get_group_indexes(self):
        """
        Retrieves the group ids from the blockchain.

        Returns:
            The group ids as a set.
        """
        if not self._group_indexes_cache:
            await self.get_pairs_info()
        return self._group_indexes_cache

    async def get_pair_index(self, pair):
        """
        Retrieves the index of a pair from the blockchain.

        Args:
            pair: The pair to retrieve the index for. Expects a string in the format "from/to".

        Returns:
            The index of the pair as an integer.

        Raises:
            ValueError: If the pair is not found in the pairs information.
        """
        pairs_info = await self.get_pairs_info()
        for index, pair_info in pairs_info.items():
            if pair_info.from_ + "/" + pair_info.to == pair:
                return index
        raise ValueError(f"Pair {pair} not found in pairs info.")

    async def get_pair_name_from_index(self, pair_index):
        """
        Retrieves the pair name from the index.

        Args:
            pair_index: The pair index.

        Returns:
            The pair name.
        """
        pairs_info = await self.get_pairs_info()
        return pairs_info[pair_index].from_ + "/" + pairs_info[pair_index].to
