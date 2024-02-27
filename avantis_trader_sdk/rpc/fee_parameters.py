import asyncio
from .rpc_helpers import map_output_to_pairs
from ..types import MarginFee, PairSpread


class FeeParametersRPC:
    """
    This class provides methods to retrieve and calculate various fee parameters
    related to trades.
    """

    def __init__(self, client):
        """
        Constructor for the FeeParametersRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_margin_fee(self):
        """
        Retrieves the margin fee for all trading pairs.

        Returns:
            A MarginFee instance containing the margin fee for each trading pair.
        """
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        raw_data = await Multicall.functions.getMargins().call()
        decoded = self.client.utils["decoder"](Multicall, "getMargins", raw_data)

        for key, value in decoded.items():
            decoded[key] = [val * 30 * 60 / 10**10 for val in value]

        return MarginFee(
            base=map_output_to_pairs(pairs_info, decoded["rolloverFeePerBlockP"]),
            margin_long=map_output_to_pairs(
                pairs_info, decoded["rolloverFeePerBlockLong"]
            ),
            margin_short=map_output_to_pairs(
                pairs_info, decoded["rolloverFeePerBlockShort"]
            ),
        )

    async def get_pair_spread(self):
        """
        Retrieves the spread percentage % for all trading pairs.

        Returns:
            A PairSpread instance containing the spread % for each trading pair.
        """
        PairStorage = self.client.contracts.get("PairStorage")
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        calls = []
        for pair_index in range(len(pairs_info)):
            call_data = PairStorage.encodeABI(fn_name="pairSpreadP", args=[pair_index])
            calls.append((PairStorage.address, call_data))

        response = await Multicall.functions.aggregate(calls).call()
        decoded_response = [
            int.from_bytes(value, byteorder="big") / 10**10 for value in response[1]
        ]

        return PairSpread(spread=map_output_to_pairs(pairs_info, decoded_response))
