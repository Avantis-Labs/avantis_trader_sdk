Changelog
---------

This section outlines the changes made in each version of the Avantis Trader SDK

**Version 0.8.3 (2025-07-25)**

- **New Features:**
  - Added support for using a custom socket API for pair feeds.

**Version 0.8.2 (2025-04-07)**

- **Bug Fixes:**
  - Fixed a bug where the trade type for zero fee market trades was not being set correctly.


**Version 0.8.1 (2025-04-07)**

- **New Features:**
  - Added support for opening zero fee market trades.

**Version 0.8.0 (2025-02-21)**

- More Info: https://avantisfi.notion.site/avantis-contracts-v1-5-upgrade

- **Breaking Changes:**

  - **New ABIs Introduced**:
    - **PairInfos ABI**
    - **PriceAggregator ABI**
    - **Trading ABI**
    - **TradingCallbacks ABI**
    - **TradingStorage ABI**

  - **Price Impact Spread Calculations**:
    
    - The following methods now support the **isPnl** parameter:
      
      - `get_price_impact_spread`
      - `get_skew_impact_spread`
      - `get_opening_price_impact_spread`

  - **Trade Transactions**:
    
    - **Open and Close Trade Transactions**: The last parameter for `execution_fee` has been **removed** in the contract.
    - **Previous Behavior**: Required `execution_fee` as the last parameter.
    - **New Behavior**: No longer requires `execution_fee`. Ensure transaction-building logic is updated accordingly.

    - ⚠️ *This is an important change—ensure your integration reflects this update.*

  - **Loss Protection Tier**:
    - Updated `get_loss_protection_tier` to support the new **PnL order type**.

  - **Referral Rebates**:
    - Updated `get_trade_referral_rebate_percentage`: The contract method for tiers has changed to `referralTiers`.

  - **Order Type Enum Update**:
    
    - The `TradeInputOrderType` enum has been updated to support the **new PnL order type**:

    .. code-block:: python

        class TradeInputOrderType(Enum):
            ...
            MARKET_PNL = 3


**Version 0.7.0 (2025-02-09)**

- **Breaking Changes:**
  - **Modified Write Contract**:

    - **Previous Behavior**: The `write_contract` method would return the transaction hash.
    - **New Behavior**: The `write_contract` method now returns the transaction receipt.
  

  - **Modified Get Balance**:

    - **Previous Behavior**: The `get_balance` method would return the balance of the account in wei.
    - **New Behavior**: The `get_balance` method now returns the balance of the account in ETH.

- **Improvements:**

  - Removed dependency on hardcoded pair feed ids.
  - Added support for fetching feed mappings dynamically from an API or trader client.
  - Introduced an optional `pair_fetcher` function in feed client for full customization.
  - Revised example to demonstrate how to use both an API or trader client to retrieve the latest price updates.

**Version 0.6.0 (2025-01-24)**

- **Breaking Changes:**
  - **Modified ABI**:

    - **`PairStorage` ABI**:

      - **Previous Behavior**: The ABI had a simpler structure for accessing pair data.
      - **New Behavior**: Updated to include more detailed and flexible structures for pair data access.

  - **Modified Data Models**:
  
    - **`PairInfo`**:

      - **Previous Behavior**: Limited fields for leverage and pair metrics.
      - **New Behavior**: Enhanced with additional fields to accommodate new metrics:
        - **Leverages**:
          - `min_leverage`: Minimum leverage for pairs.
          - `max_leverage`: Maximum leverage for pairs.
          - `pnl_min_leverage`: Minimum leverage for PnL calculations.
          - `pnl_max_leverage`: Maximum leverage for PnL calculations.

        - **Values**:

          - `max_gain_percentage`: Maximum allowable gain percentage.
          - `max_sl_percentage`: Maximum stop-loss percentage.
          - `max_long_oi_percentage`: Maximum open interest percentage for long trades.
          - `max_short_oi_percentage`: Maximum open interest percentage for short trades.
          - `group_open_interest_percentage`: Group-level open interest percentage limit.
          - `max_wallet_oi_percentage`: Maximum open interest percentage per wallet.
          - `is_usdc_aligned`: Boolean indicating USDC alignment.
          

        - **Additional Fields**:

          - `backup_feed`: Backup source for price feeds.
          - `constant_pnl_spread_bps`: Basis points for constant PnL spreads.

