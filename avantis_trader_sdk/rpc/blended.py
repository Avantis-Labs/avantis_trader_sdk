import asyncio
from ..types import Utilization, Skew


class BlendedRPC:
    """
    This class provides methods to retrieve and calculate various blended parameters
    """

    def __init__(self, client):
        """
        Constructor for the BlendedRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_blended_utilization_ratio(self):
        """
        Retrieves the blended utilization ratio for all trading pairs.

        Returns:
            A Utilization instance containing the blended utilization ratio for each trading pair.
        """
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        asset_task = self.client.asset_parameters.get_utilization()
        category_task = self.client.category_parameters.get_utilization()

        asset_utilization, category_utilization = await asyncio.gather(
            asset_task, category_task
        )

        utilization = {}

        for _, pair in pairs_info.items():
            if str(pair.group_index) in category_utilization.utilization:
                utilization[pair.from_ + "/" + pair.to] = (
                    asset_utilization.utilization[pair.from_ + "/" + pair.to] * 25
                    + category_utilization.utilization[str(pair.group_index)] * 75
                ) / 100
            else:
                utilization[pair.from_ + "/" + pair.to] = 0

        return Utilization(utilization=utilization)

    async def get_blended_skew(self):
        """
        Retrieves the blended skew for all trading pairs.

        Returns:
            A Skew instance containing the blended skew for each trading pair.
        """
        pairs_info = await self.client.pairs_cache.get_pairs_info()
        asset_task = self.client.asset_parameters.get_asset_skew()
        category_task = self.client.category_parameters.get_category_skew()

        asset_skew, category_skew = await asyncio.gather(asset_task, category_task)

        skew = {}

        for _, pair in pairs_info.items():
            if str(pair.group_index) in category_skew.skew:
                skew[pair.from_ + "/" + pair.to] = (
                    asset_skew.skew[pair.from_ + "/" + pair.to] * 25
                    + category_skew.skew[str(pair.group_index)] * 75
                ) / 100
            else:
                skew[pair.from_ + "/" + pair.to] = 0

        return Skew(skew=skew)
