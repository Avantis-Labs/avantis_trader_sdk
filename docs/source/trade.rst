Trade Operations
================

The Avantis Trader SDK provides powerful methods for managing trades, including opening, closing, canceling, and editing trades. This section will guide you through each operation with clear examples to help you interact with the Avantis contracts effectively.

Opening a Trade
---------------

The ``open_trade`` method allows you to open a new trade. Follow the steps below to open a trade using the SDK.

**Example Usage:**

.. code-block:: python

   import asyncio
   from avantis_trader_sdk import TraderClient, TradeInput, TradeInputOrderType

   private_key = "0xmyprivatekey"

   async def main():
       # Initialize TraderClient
       provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
       trader_client = TraderClient(provider_url)

       # Set local signer
       trader_client.set_local_signer(private_key) # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

       trader = trader_client.get_signer().get_ethereum_address()

       # Check allowance of USDC
       allowance = await trader_client.get_usdc_allowance_for_trading(trader)
       print(f"Allowance of {trader} is {allowance} USDC")
      
       amount_of_collateral = 10

       if allowance < amount_of_collateral:
        print(f"Allowance of {trader} is less than {amount_of_collateral} USDC. Approving...")
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
       )
       print(
           f"Loss protection percentage for this trade: {loss_protection_info.percentage}%"
       )
       print(
           f"You'll receive up to ${loss_protection_info.amount} as a loss rebate if the trade goes against you."
       )
       # ---------------------------------------------

       # 1% slippage
       slippage_percentage = 1

       # Order type for the trade (MARKET, LIMIT, or STOP_LIMIT)
       trade_input_order_type = TradeInputOrderType.MARKET

       # Open trade
       open_transaction = await trader_client.trade.build_trade_open_tx(
           trade_input, trade_input_order_type, slippage_percentage
       )

       receipt = await trader_client.sign_and_get_receipt(open_transaction)

       print(receipt)
       print("Trade opened successfully!")

   # Run the example
   asyncio.run(main())

**Steps Explained:**

1. **Initialize the TraderClient:**
   - Connect to the Base Mainnet using a provider URL.

2. **Get Pair Index:**
   - Retrieve the index of the trading pair (e.g., ETH/USD).

3. **Prepare Trade Input:**
   - Define the trade details such as trader's address, collateral, leverage, and more.

4. **Calculate Fees and Protection:**
   - Retrieve the opening fee and loss protection information for the trade.

5. **Set Slippage and Order Type:**
   - Define slippage tolerance and choose the order type (MARKET, LIMIT, STOP_LIMIT).

6. **Build and Send Transaction:**
   - Construct the transaction to open the trade and send it to the blockchain.

**Notes:**

- Ensure that the parameters such as `trade_input`, `slippage_percentage`, and `trade_input_order_type` are correctly set.
- An execution fee is charged in ETH to execute the close trade transaction. This fee is required to cover the gas costs on the Ethereum network. This is automatically calculated.
- Refer to the Avantis documentation for more details on trading fees and loss protection mechanisms - https://docs.avantisfi.com/.

Calculating Opening Fee and Loss Protection
-------------------------------------------

Before opening a trade, it's important to calculate the opening fee and understand the loss protection available for the trade. The following steps demonstrate how to retrieve this information using the SDK.

**Example Usage:**

.. code-block:: python

   # Calculate Opening Fee
   opening_fee_usdc = await trader_client.fee_parameters.get_opening_fee(
       trade_input=trade_input
   )
   print(f"Opening fee for this trade: {opening_fee_usdc} USDC")

   # Calculate Loss Protection
   loss_protection_info = (
       await trader_client.trading_parameters.get_loss_protection_for_trade_input(
           trade_input, opening_fee_usdc=opening_fee_usdc # Opening fee is optional (it will be calculated if not provided)
       )
   )
   print(f"Loss protection percentage for this trade: {loss_protection_info.percentage}%")
   print(f"You'll receive up to ${loss_protection_info.amount} as a loss rebate if the trade goes against you.")

**Details:**

- **Opening Fee**:
  - The opening fee is a cost associated with opening a new position. It's calculated based on the trade details provided in the `trade_input`.
  - The fee is returned in USDC and should be considered when evaluating the total cost of opening the trade.

  .. seealso:: For more detailed information on how the opening fee is calculated, refer to the :doc:`get_information_and_parameters`.

- **Loss Protection**:
  - Loss protection provides a percentage of the potential losses that are covered by Avantis's system.
  - The percentage and the maximum rebate amount are calculated based on the trade's parameters and current market conditions.

  .. seealso:: For more detailed information on loss protection, refer to the :doc:`get_information_and_parameters`.

**Notes:**

