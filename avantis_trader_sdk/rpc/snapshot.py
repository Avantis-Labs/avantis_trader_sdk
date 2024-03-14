import asyncio
from ..types import Snapshot, PairInfoExtended


class SnapshotRPC:
    """
    This class provides methods to retrieve and calculate various parameters as snapshot
    """

    def __init__(self, client):
        """
        Constructor for the SnapshotRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_snapshot(self):
        """
        Retrieves the blended utilization ratio for all trading pairs.

        Returns:
            A Utilization instance containing the blended utilization ratio for each trading pair.
        """
        pairs = await self.client.pairs_cache.get_pairs_info()
        (
            oi_limits,
            oi,
            utilization,
            skew,
            spread,
            margin_fee,
            group_oi_limits,
            group_oi,
            group_utilization,
            group_skew,
        ) = await asyncio.gather(
            self.client.asset_parameters.get_oi_limits(),
            self.client.asset_parameters.get_oi(),
            self.client.asset_parameters.get_utilization(),
            self.client.asset_parameters.get_asset_skew(),
            self.client.fee_parameters.constant_spread_parameter(),
            self.client.fee_parameters.get_margin_fee(),
            self.client.category_parameters.get_oi_limits(),
            self.client.category_parameters.get_oi(),
            self.client.category_parameters.get_utilization(),
            self.client.category_parameters.get_category_skew(),
        )

        response = {}

        for pairIndex in pairs:
            pair = pairs[pairIndex]
            key = pair.from_ + "/" + pair.to
            pair = pair.__dict__
            pair["open_interest_limit"] = oi_limits.limits[key]
            pair["open_interest"] = {"long": oi.long[key], "short": oi.short[key]}
            pair["utilization"] = utilization.utilization[key]
            pair["skew"] = skew.skew[key]
            pair["spread"] = spread.spread[key]
            pair["margin_fee"] = {
                "hourly_base_fee_parameter": margin_fee.hourly_base_fee_parameter[key],
                "margin_long": margin_fee.margin_long[key],
                "margin_short": margin_fee.margin_short[key],
            }
            pair["from"] = pair.pop("from_")
            pairs[pairIndex] = PairInfoExtended(**pair)

        for group_index in group_oi_limits.limits:
            response[group_index] = {
                "open_interest_limit": group_oi_limits.limits[group_index],
                "open_interest": {
                    "long": group_oi.long[group_index],
                    "short": group_oi.short[group_index],
                },
                "utilization": group_utilization.utilization[group_index],
                "skew": group_skew.skew[group_index],
                "pairs": {
                    pair.from_ + "/" + pair.to: pair
                    for _, pair in pairs.items()
                    if pair.groupIndex == int(group_index)
                },
            }

        return Snapshot(categories=response)

        # for group_index in group_indexes:

        # response = Snapshot(categories = group_indexes)

        # pairs_info = await self.client.pairs_cache.get_pairs_info()
        # print(response)
