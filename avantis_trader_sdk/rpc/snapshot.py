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
            A Snapshot instance containing several pair and group related parameters.
        """
        pairs = await self.client.pairs_cache.get_pairs_info()

        # Fetch all the required data in parallel
        (
            oi_limits,
            oi,
            utilization,
            skew,
            price_impact_spread,
            skew_impact_spread,
            margin_fee,
            depth,
            group_oi_limits,
            group_oi,
            group_utilization,
            group_skew,
            opening_fee,
        ) = await asyncio.gather(
            self.client.asset_parameters.get_oi_limits(),
            self.client.asset_parameters.get_oi(),
            self.client.asset_parameters.get_utilization(),
            self.client.asset_parameters.get_asset_skew(),
            self.client.asset_parameters.get_price_impact_spread(1000),
            self.client.asset_parameters.get_skew_impact_spread(1000),
            self.client.fee_parameters.get_margin_fee(),
            self.client.asset_parameters.get_one_percent_depth(),
            self.client.category_parameters.get_oi_limits(),
            self.client.category_parameters.get_oi(),
            self.client.category_parameters.get_utilization(),
            self.client.category_parameters.get_category_skew(),
            self.client.fee_parameters.get_opening_fee(1000),
        )

        response = {}

        for pairIndex in pairs:
            pair = pairs[pairIndex]
            key = pair.from_ + "/" + pair.to
            pair = pair.__dict__

            pair["asset_open_interest_limit"] = oi_limits.limits[key]
            pair["asset_open_interest"] = {"long": oi.long[key], "short": oi.short[key]}
            pair["asset_utilization"] = utilization.utilization[key]
            pair["asset_skew"] = skew.skew[key]

            pair["blended_utilization"] = (
                utilization.utilization[key] * 0.25
                + group_utilization.utilization[str(pair["group_index"])] * 0.75
            )
            pair["blended_skew"] = (
                skew.skew[key] * 0.25 + group_skew.skew[str(pair["group_index"])] * 0.75
            )

            pair["margin_fee"] = {
                "hourly_base_fee_parameter": margin_fee.hourly_base_fee_parameter[key],
                "hourly_margin_fee_long_bps": margin_fee.hourly_margin_fee_long_bps[
                    key
                ],
                "hourly_margin_fee_short_bps": margin_fee.hourly_margin_fee_short_bps[
                    key
                ],
            }
            pair["one_percent_depth"] = {
                "above": depth.above[key],
                "below": depth.below[key],
            }

            pair["new_1k_long_opening_fee_bps"] = opening_fee.long[key]
            pair["new_1k_short_opening_fee_bps"] = opening_fee.short[key]

            pair["new_1k_long_opening_spread_bps"] = round(
                pair["constant_spread_bps"]
                + price_impact_spread.long[key]
                + skew_impact_spread.long[key],
                4,
            )
            pair["new_1k_short_opening_spread_bps"] = round(
                pair["constant_spread_bps"]
                + price_impact_spread.short[key]
                + skew_impact_spread.short[key],
                4,
            )

            pair["price_impact_spread_long_bps"] = round(
                price_impact_spread.long[key], 4
            )
            pair["price_impact_spread_short_bps"] = round(
                price_impact_spread.short[key], 4
            )

            pair["skew_impact_spread_long_bps"] = round(skew_impact_spread.long[key], 4)
            pair["skew_impact_spread_short_bps"] = round(
                skew_impact_spread.short[key], 4
            )

            pair["priceImpactMultiplier"] = pair.pop("price_impact_parameter") * 10**10
            pair["skewImpactMultiplier"] = pair.pop("skew_impact_parameter") * 10**10
            pair["spreadP"] = pair.pop("constant_spread_bps") * 10**10 / 100
            pairs[pairIndex] = PairInfoExtended(**pair)

        for group_index in group_oi_limits.limits:
            response[group_index] = {
                "group_open_interest_limit": group_oi_limits.limits[group_index],
                "group_open_interest": {
                    "long": group_oi.long[group_index],
                    "short": group_oi.short[group_index],
                },
                "group_utilization": group_utilization.utilization[group_index],
                "group_skew": group_skew.skew[group_index],
                "pairs": {
                    pair.from_ + "/" + pair.to: pair
                    for _, pair in pairs.items()
                    if pair.group_index == int(group_index)
                },
            }

        return Snapshot(groups=response)
