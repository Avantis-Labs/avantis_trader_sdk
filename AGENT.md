# Avantis Trader SDK - AI Agent Guide

> This document is designed to help AI agents understand and use the Avantis Trader SDK effectively. It contains all essential patterns, methods, and examples for building trading applications.

## Overview

The Avantis Trader SDK is a Python SDK for interacting with the Avantis Protocol - a perpetual trading platform on Base (Ethereum L2). It provides tools for:

- Opening/closing leveraged trades (long/short)
- Managing positions (TP/SL, margin)
- Real-time price feeds (Pyth Pro/Lazer)
- Reading market data and parameters
- Delegate trading (trading on behalf of another wallet)

**Chain**: Base Mainnet (Chain ID: 8453)
**Collateral**: USDC (6 decimals)

## Installation

```bash
pip install avantis_trader_sdk
```

## Core Components

### 1. TraderClient
Main client for all trading operations.

```python
from avantis_trader_sdk import TraderClient

provider_url = "https://mainnet.base.org"
trader_client = TraderClient(provider_url)
```

### 2. FeedClient
Client for price feeds and real-time data.

```python
from avantis_trader_sdk import FeedClient

feed_client = FeedClient()
```

### 3. Signers
For signing transactions:
- `LocalSigner` - Uses private key directly
- `KMSSigner` - Uses AWS KMS

```python
# Local signer (private key)
trader_client.set_local_signer("0xYOUR_PRIVATE_KEY")

# AWS KMS signer
trader_client.set_aws_kms_signer("kms-key-id", region_name="us-east-1")
```

---

## Essential Patterns

### Pattern 1: Basic Setup
```python
import asyncio
from avantis_trader_sdk import TraderClient

async def main():
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)
    trader_client.set_local_signer("0xYOUR_PRIVATE_KEY")
    
    trader = trader_client.get_signer().get_ethereum_address()
    print(f"Trader address: {trader}")

asyncio.run(main())
```

### Pattern 2: Check Balances & Allowances
```python
# Get USDC balance
balance = await trader_client.get_usdc_balance(trader)

# Get ETH balance (for gas)
eth_balance = await trader_client.get_balance(trader)

# Check USDC allowance for trading
allowance = await trader_client.get_usdc_allowance_for_trading(trader)

# Approve USDC if needed
if allowance < amount_needed:
    await trader_client.approve_usdc_for_trading(amount_needed)
```

### Pattern 3: Build & Sign Transactions
```python
# Build transaction
transaction = await trader_client.trade.build_trade_open_tx(...)

# Sign and send
receipt = await trader_client.sign_and_get_receipt(transaction)
```

---

## Trading Operations

### Get Pair Index
Trading pairs are identified by index, not name.

```python
# Get pair index from name
pair_index = await trader_client.pairs_cache.get_pair_index("ETH/USD")
pair_index = await trader_client.pairs_cache.get_pair_index("BTC/USD")

# Get pair name from index
pair_name = await trader_client.pairs_cache.get_pair_name_from_index(0)  # "BTC/USD"
```

**Common Pair Indexes:**
- 0: BTC/USD
- 1: ETH/USD

### Open a Market Trade
```python
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

# Prepare trade input
trade_input = TradeInput(
    trader=trader,              # Wallet address
    pair_index=1,               # 1 = ETH/USD
    collateral_in_trade=100,    # 100 USDC collateral
    is_long=True,               # True = long, False = short
    leverage=25,                # 25x leverage
    tp=4000,                    # Take profit price
    sl=2800,                    # Stop loss price (0 = no stop loss)
)

# Build and sign transaction
transaction = await trader_client.trade.build_trade_open_tx(
    trade_input=trade_input,
    trade_input_order_type=TradeInputOrderType.MARKET,
    slippage_percentage=1,  # 1% slippage
)
receipt = await trader_client.sign_and_get_receipt(transaction)
```

### Open a Limit Order
```python
trade_input = TradeInput(
    trader=trader,
    pair_index=1,
    collateral_in_trade=100,
    is_long=True,
    leverage=25,
    open_price=3000,            # Limit price
    tp=4000,
    sl=2800,
)

transaction = await trader_client.trade.build_trade_open_tx(
    trade_input=trade_input,
    trade_input_order_type=TradeInputOrderType.LIMIT,
    slippage_percentage=1,
)
```

### Get Open Trades
```python
# Get all trades and pending limit orders for a trader
trades, pending_orders = await trader_client.trade.get_trades(trader)

# Each trade has:
for trade in trades:
    print(f"Pair: {trade.trade.pair_index}")
    print(f"Index: {trade.trade.trade_index}")
    print(f"Collateral: {trade.trade.collateral_in_trade} USDC")
    print(f"Leverage: {trade.trade.leverage}x")
    print(f"Long: {trade.trade.is_long}")
    print(f"Open Price: {trade.trade.open_price}")
    print(f"TP: {trade.trade.tp}")
    print(f"SL: {trade.trade.sl}")
    print(f"Liquidation Price: {trade.liquidation_price}")
```

