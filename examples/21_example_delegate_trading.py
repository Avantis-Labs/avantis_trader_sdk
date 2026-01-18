import asyncio
import time

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType, MarginUpdateType

# This example demonstrates delegate trading functionality.
# A delegate can perform all trade-related actions on behalf of the main wallet.
#
# Use cases:
# - Trading bots operating on behalf of users
# - Automated trading systems
# - Multi-sig setups where one wallet authorizes another
#
# Important: Each wallet can have at most one delegate (1:1 relationship)

# Main wallet's private key (the wallet that owns the trades)
# ---------------------------------------
# Change to your own private key
# ---------------------------------------
main_wallet_private_key = "0xmain_wallet_private_key"

# Delegate wallet's private key (the wallet that will execute trades)
# ---------------------------------------
# Change to your own private key
# ---------------------------------------
delegate_wallet_private_key = "0xdelegate_wallet_private_key"


async def main():
    provider_url = "https://mainnet.base.org"

    # We need two client instances:
    # 1. Main wallet client - to set up delegation and approve USDC
    # 2. Delegate client - to execute trades on behalf of main wallet

    # Initialize main wallet client
    main_client = TraderClient(provider_url)
    main_client.set_local_signer(main_wallet_private_key)
    main_wallet = main_client.get_signer().get_ethereum_address()
    print(f"Main wallet address: {main_wallet}")

    # Initialize delegate client
    delegate_client = TraderClient(provider_url)
    delegate_client.set_local_signer(delegate_wallet_private_key)
    delegate_wallet = delegate_client.get_signer().get_ethereum_address()
    print(f"Delegate wallet address: {delegate_wallet}")

    # =========================================
    # STEP 1: Set up delegation (if not already set)
    # =========================================
    print("\n--- Step 1: Setting up delegation ---")

    current_delegate = await main_client.trade.get_delegate(main_wallet)
    print(f"Current delegate for main wallet: {current_delegate}")

    zero_address = "0x0000000000000000000000000000000000000000"
    if current_delegate.lower() != delegate_wallet.lower():
        if current_delegate != zero_address:
            print(f"Removing existing delegate: {current_delegate}")
            remove_tx = await main_client.trade.build_remove_delegate_tx()
            receipt = await main_client.sign_and_get_receipt(remove_tx)
            print(f"Removed delegate. Tx: {receipt['transactionHash'].hex()}")

        print(f"Setting {delegate_wallet} as delegate...")
        set_delegate_tx = await main_client.trade.build_set_delegate_tx(delegate_wallet)
        receipt = await main_client.sign_and_get_receipt(set_delegate_tx)
        print(f"Delegate set successfully. Tx: {receipt['transactionHash'].hex()}")

        # Verify delegation
        current_delegate = await main_client.trade.get_delegate(main_wallet)
        print(f"Verified delegate: {current_delegate}")
    else:
        print("Delegate already set correctly.")

    # =========================================
    # STEP 2: Ensure USDC allowance (from main wallet)
    # =========================================
    print("\n--- Step 2: Checking USDC allowance ---")

    amount_of_collateral = 10
    allowance = await main_client.get_usdc_allowance_for_trading(main_wallet)
    print(f"Current USDC allowance: {allowance}")

    if allowance < amount_of_collateral:
        print(f"Approving {amount_of_collateral} USDC for trading...")
        await main_client.approve_usdc_for_trading(amount_of_collateral)
        allowance = await main_client.get_usdc_allowance_for_trading(main_wallet)
        print(f"New allowance: {allowance} USDC")

    # =========================================
    # STEP 3: Open trade via delegate
    # =========================================
    print("\n--- Step 3: Opening trade via delegate ---")

    pair_index = await delegate_client.pairs_cache.get_pair_index("ETH/USD")

    trade_input = TradeInput(
        trader=main_wallet,  # Trade belongs to main wallet
        pair_index=pair_index,
        collateral_in_trade=amount_of_collateral,
        is_long=True,
        leverage=25,
        index=0,
        tp=5000,
        sl=0,
    )

    # Delegate builds and signs the transaction, but trade belongs to main wallet
    open_tx = await delegate_client.trade.build_trade_open_tx_delegate(
        trade_input,
        TradeInputOrderType.MARKET,
        slippage_percentage=1,
    )
    receipt = await delegate_client.sign_and_get_receipt(open_tx)
    print(f"Trade opened via delegate. Tx: {receipt['transactionHash'].hex()}")

    # Wait for trade execution
    print("Waiting for trade execution...")
    time.sleep(30)

    # =========================================
    # STEP 4: Get trades (belongs to main wallet)
    # =========================================
    print("\n--- Step 4: Fetching trades ---")

    trades, _ = await delegate_client.trade.get_trades(main_wallet)
    print(f"Main wallet has {len(trades)} open trades")

    if not trades:
        print("No trades found. Exiting.")
        return

    trade = trades[0]
    print(
        f"Trade: pair_index={trade.trade.pair_index}, index={trade.trade.trade_index}"
    )
    print(f"  Collateral: {trade.trade.open_collateral}")
    print(f"  Leverage: {trade.trade.leverage}x")
    print(f"  TP: {trade.trade.tp}, SL: {trade.trade.sl}")

    # =========================================
    # STEP 5: Update TP/SL via delegate
    # =========================================
    print("\n--- Step 5: Updating TP/SL via delegate ---")

    update_tx = await delegate_client.trade.build_trade_tp_sl_update_tx_delegate(
        pair_index=trade.trade.pair_index,
        trade_index=trade.trade.trade_index,
        take_profit_price=6000,
        stop_loss_price=3000,
        trader=main_wallet,
    )
    receipt = await delegate_client.sign_and_get_receipt(update_tx)
    print(f"TP/SL updated via delegate. Tx: {receipt['transactionHash'].hex()}")

    # Wait for update
    time.sleep(10)

    # =========================================
    # STEP 6: Update margin via delegate (deposit)
    # =========================================
    print("\n--- Step 6: Depositing margin via delegate ---")

    # First ensure additional allowance from main wallet
    additional_collateral = 5
    current_allowance = await main_client.get_usdc_allowance_for_trading(main_wallet)
    if current_allowance < additional_collateral:
        await main_client.approve_usdc_for_trading(additional_collateral + 100)

    margin_tx = await delegate_client.trade.build_trade_margin_update_tx_delegate(
        pair_index=trade.trade.pair_index,
        trade_index=trade.trade.trade_index,
        margin_update_type=MarginUpdateType.DEPOSIT,
        collateral_change=additional_collateral,
        trader=main_wallet,
    )
    receipt = await delegate_client.sign_and_get_receipt(margin_tx)
    print(f"Margin deposited via delegate. Tx: {receipt['transactionHash'].hex()}")

    # Wait for update
    time.sleep(10)

    # =========================================
    # STEP 7: Close trade via delegate
    # =========================================
    print("\n--- Step 7: Closing trade via delegate ---")

    # Refresh trade info
    trades, _ = await delegate_client.trade.get_trades(main_wallet)
    trade = trades[0]

    close_tx = await delegate_client.trade.build_trade_close_tx_delegate(
        pair_index=trade.trade.pair_index,
        trade_index=trade.trade.trade_index,
        collateral_to_close=trade.trade.open_collateral,  # Close full position
        trader=main_wallet,
    )
    receipt = await delegate_client.sign_and_get_receipt(close_tx)
    print(f"Trade closed via delegate. Tx: {receipt['transactionHash'].hex()}")

    print("\n--- Delegate trading example completed! ---")

    # =========================================
    # OPTIONAL: Remove delegation
    # =========================================
    # Uncomment to remove the delegate after the example
    # print("\n--- Removing delegation ---")
    # remove_tx = await main_client.trade.build_remove_delegate_tx()
    # receipt = await main_client.sign_and_get_receipt(remove_tx)
    # print(f"Delegate removed. Tx: {receipt['transactionHash'].hex()}")


if __name__ == "__main__":
    asyncio.run(main())
