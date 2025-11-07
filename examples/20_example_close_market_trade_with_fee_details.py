import asyncio

from avantis_trader_sdk import TraderClient

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

    # Fetch open trades
    trades, _ = await trader_client.trade.get_trades(trader)
    if not trades:
        print("No trades found")
        return

    if len(trades) == 0:
        print("No trades found")
        return

    # Get referral rebate percentage
    rebate_pct = (
        await trader_client.trading_parameters.get_trade_referral_rebate_percentage(
            trader
        )
    )

    trade_data = trades[0]
    trade = trade_data.trade
    pair_index = trade.pair_index

    # Get pair info
    pair_info = await trader_client.pairs_cache.get_pair_info_from_socket(pair_index)

    # Get live price
    price_data = await trader_client.feed_client.get_latest_price_updates(
        [pair_info["feed"]["feedId"]]
    )
    current_price = price_data.parsed[0].converted_price
    print(f"\nCurrent price of {pair_index}: {current_price}")

    # Calculate PnL
    multiplier = 1 if trade.is_long else -1
    gross_pnl = (
        ((current_price - trade.open_price) * multiplier / trade.open_price)
        * trade.leverage
        * trade.open_collateral
    )
    print(f"Gross PnL: {gross_pnl}")

    # Loss protection
    loss_protection_pct = trade_data.additional_info.loss_protection_percentage
    loss_protection_amount = (
        (abs(gross_pnl) * loss_protection_pct / 100) if gross_pnl < 0 else 0
    )
    print(f"Loss protection amount: {loss_protection_amount}")

    # Fees and rebate
    closing_fee = (
        trade.open_collateral * trade.leverage * pair_info["closeFeeP"] / 100
    ) * (1 - rebate_pct / 100)
    print(f"Closing fee: {closing_fee}")

    margin_fee = trade_data.margin_fee
    net_pnl = gross_pnl - margin_fee - closing_fee + loss_protection_amount
    equity_value = trade.open_collateral + net_pnl

    print(f"Net PnL: {net_pnl}")
    print(f"Equity value: {equity_value}\n")

    # Close trade
    close_transaction = await trader_client.trade.build_trade_close_tx(
        pair_index=pair_index,
        trade_index=trade.trade_index,
        collateral_to_close=trade.open_collateral,  # Amount of collateral to close. Pass full amount to close the trade. Pass partial amount to partially close the trade.
        trader=trader,
    )

    receipt = await trader_client.sign_and_get_receipt(close_transaction)

    print(receipt)

    print("Trade closed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
