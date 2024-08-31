import asyncio
from ..types import OpenInterest, OpenInterestLimits, Utilization, Skew


class CategoryParametersRPC:
    """
    This class provides methods to retrieve and calculate various category parameters
    related to open interest, open interest limits, and category utilization.
    """

    def __init__(self, client):
        """
        Constructor for the CategoryParametersRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_oi_limits(self):
        """
        Retrieves the open interest limits for all categories.

        Returns:
            An OpenInterestLimits instance containing the open interest limits. The index of the list
            corresponds to the category index.
        """
        PairStorage = self.client.contracts.get("PairStorage")
        Multicall = self.client.contracts.get("Multicall")
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        group_indexes = await self.client.pairs_cache.get_group_indexes()

        pair_indexes = []
        for group_index in group_indexes:
            for _, pair in pairs_info.items():
                if pair.group_index == group_index:
                    pair_indexes.append(pair.fee_index)
                    break

        calls = []
        for pair_index in pair_indexes:
            call_data = PairStorage.encodeABI(fn_name="groupMaxOI", args=[pair_index])
            calls.append((PairStorage.address, call_data))

        response = await Multicall.functions.aggregate(calls).call()
        decoded_response = [
            int.from_bytes(value, byteorder="big") / 10**6 for value in response[1]
        ]
        decoded_response = {
            str(group_index): value
            for group_index, value in zip(group_indexes, decoded_response)
        }
        return OpenInterestLimits(limits=decoded_response)

    async def get_oi(self):
        """
        Retrieves the current open interest for all categories.

        Returns:
            An OpenInterest instance containing the long and short open interest
        """
        PairStorage = self.client.contracts.get("PairStorage")
        Multicall = self.client.contracts.get("Multicall")
        group_indexes = await self.client.pairs_cache.get_group_indexes()

        long_calls = []
        short_calls = []
        for group_index in group_indexes:
            call_data = PairStorage.encodeABI(fn_name="groupOIs", args=[group_index, 0])
            long_calls.append((PairStorage.address, call_data))

            call_data = PairStorage.encodeABI(fn_name="groupOIs", args=[group_index, 1])
            short_calls.append((PairStorage.address, call_data))

        long_task = Multicall.functions.aggregate(long_calls).call()
        short_task = Multicall.functions.aggregate(short_calls).call()

        long_response, short_response = await asyncio.gather(long_task, short_task)

        long_response = [
            int.from_bytes(value, byteorder="big") / 10**6 for value in long_response[1]
        ]
        short_response = [
            int.from_bytes(value, byteorder="big") / 10**6
            for value in short_response[1]
        ]

        long_response = {
            str(group_index): value
            for group_index, value in zip(group_indexes, long_response)
        }
        short_response = {
            str(group_index): value
            for group_index, value in zip(group_indexes, short_response)
        }

        return OpenInterest(long=long_response, short=short_response)

    # async def get_oi(self):
    #     """
    #     Retrieves the current open interest for all categories.

    #     Returns:
    #         An OpenInterest instance containing the long and short open interest
    #     """
    #     pair_info = await self.client.pairs_cache.get_pairs_info()
    #     pair_oi = await self.client.asset_parameters.get_oi()
    #     group_indexes = await self.client.pairs_cache.get_group_indexes()

    #     long_response = {}
    #     short_response = {}

    #     for group_index in group_indexes:
    #         long_response[group_index] = 0
    #         short_response[group_index] = 0

    #     for pair_key, oi in pair_oi.long.items():
    #         if pair_key in self.client.pairs_cache._pair_mapping:
    #             pair_index = self.client.pairs_cache._pair_mapping[pair_key]
    #             pair = pair_info[pair_index]
    #             group_index = pair.group_index
    #             long_response[group_index] += oi
    #             # Assuming pair_oi.short has the same keys as pair_oi.long
    #             short_response[group_index] += pair_oi.short[pair_key]
    #         else:
    #             print(f"Warning: {pair_key} not found in pair_info")

    #     return OpenInterest(long=long_response, short=short_response)

    # async def get_utilization(self):
    #     """
    #     Calculates the category utilization for all categories.

    #     Returns:
    #         A Utilization instance containing the category utilization
    #         percentage % for each category.
    #     """
    #     PairStorage = self.client.contracts.get("PairStorage")
    #     Multicall = self.client.contracts.get("Multicall")
    #     pairs_info = await self.client.pairs_cache.get_pairs_info()
    #     group_indexes = await self.client.pairs_cache.get_group_indexes()

    #     pair_indexes = []
    #     for group_index in group_indexes:
    #         for _, pair in pairs_info.items():
    #             if pair.group_index == group_index:
    #                 pair_indexes.append(pair.fee_index)
    #                 break

    #     calls = []
    #     for pair_index in pair_indexes:
    #         call_data = PairStorage.encodeABI(fn_name="groupOI", args=[pair_index])
    #         calls.append((PairStorage.address, call_data))

    #     oi_limits_task = self.get_oi_limits()
    #     aggregate_task = Multicall.functions.aggregate(calls).call()

    #     oi_limits, aggregate_response = await asyncio.gather(
    #         oi_limits_task, aggregate_task
    #     )

    #     utilization = {}

    #     for pair_index in range(len(aggregate_response[1])):
    #         current_oi = (
    #             int.from_bytes(aggregate_response[1][pair_index], byteorder="big")
    #             / 10**6
    #         )
    #         limit = oi_limits.limits[str(pair_index)]
    #         print(current_oi, limit)
    #         utilization[pair_index] = current_oi * 100 / limit if limit else 0

    #     return Utilization(utilization=utilization)

    async def get_utilization(self):
        """
        Calculates the category utilization for all categories.

        Returns:
            A Utilization instance containing the category utilization
            absolute value for each category.
        """
        oi_limits_task = self.get_oi_limits()
        oi_task = self.get_oi()

        oi_limits, oi = await asyncio.gather(oi_limits_task, oi_task)

        utilization = {}

        for group_index in range(len(oi.long)):
            current_oi = oi.long[str(group_index)] + oi.short[str(group_index)]
            limit = oi_limits.limits[str(group_index)]
            utilization[str(group_index)] = current_oi / limit if limit else 0

        return Utilization(utilization=utilization)

    async def get_category_skew(self):
        """
        Calculates the category skew for all categories.

        Returns:
            An Skew instance containing the category skew
            absolute value for each category.
        """
        oi = await self.get_oi()

        skew = {}
        for group_index, long_ratio in oi.long.items():
            short_ratio = oi.short[group_index]
            skew[group_index] = (
                long_ratio / (long_ratio + short_ratio)
                if long_ratio + short_ratio
                else 0
            )

        return Skew(skew=skew)
