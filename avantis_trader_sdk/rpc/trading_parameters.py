from ..types import TradeInput, LossProtectionInfo
from typing import Optional


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

    async def get_loss_protection_tier(self, trade: TradeInput, is_pnl: bool = False):
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
                trade.positionSizeUSDC,
                trade.positionSizeUSDC,
                trade.openPrice,
                trade.buy,
                trade.leverage,
                trade.tp,
                trade.sl,
                trade.timestamp,
            ),
            is_pnl,
        ).call()
        return response

    async def get_loss_protection_percentage_by_tier(self, tier: int, pair_index: int):
        """
        Gets the loss protection tier.

        Args:
            tier: The tier.
            pair_index: The pair index.

        Returns:
            The loss protection percentage.
        """
        PairStorage = self.client.contracts.get("PairStorage")
        data = await PairStorage.functions.lossProtectionMultiplier(
            pair_index, tier
        ).call()
        return 100 - data

    async def get_loss_protection_percentage(self, trade: TradeInput):
        """
        Retrieves the loss protection percentage for a trade.

        Args:
            trade: A TradeInput instance containing the trade details.

        Returns:
            The loss protection percentage.
        """
        tier = await self.get_loss_protection_tier(trade)
        return await self.get_loss_protection_percentage_by_tier(tier, trade.pairIndex)

    async def get_loss_protection_for_trade_input(
        self, trade: TradeInput, opening_fee_usdc: Optional[float] = None
    ):
        """
        Retrieves the loss protection for a trade.

        Args:
            trade: A TradeInput instance containing the trade details.

        Returns:
            A LossProtectionInfo instance containing the loss protection percentage and amount in USDC.
        """
        loss_protection_percentage = await self.get_loss_protection_percentage(trade)

        if loss_protection_percentage == 0:
            return LossProtectionInfo(percentage=0, amount=0)

        if opening_fee_usdc is None:
            opening_fee_usdc = await self.client.fee_parameters.get_opening_fee(
                trade_input=trade
            )
        collateral_after_opening_fee = trade.positionSizeUSDC / 10**6 - opening_fee_usdc
        loss_protection_usdc = (
            collateral_after_opening_fee * loss_protection_percentage / 100
        )

        return LossProtectionInfo(
            percentage=loss_protection_percentage, amount=loss_protection_usdc
        )

    async def get_trade_referral_rebate_percentage(self, trader: Optional[str] = None):
        """
        Retrieves the trade referral rebate percentage for a trader.

        Args:
            trader (optional): The trader's wallet address.

        Returns:
            The trade referral rebate percentage.
        """
        Referral = self.client.contracts.get("Referral")

        if trader is None:
            trader = self.client.get_signer().get_ethereum_address()

        trader_referral_info = await Referral.functions.getTraderReferralInfo(
            trader
        ).call()
        if (
            len(trader_referral_info) == 0
            or trader_referral_info[1] == "0x0000000000000000000000000000000000000000"
        ):
            return 0
        referrer_tier = await Referral.functions.referrerTiers(
            trader_referral_info[1]
        ).call()  # trader_referral_info[1] is the referrer address
        tier_info = await self.client.read_contract(
            "Referral", "referralTiers", referrer_tier
        )
        discount_percentage = tier_info["feeDiscountPct"] / 100
        return discount_percentage