### Close a Trade
```python
# Close full position
close_tx = await trader_client.trade.build_trade_close_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    collateral_to_close=trade.trade.collateral_in_trade,  # Full amount
    trader=trader,
)
receipt = await trader_client.sign_and_get_receipt(close_tx)

# Partial close (close half)
partial_close_tx = await trader_client.trade.build_trade_close_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    collateral_to_close=trade.trade.collateral_in_trade / 2,
    trader=trader,
)
```

### Update Take Profit / Stop Loss
```python
update_tx = await trader_client.trade.build_trade_tp_sl_update_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    take_profit_price=4500,  # New TP
    stop_loss_price=2900,    # New SL (0 to remove)
    trader=trader,
)
receipt = await trader_client.sign_and_get_receipt(update_tx)
```

### Update Margin (Deposit/Withdraw Collateral)
```python
from avantis_trader_sdk.types import MarginUpdateType

# Deposit more collateral
deposit_tx = await trader_client.trade.build_trade_margin_update_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    margin_update_type=MarginUpdateType.DEPOSIT,
    collateral_change=50,  # Add 50 USDC
    trader=trader,
)

# Withdraw collateral
withdraw_tx = await trader_client.trade.build_trade_margin_update_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    margin_update_type=MarginUpdateType.WITHDRAW,
    collateral_change=20,  # Remove 20 USDC
    trader=trader,
)
```

### Cancel Limit Order
```python
cancel_tx = await trader_client.trade.build_order_cancel_tx(
    pair_index=order.pair_index,
    trade_index=order.trade_index,
    trader=trader,
)
receipt = await trader_client.sign_and_get_receipt(cancel_tx)
```

---

## Price Feeds

### Get Latest Price (One-time)
```python
from avantis_trader_sdk import FeedClient

feed_client = FeedClient()

# Get price data for a pair by index
price_data = await feed_client.get_price_update_data(pair_index=0)  # BTC
print(f"BTC Price: {price_data.pro.price}")

price_data = await feed_client.get_price_update_data(pair_index=1)  # ETH
print(f"ETH Price: {price_data.pro.price}")
```

### Real-time Price Streaming (SSE)
```python
from avantis_trader_sdk import FeedClient

feed_client = FeedClient()

def handle_price_update(data):
    for feed in data.price_feeds:
        print(f"Feed {feed.price_feed_id}: {feed.converted_price}")

# Subscribe to Lazer feed IDs (same as pair indexes)
await feed_client.listen_for_lazer_price_updates(
    lazer_feed_ids=[0, 1],  # BTC, ETH
    callback=handle_price_update,
)
```

### Get Lazer Feed ID
```python
# Get Lazer feed ID for a pair
lazer_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index=0)
```

---

## Delegate Trading

Allows one wallet to trade on behalf of another.

### Set Up Delegation
```python
# Main wallet sets delegate
delegate_address = "0xDELEGATE_ADDRESS"
set_delegate_tx = await trader_client.trade.build_set_delegate_tx(
    delegate=delegate_address,
    trader=main_wallet_address,
)
receipt = await trader_client.sign_and_get_receipt(set_delegate_tx)
```

### Check Current Delegate
```python
delegate = await trader_client.trade.get_delegate(trader=main_wallet_address)
# Returns "0x0000..." if no delegate set
```

### Trade as Delegate
```python
# Delegate wallet opens trade for main wallet
trader_client.set_local_signer(DELEGATE_PRIVATE_KEY)

# Use _delegate versions of methods
open_tx = await trader_client.trade.build_trade_open_tx_delegate(
    trade_input=trade_input,  # trade_input.trader = main wallet
    trade_input_order_type=TradeInputOrderType.MARKET,
    slippage_percentage=1,
)

close_tx = await trader_client.trade.build_trade_close_tx_delegate(...)
update_tp_sl_tx = await trader_client.trade.build_trade_tp_sl_update_tx_delegate(...)
update_margin_tx = await trader_client.trade.build_trade_margin_update_tx_delegate(...)
```

### Remove Delegation
```python
remove_tx = await trader_client.trade.build_remove_delegate_tx(trader=main_wallet_address)
receipt = await trader_client.sign_and_get_receipt(remove_tx)
```

---

## Market Data

### Get All Pairs Info
```python
pairs_info = await trader_client.pairs_cache.get_pairs_info()
for index, pair in pairs_info.items():
    print(f"{index}: {pair.from_}/{pair.to}")
```

### Get Pair Count
```python
count = await trader_client.pairs_cache.get_pairs_count()
```

