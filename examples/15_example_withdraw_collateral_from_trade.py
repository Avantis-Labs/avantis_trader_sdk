import asyncio

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import MarginUpdateType

# Trader's private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
private_key = "0xmyprivatekey"


async def main():
    # Initialize TraderClient
    provider_url = "https://sepolia.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # Set local signer
    trader_client.set_local_signer(
        private_key
    )  # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

    trader = trader_client.get_signer().get_ethereum_address()

    # Get opentrades
    (trades,) = await trader_client.trade.get_trades(trader)
    print("Trades: ", trades)

    # Select first trade to update
    trade_to_update = trades[0]

    # ---------------------------------------------
    # NOTE: Any accrued margin fee on the trade will
    # be deducted from the remaining collateral
    # ---------------------------------------------

    # Update trade
    deposit_transaction = await trader_client.trade.build_trade_margin_update_tx(
        pair_index=trade_to_update.trade.pair_index,
        trade_index=trade_to_update.trade.trade_index,
        margin_update_type=MarginUpdateType.WITHDRAW,  # Type of margin update (DEPOSIT or WITHDRAW)
        collateral_change=10,  # Amount of collateral to deposit or withdraw
        trader=trader,
    )

    receipt = await trader_client.sign_and_get_receipt(deposit_transaction)

    print(receipt)

    print("Trade updated successfully!")


if __name__ == "__main__":
    asyncio.run(main())
