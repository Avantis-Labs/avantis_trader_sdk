import asyncio
from .rpc_helpers import map_output_to_pairs
from ..types import OpenInterest, OpenInterestLimits, AssetUtilization, AssetSkew


class AssetParametersRPC:
    """
    This class provides methods to retrieve and calculate various asset parameters
    related to open interest, open interest limits, and asset utilization.
    """

    def __init__(self, client):
        """
        Constructor for the AssetParametersRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_oi_limits(self):
        """
        Retrieves the open interest limits for all trading pairs.

        Returns:
            An OpenInterestLimits instance containing the open interest limits
            for each trading pair.
        """
        PairStorage = self.client.contracts.get("PairStorage")
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        calls = []
        for pair_index in range(len(pairs_info)):
            call_data = PairStorage.encodeABI(fn_name="pairMaxOI", args=[pair_index])
            calls.append((PairStorage.address, call_data))

        response = await Multicall.functions.aggregate(calls).call()
        decoded_response = [
            int.from_bytes(value, byteorder="big") / 10**6 for value in response[1]
        ]

        return OpenInterestLimits(
            limits=map_output_to_pairs(pairs_info, decoded_response)
        )

    async def get_oi(self):
        """
        Retrieves the current open interest for all trading pairs.

        Returns:
            An OpenInterest instance containing the long and short open interest
            ratios for each trading pair.
        """
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        raw_data = await Multicall.functions.getLongShortRatios().call()
        decoded = self.client.utils["decoder"](
            Multicall, "getLongShortRatios", raw_data
        )
        return OpenInterest(
            longRatio=map_output_to_pairs(pairs_info, decoded["longRatio"]),
            shortRatio=map_output_to_pairs(pairs_info, decoded["shortRatio"]),
        )

    async def get_asset_utilization(self):
        """
        Calculates the asset utilization for all trading pairs.

        Returns:
            An AssetUtilization instance containing the asset utilization
            percentage % for each trading pair.
        """
        TradingStorage = self.client.contracts.get("TradingStorage")
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        calls = []
        for pair_index in range(len(pairs_info)):
            call_data = TradingStorage.encodeABI(fn_name="pairOI", args=[pair_index])
            calls.append((TradingStorage.address, call_data))

        oi_limits_task = self.get_oi_limits()
        aggregate_task = Multicall.functions.aggregate(calls).call()

        oi_limits, aggregate_response = await asyncio.gather(
            oi_limits_task, aggregate_task
        )

        utilization = {}
        for pair_index, (pair_data, oi_limit) in enumerate(
            zip(aggregate_response[1], oi_limits.limits.values())
        ):
            pair_name = f"{pairs_info[pair_index].from_}/{pairs_info[pair_index].to}"
            current_oi = int.from_bytes(pair_data, byteorder="big") / 10**6
            limit = oi_limit
            utilization[pair_name] = current_oi * 100 / limit if limit else 0

        return AssetUtilization(utilization=utilization)

    async def get_asset_skew(self):
        """
        Calculates the asset skew for all trading pairs.

        Returns:
            An AssetSkew instance containing the asset skew
            percentage % for each trading pair.
        """
        oi = await self.get_oi()

        skew = {}
        for pair, long_ratio in oi.longRatio.items():
            short_ratio = oi.shortRatio[pair]
            skew[pair] = (
                long_ratio * 100 / (long_ratio + short_ratio)
                if long_ratio + short_ratio
                else 0
            )

        return AssetSkew(skew=skew)