- Always calculate the opening fee before confirming a trade to ensure you are aware of the total cost.
- Understanding the loss protection available can help mitigate risks, especially in volatile markets.
- The examples above demonstrate how to retrieve these values, but the actual decision to open a trade should consider both the opening fee and the level of loss protection.


Retrieving Open Trades and Pending Limit Orders
-----------------------------------------------

The ``get_trades`` method retrieves all the open trades and pending limit orders for a given trader. This is useful for managing positions, monitoring trades, and understanding the current state of your orders.

**Parameters:**

- ``trader`` (str): The trader's wallet address.

**Returns:**

- A tuple containing:
  - A list of :class:`~avantis_trader_sdk.types.TradeExtendedResponse` instances representing the trader's open trades.
  - A list of :class:`~avantis_trader_sdk.types.PendingLimitOrderExtendedResponse` instances representing the trader's pending limit orders.

**Example Usage:**

.. code-block:: python

   trades, pending_open_limit_orders = await trader_client.trade.get_trades(trader="0xmywalletaddress")

   # Print open trades
   for trade in trades:
       print(f"Trade Index: {trade.trade.trade_index}, Collateral: {trade.trade.open_collateral} USDC, Leverage: {trade.trade.leverage}")

   # Print pending limit orders
   for order in pending_open_limit_orders:
       print(f"Order Index: {order.trade_index}, Collateral: {order.open_collateral} USDC, Leverage: {order.leverage}, Order Price: {order.price}")

**Details:**

- **Trades**:
  - Each trade includes detailed information such as the trading pair, collateral, leverage, take profit (TP), stop loss (SL), and more.
  - The method also retrieves additional info like open interest, last updated TP/SL timestamps, loss protection percentage, margin fee, and liquidation price.

- **Pending Limit Orders**:
  - The method gathers all pending limit orders that haven't been executed yet.
  - Each order includes details like collateral, leverage, order price, slippage, and the block in which it was placed.

**Notes:**

- This method interacts with the Multicall contract to fetch aggregated trade and order data for the specified trader.
- The returned data is formatted into structured responses (`TradeExtendedResponse` and `PendingLimitOrderExtendedResponse`) for ease of use.
- The information retrieved includes essential trade and order details, making it straightforward to manage and analyze positions.

Closing a Trade
---------------

The ``close_trade`` method allows you to close an open trade. You can close a trade fully or partially by specifying the amount of collateral to close. Below is an example of how to retrieve your trades, select one, and close it.

**Example Usage:**

.. code-block:: python

   # Get open and pending trades
   trades, pending_open_limit_orders = await trader_client.trade.get_trades(trader)
   print("Trades: ", trades)

   # Select the first trade to close
   trade_to_close = trades[0]

   # Close trade
   close_transaction = await trader_client.trade.build_trade_close_tx(
       pair_index=trade_to_close.trade.pair_index,
       trade_index=trade_to_close.trade.trade_index,
       collateral_to_close=trade_to_close.trade.open_collateral,  # Amount of collateral to close. Pass full amount to close the trade. Pass partial amount to partially close the trade.
       # collateral_to_close=trade_to_close.trade.open_collateral/2, # Uncomment this to close half of the trade
       trader=trader,
   )

   receipt = await trader_client.sign_and_get_receipt(close_transaction)

   print(receipt)
   print("Trade closed successfully!")

**Steps Explained:**

1. **Retrieve Open Trades:**
   - Use the `get_trades` method to retrieve all open trades and pending limit orders for the trader.

2. **Select a Trade to Close:**
   - Select a specific trade from the list of open trades. In this example, the first trade is selected.

3. **Build Close Transaction:**
   - Use the `build_trade_close_tx` method to construct a transaction for closing the selected trade. You can close the entire trade or partially close it by specifying the amount of collateral to close.

4. **Sign and Send Transaction:**
   - Sign the transaction using your private key and send it to the network. The transaction receipt confirms the successful closure of the trade.

**Notes:**

- Ensure that the correct trade is selected for closure to avoid closing the wrong position.
- Partial closures allow for flexible position management, enabling traders to reduce exposure without completely exiting the market.
- An execution fee is charged in ETH to execute the close trade transaction. This fee is required to cover the gas costs on the Ethereum network. This is automatically calculated.

Placing a Limit Order
----------------------

The ``open_limit_order`` method allows you to place a limit order. A limit order allows you to specify the desired execution price for the trade. This is similar to opening a market trade, but with the order type set to `LIMIT` and an open price specified.

**Example Usage:**

