import asyncio
import time

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

# Trader's private key and wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own private key and wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
private_key = "0xmyprivatekey"
trader = "0xmywalletaddress"


# We will first prepare trade input, then open a trade, get opened trade's info and finally close the trade
async def main():
    # Initialize TraderClient
    provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # Get trader's USDC balance
    balance = await trader_client.get_usdc_balance(trader)
    print(f"Balance of {trader} is {balance} USDC")

    # Get pair index of the pair. For example, ETH/USD
    pair_index_of_eth_usd = await trader_client.pairs_cache.get_pair_index("ETH/USD")

    # Prepare trade input
    trade_input = TradeInput(
        trader=trader,  # Trader's wallet address
        open_price=None,  # (Optional) Open price of the trade. If None then it will default to the current price
        pair_index=pair_index_of_eth_usd,  # Pair index
        collateral_in_trade=10,  # Amount of collateral in trade (in USDC)
        is_long=True,  # True for long, False for short
        leverage=25,  # Leverage for the trade
        index=0,  # This is the index of the trade for a pair (0 for the first trade, 1 for the second, etc.)
        tp=4000,  # Take profit price. Max allowed is 500% of open price.
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

    receipt = await trader_client.sign_and_get_receipt(private_key, open_transaction)

    print(receipt)
    print("Trade opened successfully!")

    # Wait for trade to be opened/executed
    time.sleep(30)

    # Get open and pending trades
    trades, pendingOpenLimitOrders = await trader_client.trade.get_trades(trader)
    print("Trades: ", trades)

    # Select first trade to close
    trade_to_close = trades[0]

    # Close trade
    close_transaction = await trader_client.trade.build_trade_close_tx(
        trader=trader,
        pair_index=trade_to_close.trade.pair_index,
        trade_index=trade_to_close.trade.trade_index,
        collateral_to_close=trade_to_close.trade.open_collateral
        / 2,  # Close half of the trade
    )

    receipt = await trader_client.sign_and_get_receipt(private_key, close_transaction)

    print(receipt)

    print("Trade closed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