### Get Trading Fees
```python
# Get opening fee for a trade
opening_fee = await trader_client.fee_parameters.get_new_trade_opening_fee(trade_input)
print(f"Opening fee: {opening_fee} USDC")
```

### Get Loss Protection
```python
loss_protection = await trader_client.trading_parameters.get_loss_protection_for_trade_input(
    trade_input,
    opening_fee_usdc=opening_fee
)
print(f"Loss protection: {loss_protection.percentage}%")
print(f"Max rebate: ${loss_protection.amount}")
```

### Get Market Snapshot
```python
snapshot = await trader_client.snapshot.get_snapshot()
# Contains open interest, utilization, skew for all groups/pairs
```

---

## Types Reference

### TradeInput
```python
TradeInput(
    trader: str,              # Wallet address
    pair_index: int,          # Trading pair index
    collateral_in_trade: float,  # USDC collateral amount
    is_long: bool,            # True=long, False=short
    leverage: int,            # Leverage multiplier
    tp: float,                # Take profit price
    sl: float,                # Stop loss price (0=none)
    open_price: float = None, # For limit orders
    index: int = 0,           # Trade index
)
```

### TradeInputOrderType
```python
TradeInputOrderType.MARKET          # Market order
TradeInputOrderType.LIMIT           # Limit order
TradeInputOrderType.STOP_LIMIT      # Stop limit order
TradeInputOrderType.MARKET_ZERO_FEE # Zero fee market order
```

### MarginUpdateType
```python
MarginUpdateType.DEPOSIT   # Add collateral
MarginUpdateType.WITHDRAW  # Remove collateral
```

### TradeExtendedResponse (from get_trades)
```python
trade.trade.trader              # Wallet address
trade.trade.pair_index          # Pair index
trade.trade.trade_index         # Trade index
trade.trade.collateral_in_trade # Current collateral
trade.trade.open_collateral     # Initial collateral
trade.trade.open_price          # Entry price
trade.trade.is_long             # Long/short
trade.trade.leverage            # Leverage
trade.trade.tp                  # Take profit
trade.trade.sl                  # Stop loss
trade.trade.timestamp           # Open timestamp
trade.liquidation_price         # Liquidation price
trade.margin_fee                # Accumulated margin fee
```

---

## Complete Example: Open and Close Trade

```python
import asyncio
from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

async def main():
    # Setup
    trader_client = TraderClient("https://mainnet.base.org")
    trader_client.set_local_signer("0xYOUR_PRIVATE_KEY")
    trader = trader_client.get_signer().get_ethereum_address()
    
    # Check and approve USDC
    allowance = await trader_client.get_usdc_allowance_for_trading(trader)
    if allowance < 100:
        await trader_client.approve_usdc_for_trading(100)
    
    # Open long ETH position
    trade_input = TradeInput(
        trader=trader,
        pair_index=1,  # ETH/USD
        collateral_in_trade=100,
        is_long=True,
        leverage=10,
        tp=5000,
        sl=2500,
    )
    
    open_tx = await trader_client.trade.build_trade_open_tx(
        trade_input, TradeInputOrderType.MARKET, slippage_percentage=1
    )
    await trader_client.sign_and_get_receipt(open_tx)
    print("Trade opened!")
    
    # Wait for execution
    await asyncio.sleep(30)
    
    # Get trades and close
    trades, _ = await trader_client.trade.get_trades(trader)
    if trades:
        trade = trades[0]
        close_tx = await trader_client.trade.build_trade_close_tx(
            pair_index=trade.trade.pair_index,
            trade_index=trade.trade.trade_index,
            collateral_to_close=trade.trade.collateral_in_trade,
            trader=trader,
        )
        await trader_client.sign_and_get_receipt(close_tx)
        print("Trade closed!")

asyncio.run(main())
```

---

## Error Handling

```python
try:
    receipt = await trader_client.sign_and_get_receipt(transaction)
except Exception as e:
    print(f"Transaction failed: {e}")
```

---

## Important Notes

1. **Always check USDC allowance** before opening trades
2. **Trade indexes are per-pair** - each pair has independent trade indexes 0, 1, 2...
3. **Take profit cannot be 0** - it's required for all trades
4. **Stop loss can be 0** - means no stop loss
5. **Prices use 10 decimals** internally but SDK accepts human-readable values
6. **Collateral uses 6 decimals** (USDC) but SDK accepts human-readable values
7. **Execution fees** are paid in ETH - ensure wallet has ETH for gas
8. **Delegate trading** - USDC allowance must be set by the main wallet, not the delegate

---

## Resources

- [Avantis Documentation](https://docs.avantisfi.com/)
- [SDK Examples](https://github.com/Avantis-Labs/avantis_trader_sdk/tree/main/examples)
- [SDK Documentation](https://sdk.avantisfi.com/)
- [SDK API Reference](https://sdk.avantisfi.com/api_reference.html)