.. code-block:: python

   import asyncio
   from avantis_trader_sdk import TraderClient, TradeInput, TradeInputOrderType

   private_key = "0xmyprivatekey"

   async def main():
       # Initialize TraderClient
       provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
       trader_client = TraderClient(provider_url)

       # Set local signer
       trader_client.set_local_signer(private_key) # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

       trader = trader_client.get_signer().get_ethereum_address()

       # Get trader's USDC balance
       balance = await trader_client.get_usdc_balance(trader)
       print(f"Balance of {trader} is {balance} USDC")

       # Check allowance of USDC
       allowance = await trader_client.get_usdc_allowance_for_trading(trader)
       print(f"Allowance of {trader} is {allowance} USDC")
    
       amount_of_collateral = 10

       if allowance < amount_of_collateral:
           print(f"Allowance of {trader} is less than {amount_of_collateral} USDC. Approving...")
           await trader_client.approve_usdc_for_trading(amount_of_collateral)
           allowance = await trader_client.get_usdc_allowance_for_trading(trader)
           print(f"New allowance of {trader} is {allowance} USDC")

       # Get pair index of the pair. For example, ETH/USD
       pair_index_of_eth_usd = await trader_client.pairs_cache.get_pair_index("ETH/USD")

       # Prepare trade input
       trade_input = TradeInput(
           trader=trader,  # Trader's wallet address
           open_price=1500,  # Open price of the trade (Desired execution price)
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
       opening_fee_usdc = await trader_client.fee_parameters.get_opening_fee(
           trade_input=trade_input
       )
       print(f"Opening fee for this trade: {opening_fee_usdc} USDC")

       # Get loss protection percentage
       loss_protection_info = (
           await trader_client.trading_parameters.get_loss_protection_for_trade_input(
               trade_input, opening_fee_usdc=opening_fee_usdc
           )
       )
       print(f"Loss protection percentage for this trade: {loss_protection_info.percentage}%")
       print(f"You'll receive up to ${loss_protection_info.amount} as a loss rebate if the trade goes against you.")
       # ---------------------------------------------

       # 1% slippage
       slippage_percentage = 1

       # Order type for the trade (LIMIT in this case)
       trade_input_order_type = TradeInputOrderType.LIMIT

       # Open trade as a limit order
       open_transaction = await trader_client.trade.build_trade_open_tx(
           trade_input, trade_input_order_type, slippage_percentage
       )

       receipt = await trader_client.sign_and_get_receipt(open_transaction)

       print(receipt)
       print("Order placed successfully!")

   # Run the example
   asyncio.run(main())

**Details:**

- **Limit Order:**
  - A limit order is used when you want to specify the exact price at which you want to execute the trade. The order will only execute if the market reaches this price.
  - The `open_price` parameter in the `TradeInput` specifies the desired execution price.

**Steps Explained:**

1. **Initialize TraderClient:**
   - Connect to the Base Mainnet using a provider URL.

2. **Get Pair Index:**
   - Retrieve the index of the trading pair (e.g., ETH/USD).

3. **Prepare Trade Input:**
   - Define the trade details, including the trader's address, collateral, leverage, and desired execution price.

4. **Calculate Fees and Protection:**
   - Retrieve the opening fee and loss protection information for the trade.

5. **Set Order Type and Slippage:**
   - Define the order type as `LIMIT` and set the slippage tolerance.

6. **Build and Send Transaction:**
   - Construct the transaction for the limit order and send it to the network. The transaction receipt confirms the successful placement of the order.

**Notes:**

- Ensure that the `open_price` is set to your desired execution price.
- Limit orders provide control over the trade execution price but may not be filled if the market doesn't reach the specified price.
- An execution fee in ETH is required to place the order. This fee covers the gas costs on the Ethereum network. This is automatically calculated.

Canceling a Limit Order
------------------------

The ``cancel_limit_order`` method allows you to cancel a pending limit order. This can be useful if you no longer wish to execute the order or if market conditions have changed.

**Example Usage:**

.. code-block:: python

   import asyncio
   from avantis_trader_sdk import TraderClient

   private_key = "0xmyprivatekey"

   async def main():
       # Initialize TraderClient
       provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
       trader_client = TraderClient(provider_url)

       # Set local signer
       trader_client.set_local_signer(private_key) # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

       trader = trader_client.get_signer().get_ethereum_address()

       # Get open and pending trades
       trades, pending_open_limit_orders = await trader_client.trade.get_trades(trader)
       print("Pending Open Limit Orders: ", pending_open_limit_orders)

       # Select first order to cancel
       order_to_cancel = pending_open_limit_orders[0]

       # Cancel the order
       close_transaction = await trader_client.trade.build_order_cancel_tx(
        pair_index=order_to_cancel.pair_index,
        trade_index=order_to_cancel.trade_index,
        trader=trader,
       )

       receipt = await trader_client.sign_and_get_receipt(cancel_transaction)

       print(receipt)
       print("Order canceled successfully!")

   # Run the example
   asyncio.run(main())

**Details:**

- **Canceling a Limit Order:**
  - To cancel a limit order, you must specify the trading pair and trade index of the order you wish to cancel.
  - Once canceled, the limit order will not be executed, even if the market reaches the specified price.

**Steps Explained:**

1. **Retrieve Pending Limit Orders:**
   - Use the `get_trades` method to retrieve all open trades and pending limit orders for the trader.

2. **Select an Order to Cancel:**
   - Select a specific limit order from the list of pending orders. In this example, the first pending order is selected.

3. **Build Cancel Transaction:**
   - Use the `build_order_cancel_tx` method to construct a transaction for canceling the selected limit order.

4. **Sign and Send Transaction:**
   - Sign the transaction using your private key and send it to the network. The transaction receipt confirms the successful cancellation of the order.

**Notes:**

- Ensure that you cancel the correct limit order to avoid unintended cancellations.
- Once a limit order is canceled, it cannot be reinstated, so be certain before proceeding.

Updating Collateral (Margin Update)
-----------------------------------

The ``update_margin`` method allows you to deposit or withdraw collateral from an existing trade. This action adjusts the trade's leverage while keeping the position size the same. The minimum leverage allowed on the platform is 2x.

**Example Usage:**

.. code-block:: python

   import asyncio
   from avantis_trader_sdk import TraderClient, MarginUpdateType

   private_key = "0xmyprivatekey"

   async def main():
       # Initialize TraderClient
       provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
       trader_client = TraderClient(provider_url)

       # Set local signer
       trader_client.set_local_signer(private_key) # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

       trader = trader_client.get_signer().get_ethereum_address()

       # Get open trades
       trades, _ = await trader_client.trade.get_trades(trader)
       print("Trades: ", trades)

       # Select first trade to update
       trade_to_update = trades[0]

       # Check allowance of USDC
       allowance = await trader_client.get_usdc_allowance_for_trading(trader)
       print(f"Allowance of {trader} is {allowance} USDC")

       amount_of_collateral = 5
    
       if allowance < amount_of_collateral:
           print(f"Allowance of {trader} is less than {amount_of_collateral} USDC. Approving...")
           await trader_client.approve_usdc_for_trading(amount_of_collateral)
           allowance = await trader_client.get_usdc_allowance_for_trading(trader)
           print(f"New allowance of {trader} is {allowance} USDC")

       # ---------------------------------------------
       # NOTE: Any accrued margin fee on the trade will
       # be deducted from the deposited amount
       # ---------------------------------------------

       # Update trade margin
       deposit_transaction = await trader_client.trade.build_trade_margin_update_tx(
           trader=trader,
           pair_index=trade_to_update.trade.pair_index,
           trade_index=trade_to_update.trade.trade_index,
           margin_update_type=MarginUpdateType.DEPOSIT,  # Type of margin update (DEPOSIT or WITHDRAW)
           # margin_update_type=MarginUpdateType.WITHDRAW, # Uncomment this to withdraw collateral
           collateral_change=amount_of_collateral,  # Amount of collateral to deposit or withdraw
       )

       receipt = await trader_client.sign_and_get_receipt(private_key, deposit_transaction)

       print(receipt)
       print("Trade updated successfully!")

   # Run the example
   asyncio.run(main())

**Details:**

- **Margin Update:**
  - Margin updates allow you to deposit or withdraw collateral from an open trade, which in turn adjusts the leverage. Depositing collateral reduces leverage, while withdrawing collateral increases leverage.

- **Important Consideration:**
  - Any accrued margin fee on the trade will be deducted from the deposited amount during a deposit operation. Ensure that the deposit amount is sufficient to cover any fees and still achieve the desired margin update.

**Steps Explained:**

1. **Retrieve Open Trades:**
   - Use the `get_trades` method to retrieve all open trades for the trader.

2. **Select a Trade to Update:**
   - Select the trade you wish to update from the list of open trades. In this example, the first trade is selected.

3. **Build Margin Update Transaction:**
   - Use the `build_trade_margin_update_tx` method to construct a transaction for depositing or withdrawing collateral from the selected trade.

4. **Sign and Send Transaction:**
   - Sign the transaction using your private key and send it to the network. The transaction receipt confirms the successful margin update.

**Notes:**

- Adjusting the collateral impacts the leverage of the trade. Depositing collateral decreases leverage, providing more security, while withdrawing collateral increases leverage, potentially increasing risk.
- The minimum leverage allowed on the platform is 2x. Ensure that after any margin update, the leverage remains above this minimum threshold.
- The maximum leverage allowed can vary from asset to asset, so be sure to check the specific leverage limits for the asset you are trading.