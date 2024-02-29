import asyncio
from .rpc_helpers import map_output_to_pairs
from ..types import MarginFee, PairSpread, Fee, TradeInput
from typing import Optional


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

    async def get_opening_fee(
        self, position_size: int = 0, is_long: Optional[bool] = None, pair: str = None
    ):
        """
        Retrieves the opening fee for all trading pairs.

        Args:
            is_long: A boolean indicating if the position is a buy or sell. Defaults to None. If None, the opening fee for both buy and sell will be returned.
            position_size: The size of the position (collateral * leverage). Supports upto 6 decimals. Defaults to 0.
            pair: The trading pair for which the opening fee is to be calculated. Defaults to None. If None, the opening fee for all trading pairs will be returned.

        Returns:
            A Fee instance containing the skew impact Fee for each trading pair.
        """
        position_size = int(position_size * 10**6)

        Multicall = self.client.contracts.get("Multicall")

        calls = []
        response = None

        if pair is not None:
            pair_index = await self.client.pairs_cache.get_pair_index(pair)
            PriceAggregator = self.client.contracts.get("PriceAggregator")
            if is_long is None:
                calls.extend(
                    [
                        (
                            PriceAggregator.address,
                            PriceAggregator.encodeABI(
                                fn_name="openFeeP",
                                args=[pair_index, position_size, True],
                            ),
                        ),
                        (
                            PriceAggregator.address,
                            PriceAggregator.encodeABI(
                                fn_name="openFeeP",
                                args=[pair_index, position_size, False],
                            ),
                        ),
                    ]
                )
            else:
                response = await PriceAggregator.functions.openFeeP(
                    pair_index, position_size, is_long
                ).call()
        else:
            pairs_info = await self.client.pairs_cache.get_pairs_info()
            PriceAggregator = self.client.contracts.get("PriceAggregator")
            for pair_index in range(len(pairs_info)):
                if is_long is None:
                    calls.extend(
                        [
                            (
                                PriceAggregator.address,
                                PriceAggregator.encodeABI(
                                    fn_name="openFeeP",
                                    args=[pair_index, position_size, True],
                                ),
                            ),
                            (
                                PriceAggregator.address,
                                PriceAggregator.encodeABI(
                                    fn_name="openFeeP",
                                    args=[pair_index, position_size, False],
                                ),
                            ),
                        ]
                    )
                else:
                    calls.append(
                        (
                            PriceAggregator.address,
                            PriceAggregator.encodeABI(
                                fn_name="openFeeP",
                                args=[pair_index, position_size, is_long],
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
                    return Fee(
                        long=map_output_to_pairs(pairs_info, decoded_response[::2]),
                        short=map_output_to_pairs(pairs_info, decoded_response[1::2]),
                    )
                else:
                    return Fee(
                        long={pair: decoded_response[0]},
                        short={pair: decoded_response[1]},
                    )
            elif is_long:
                decoded_response = map_output_to_pairs(
                    pairs_info,
                    [
                        int.from_bytes(value, byteorder="big") / 10**10
                        for value in response[1]
                    ],
                )
                return Fee(long=decoded_response)
            else:
                decoded_response = map_output_to_pairs(
                    pairs_info,
                    [
                        int.from_bytes(value, byteorder="big") / 10**10
                        for value in response[1]
                    ],
                )
                return Fee(short=decoded_response)
        elif is_long:
            return Fee(long={pair: response / 10**10})
        else:
            return Fee(short={pair: response / 10**10})
