Changelog
---------

This section outlines the changes made in each version of the Avantis Trader SDK

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