- **New Data Models**:
  - **`PairInfoWithData`**:
    - Combines detailed pair data (`PairInfo`) with additional metrics (`PairData`).
    - Includes all new fields from `PairInfo` as well as the following:
      - `PairData`: Contains essential details such as `from`, `to`, and pair-related attributes.

- **Improvements:**
  - Enhanced data model flexibility for pair configurations.
  - Updated documentation to reflect the new ABI structure.


**Version 0.5.0 (2025-01-17)**
- **Breaking Changes:**
  - **Modified Methods**:
    - **`build_trade_close_tx`**:
      - **Previous Behavior**: Required a 6 decimal precision float for collateral_to_close. e.g. 100500000 for 100.5 USDC
      - **New Behavior**: Now requires a normal float value for collateral_to_close. e.g. 100.5 for 100.5 USDC

  - **New Methods**:
    - **`build_trade_tp_sl_update_tx`**:
      - **Description**: Introduced a new method specifically for updating the take profit and stop loss of a trade.
      - **Purpose**: To allow traders to update the take profit and stop loss of a trade without having to close and open a new trade.
      - **Input**: Accepts a `pair_index`, `trade_index`, `take_profit_price`, `stop_loss_price`, and `trader` (optional).
      - **Output**: Returns the transaction object to update the take profit and stop loss of a trade.

- **Improvements:**
   - Added warning for upcoming v1.5 contracts upgrade
   - Fixed margin update and USDC approval methods
   - Optimized fee values for margin updates
   - `write_contract` will now auto fill the `nonce` and `chainId` if not provided

**Version 0.4.0 (2024-12-02)**
- **Breaking Changes:**
  - **Modified Methods**:
    - **`get_opening_fee`**:
      - **Previous Behavior**: Returned a `Fee` instance with fee details based on input parameters. If the parameters included `trade_input`, it would calculate and return the final fee in USDC.
      - **New Behavior**: Now strictly returns fee details in **basis points (bps)** based on input parameters. It no longer accepts `trade_input` as an argument. This ensures consistent behavior and avoids ambiguity.

  - **New Methods**:
    - **`get_new_trade_opening_fee`**:
      - **Description**: Introduced a new method specifically for calculating the **final opening fee in USDC** for a trade, based on the provided `trade_input`.
      - **Purpose**: To handle trade-specific fee calculations consistently and separately from the broader `get_opening_fee` method.
      - **Input**: Accepts a `TradeInput` object.
      - **Output**: Returns the calculated opening fee in USDC, adjusted for referral rebates.

**Version 0.3.1 (2024-10-23)**
   - Added feed ids for new pairs

**Version 0.3.0 (2024-10-20)**

- **Breaking Changes:**
  
  - Refactored transaction signing:
  
    Existing integrations may require updates to align with the new signing approach (see updated examples: :doc:`trade <trade>` and `GitHub Examples <https://github.com/Avantis-Labs/avantis_trader_sdk/tree/main/examples>`_).
  
  - Made the `trader` parameter optional in select trading methods:
  
    Ensure your code accounts for cases where `trader` may not be explicitly provided. Affected methods include:
  
    - `build_trade_close_tx`
    - `build_order_cancel_tx`
    - `build_trade_margin_update_tx`

- **New Features:**
   - Added support for approving USDC for trading.
   - Introduced support for transaction signing via AWS KMS.
   - Implemented a `BaseSigner` class to allow custom signer integrations.

- **Improvements:**
   - Refactored transaction signing for better flexibility and integration.
   - Enhanced examples to demonstrate the new allowance and approve methods.
   - Updated examples to utilize the new signer methods.
   - Expanded documentation with additional examples and use cases.

**Version 0.2.2 (2024-10-16)**
   - Added support for Python v3.6
   - Handled de-listed pairs gracefully

**Version 0.2.1 (2024-08-31)**
   - Added support for trading.
   - Improved error handling and logging.
   - Updated to pydantic 2.0 for data validation.
   - Updated documentation with more examples and use cases.
   - Added support for price updates on demand.

**Version 0.1.0 (2024-03-01)**
   - Initial release of the Avantis Trader SDK.
   - Added support for asset parameters, category parameters, trading parameters, and fee parameters.
   - Implemented a websocket client for real-time price feed updates.
