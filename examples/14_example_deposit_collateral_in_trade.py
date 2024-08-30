import asyncio
import time

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import MarginUpdateType

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


async def main():
    # Initialize TraderClient
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    # Get opentrades
    (trades, _) = await trader_client.trade.get_trades(trader)
    print("Trades: ", trades)

    # Select first trade to update
    trade_to_update = trades[0]

    # Update trade
    deposit_transaction = await trader_client.trade.build_trade_margin_update_tx(
        trader=trader,
        pair_index=trade_to_update.trade.pair_index,
        trade_index=trade_to_update.trade.trade_index,
        margin_update_type=MarginUpdateType.DEPOSIT,  # Type of margin update (DEPOSIT or WITHDRAW)
        collateral_change=5,  # Amount of collateral to deposit or withdraw
    )

    receipt = await trader_client.sign_and_get_receipt(private_key, deposit_transaction)

    print(receipt)

    print("Trade updated successfully!")


if __name__ == "__main__":
    asyncio.run(main())
