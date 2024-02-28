import asyncio
from .rpc_helpers import map_output_to_pairs
from ..types import (
    OpenInterest,
    OpenInterestLimits,
    Utilization,
    Skew,
    PriceImpactSpread,
)
from typing import Optional


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
            long=map_output_to_pairs(pairs_info, decoded["longRatio"]),
            short=map_output_to_pairs(pairs_info, decoded["shortRatio"]),
        )

    async def get_utilization(self):
        """
        Calculates the asset utilization for all trading pairs.

        Returns:
            A Utilization instance containing the asset utilization
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

        return Utilization(utilization=utilization)

    async def get_asset_skew(self):
        """
        Calculates the asset skew for all trading pairs.

        Returns:
            An Skew instance containing the asset skew
            percentage % for each trading pair.
        """
        oi = await self.get_oi()

        skew = {}
        for pair, long_ratio in oi.long.items():
            short_ratio = oi.short[pair]
            skew[pair] = (
                long_ratio * 100 / (long_ratio + short_ratio)
                if long_ratio + short_ratio
                else 0
            )

        return Skew(skew=skew)

    async def get_price_impact_spread(
        self, position_size: int = 0, is_long: Optional[bool] = None, pair: str = None
    ):
        """
        Retrieves the price impact spread for all trading pairs.

        Args:
            is_long: A boolean indicating if the position is a buy or sell. Defaults to None. If None, the price impact spread for both buy and sell will be returned.
            position_size: The size of the position (collateral * leverage). Supports upto 6 decimals. Defaults to 0.
            pair: The trading pair for which the price impact spread is to be calculated. Defaults to None. If None, the price impact spread for all trading pairs will be returned.

        Returns:
            A PriceImpactSpread instance containing the price impact spread for each trading pair.
        """
        position_size = int(position_size * 10**6)

        Multicall = self.client.contracts.get("Multicall")

        calls = []
        response = None

        if pair is not None:
            pair_index = await self.client.pairs_cache.get_pair_index(pair)
            PairInfos = self.client.contracts.get("PairInfos")
            if is_long is None:
                calls.extend(
                    [
                        (
                            PairInfos.address,
                            PairInfos.encodeABI(
                                fn_name="getPriceImpactSpread",
                                args=[pair_index, True, position_size],
                            ),
                        ),
                        (
                            PairInfos.address,
                            PairInfos.encodeABI(
                                fn_name="getPriceImpactSpread",
                                args=[pair_index, False, position_size],
                            ),
                        ),
                    ]
                )
            else:
                response = await PairInfos.functions.getPriceImpactSpread(
                    pair_index, is_long, position_size
                ).call()
        else:
            pairs_info = await self.client.pairs_cache.get_pairs_info()
            PairInfos = self.client.contracts.get("PairInfos")
            for pair_index in range(len(pairs_info)):
                if is_long is None:
                    calls.extend(
                        [
                            (
                                PairInfos.address,
                                PairInfos.encodeABI(
                                    fn_name="getPriceImpactSpread",
                                    args=[pair_index, True, position_size],
                                ),
                            ),
                            (
                                PairInfos.address,
                                PairInfos.encodeABI(
                                    fn_name="getPriceImpactSpread",
                                    args=[pair_index, False, position_size],
                                ),
                            ),
                        ]
                    )
                else:
                    calls.append(
                        (
                            PairInfos.address,
                            PairInfos.encodeABI(
                                fn_name="getPriceImpactSpread",
                                args=[pair_index, is_long, position_size],
                            ),
                        )
                    )

        if response is None:
            response = await Multicall.functions.aggregate(calls).call()
            if is_long is None:
                decoded_response = [
                    int.from_bytes(value, byteorder="big") / 10**10
                    for value in response[1]
                ]
                if pair is None:
                    return PriceImpactSpread(
                        long=map_output_to_pairs(pairs_info, decoded_response[::2]),
                        short=map_output_to_pairs(pairs_info, decoded_response[1::2]),
                    )
                else:
                    return PriceImpactSpread(
                        long={pair: decoded_response[0]},
                        short={pair: decoded_response[1]},
                    )
            elif is_long:
                decoded_response = map_output_to_pairs(
                    pairs_info,
                    [
                        int.from_bytes(value, byteorder="big") / 10**10
                        for value in buy_response[1]
                    ],
                )
                return PriceImpactSpread(long=decoded_response)
            else:
                decoded_response = map_output_to_pairs(
                    pairs_info,
                    [
                        int.from_bytes(value, byteorder="big") / 10**10
                        for value in sell_response[1]
                    ],
                )
                return PriceImpactSpread(short=decoded_response)
        elif is_long:
            return PriceImpactSpread(long={pair: response / 10**10})
        else:
            return PriceImpactSpread(short={pair: response / 10**10})
