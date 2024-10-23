import asyncio

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

# Trader's private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
private_key = "0xmyprivatekey"


# We will first prepare trade input, then open a trade, get opened trade's info and finally close the trade
async def main():
    # Initialize TraderClient
    provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # Set local signer
    trader_client.set_local_signer(
        private_key
    )  # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

    trader = trader_client.get_signer().get_ethereum_address()

    # Get trader's USDC balance
    balance = await trader_client.get_usdc_balance(trader)
    print(f"Balance of {trader} is {balance} USDC")

    # Check allowance of USDC
    allowance = await trader_client.get_usdc_allowance_for_trading(trader)
    print(f"Allowance of {trader} is {allowance} USDC")

    amount_of_collateral = 10

    if allowance < amount_of_collateral:
        print(
            f"Allowance of {trader} is less than {amount_of_collateral} USDC. Approving..."
        )
        await trader_client.approve_usdc_for_trading(amount_of_collateral)
        allowance = await trader_client.get_usdc_allowance_for_trading(trader)
        print(f"New allowance of {trader} is {allowance} USDC")

    # Get pair index of the pair. For example, ETH/USD
    pair_index_of_eth_usd = await trader_client.pairs_cache.get_pair_index("ETH/USD")

    # Prepare trade input
    trade_input = TradeInput(
        trader=trader,  # Trader's wallet address
        open_price=None,  # (Optional) Open price of the trade. Current price in case of Market orders. If None then it will default to the current price
        pair_index=pair_index_of_eth_usd,  # Pair index
        collateral_in_trade=amount_of_collateral,  # Amount of collateral in trade (in USDC)
        is_long=True,  # True for long, False for short
        leverage=25,  # Leverage for the trade
        index=0,  # This is the index of the trade for a pair (0 for the first trade, 1 for the second, etc.)
        tp=4000.5,  # Take profit price. Max allowed is 500% of open price.
        sl=0,  # Stop loss price
        timestamp=0,  # Timestamp of the trade. 0 for now
    )

    # ---------------------------------------------
    # Get opening fee data
    # Read more: https://docs.avantisfi.com/trading/trading-fees/crypto#dynamic-opening-fee-0.04-0.1-position-size
    opening_fee_usdc = await trader_client.fee_parameters.get_opening_fee(
        trade_input=trade_input
    )
    print(f"Opening fee for this trade: {opening_fee_usdc} USDC")

    # Get loss protection percentage
    # Read more: https://docs.avantisfi.com/rewards/loss-protection
    loss_protection_info = (
        await trader_client.trading_parameters.get_loss_protection_for_trade_input(
            trade_input, opening_fee_usdc=opening_fee_usdc
        )
    )  # Opening fee is optional (it will be calculated if not provided)
    print(
        f"Loss protection percentage for this trade (Read more: https://docs.avantisfi.com/rewards/loss-protection): {loss_protection_info.percentage}%"
    )
    print(
        f"You'll receive up to ${loss_protection_info.amount} as a loss rebate if the trade goes against you."
    )
    # ---------------------------------------------

    # 1% slippage
    slippage_percentage = 1

    # Order type for the trade (MARKET or LIMIT or STOP_LIMIT)
    trade_input_order_type = TradeInputOrderType.MARKET

    # Open trade
    open_transaction = await trader_client.trade.build_trade_open_tx(
        trade_input, trade_input_order_type, slippage_percentage
    )

    receipt = await trader_client.sign_and_get_receipt(open_transaction)

    print(receipt)
    print("Trade opened successfully!")


if __name__ == "__main__":
    asyncio.run(main())
