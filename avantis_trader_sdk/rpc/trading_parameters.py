from ..types import TradeInput


class TradingParametersRPC:
    """
    The TradingParametersRPC class contains methods for retrieving trading parameters from the Avantis Protocol.
    """

    def __init__(self, client):
        """
        Constructor for the TradingParametersRPC class.

        Args:
            client: The TraderClient object.
        """
        self.client = client

    async def get_loss_protection_tier(self, trade: TradeInput):
        """
        Retrieves the loss protection tier for a trade. Read more about loss protection tiers here: https://docs.avantisfi.com/rewards/loss-protection

        Args:
            trade: A TradeInput instance containing the trade details.

        Returns:
            The loss protection tier as an integer.
        """
        PairInfos = self.client.contracts.get("PairInfos")

        response = await PairInfos.functions.lossProtectionTier(
            (
                trade.trader,
                trade.pairIndex,
                trade.index,
                trade.initialPosToken,
                trade.positionSizeUSDC,
                trade.openPrice,
                trade.buy,
                trade.leverage,
                trade.tp,
                trade.sl,
                trade.timestamp,
            )
        ).call()
        return response
