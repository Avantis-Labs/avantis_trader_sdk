Usage
=====

The Avantis Trader SDK provides various methods to interact with Avantis contracts and retrieve trading parameters. Below are examples for each category.

Pairs Cache
-----------

The ``pairs_cache`` module provides methods to retrieve trading pairs and their details. Reference: :meth:`~avantis_trader_sdk.rpc.pairs_cache.PairsCache`:

get_pairs_info
^^^^^^^^^^^^^^^

The ``get_pairs_info`` method retrieves the pairs information from the blockchain. The information is cached and will be returned from the cache if it is available and force_update is False. This is to avoid unnecessary calls to the blockchain. This method is called internally by the SDK when the user requests any data related to trading pairs.

**Parameters:**

- ``force_update`` (bool, optional): If True, the cache will be ignored and the information will be retrieved from the blockchain. Defaults to False.

**Returns:**

- A dictionary containing the pairs information.

**Example Usage:**

.. code-block:: python

   pairs_info = await trader_client.pairs_cache.get_pairs_info()
   print("Pairs Info:", pairs_info)

get_pairs_count
^^^^^^^^^^^^^^^

The ``get_pairs_count`` method retrieves the number of trading pairs available on the blockchain.

**Returns:**

- The number of trading pairs available on the blockchain. (int)

**Example Usage:**

.. code-block:: python

   pairs_count = await trader_client.pairs_cache.get_pairs_count()
   print("Pairs Count:", pairs_count)

get_group_indexes
^^^^^^^^^^^^^^^^^

The ``get_group_indexes`` method retrieves the group ids from the blockchain. The group ids are used to categorize trading pairs based on their underlying asset. For example, all trading pairs with the same underlying asset will have the same group id. This method is called internally by the SDK when the user requests any data related to trading pairs.

Group id 0 and 1 are reserved for the crypto groups. Group id 2 is reserved for the forex group. Group id 3 is reserved for the commodities group.

Each pair in pair info, returned by :meth:`~avantis_trader_sdk.rpc.pairs_cache.PairsCache.get_pairs_info`, has a group index ``groupIndex`` property.

**Returns:**

- The group ids as a set.

**Example Usage:**

.. code-block:: python

   group_indexes = await trader_client.pairs_cache.get_group_indexes()
   print("Group Indexes:", group_indexes)


get_pair_index
^^^^^^^^^^^^^^

The ``get_pair_index`` method retrieves the index of a trading pair from the blockchain. The index is used to identify the trading pair in the blockchain.

**Parameters:**

- ``pair`` (str): The trading pair to retrieve the index for. Expects a string in the format "from/to".

**Returns:**

- The index of the pair as an integer (int).

**Raises:**

- ValueError: If the pair is not found in the pairs information.

**Example Usage:**

.. code-block:: python

   pair_index = await trader_client.pairs_cache.get_pair_index("ETH/USD")
   print("Pair Index:", pair_index)


Asset Parameters
----------------

The ``asset_parameters`` module provides methods to retrieve and calculate various asset parameters related to trading. Reference: :meth:`~avantis_trader_sdk.rpc.asset_parameters.AssetParametersRPC`:

get_oi_limits
^^^^^^^^^^^^^

The ``get_oi_limits`` method retrieves the open interest limits for all trading pairs. Open interest limits are the maximum allowable open interest for each trading pair, which helps manage risk and liquidity in the market.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.OpenInterestLimits` containing the open interest limits for each trading pair. Each entry in the ``limits`` dictionary maps a trading pair (e.g., "ETH/USD") to its corresponding open interest limit.

**Example Usage:**

.. code-block:: python

   oi_limits = await trader_client.asset_parameters.get_oi_limits()
   print("Open Interest Limits:", oi_limits.limits)

**Notes:**

- The open interest limits are returned in units of the quote currency of each trading pair.

get_oi
^^^^^^

The ``get_oi`` method retrieves the current open interest for all trading pairs. Open interest represents the total number of open positions in a trading pair, which is a key metric for understanding market liquidity and trader sentiment.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.OpenInterest` containing the long and short open interest ratios for each trading pair. The ``long`` and ``short`` dictionaries map each trading pair (e.g., "ETH/USD") to its corresponding long and short open interest ratios, respectively.

**Example Usage:**

.. code-block:: python

   oi = await trader_client.asset_parameters.get_oi()
   print("Open Interest (Long):", oi.long)
   print("Open Interest (Short):", oi.short)

**Notes:**

- The open interest ratios are returned as percentages, representing the proportion of long or short positions relative to the total open interest in each trading pair.

get_utilization
^^^^^^^^^^^^^^^

The ``get_utilization`` method calculates the asset utilization for all trading pairs. Asset utilization is a measure of how much of the available open interest limit is currently being used by open positions.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Utilization` containing the asset utilization percentage for each trading pair. The ``utilization`` dictionary maps each trading pair (e.g., "ETH/USD") to its corresponding utilization percentage.

**Example Usage:**

.. code-block:: python

   utilization = await trader_client.asset_parameters.get_utilization()
   print("Asset Utilization:", utilization.utilization)

**Notes:**

- Utilization is calculated as the current open interest divided by the open interest limit for each trading pair.
- A higher utilization percentage indicates that a larger portion of the available limit is being used, which can impact the cost of opening new positions (e.g., higher fees or price impact).
- Utilization is returned as a percentage, where 100% means the open interest limit is fully utilized.

get_asset_skew
^^^^^^^^^^^^^^

The ``get_asset_skew`` method calculates the asset skew for all trading pairs. Asset skew is a measure of the imbalance between long and short open interest.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Skew` containing the asset skew percentage for each trading pair. The ``skew`` dictionary maps each trading pair (e.g., "ETH/USD") to its corresponding skew percentage.

**Example Usage:**

.. code-block:: python

   skew = await trader_client.asset_parameters.get_asset_skew()
   print("Asset Skew:", skew.skew)

**Notes:**

- Skew is calculated as the percentage of long open interest relative to the total open interest (long + short) for each trading pair.
- A skew of 50% indicates a balanced market with equal long and short interest. A skew higher than 50% indicates a market biased towards long positions, and a skew lower than 50% indicates a market biased towards short positions.
- Skew is returned as a percentage, where 100% means all open interest is in long positions, and 0% means all open interest is in short positions.

get_price_impact_spread
^^^^^^^^^^^^^^^^^^^^^^^

The ``get_price_impact_spread`` method retrieves the price impact spread for all trading pairs. Price impact spread is a measure of how much the price is expected to move due to a trade.

**Parameters:**

- ``position_size`` (int): The size of the position (collateral * leverage). Supports up to 6 decimals. Defaults to 0.
- ``is_long`` (bool, optional): A boolean indicating if the position is a buy (long) or sell (short). Defaults to None. If None, the price impact spread for both buy and sell will be returned.
- ``pair`` (str, optional): The trading pair for which the price impact spread is to be calculated. Defaults to None. If None, the price impact spread for all trading pairs will be returned.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Spread` containing the price impact spread for each trading pair. The ``long`` and ``short`` dictionaries within the ``Spread`` instance map each trading pair (e.g., "ETH/USD") to its corresponding price impact spread for long and short positions, respectively.

**Example Usage:**

.. code-block:: python

   # Example 1: Specify position size, is_long, and pair
   price_impact_spread = await trader_client.asset_parameters.get_price_impact_spread(position_size=1000, is_long=True, pair="ETH/USD")
   print("Price Impact Spread for ETH/USD (Long):", price_impact_spread.long["ETH/USD"])

   # Example 2: Omit is_long to get both long and short spreads for a specific pair
   price_impact_spread = await trader_client.asset_parameters.get_price_impact_spread(position_size=1000, pair="ETH/USD")
   print("Price Impact Spread for ETH/USD (Long):", price_impact_spread.long["ETH/USD"])
   print("Price Impact Spread for ETH/USD (Short):", price_impact_spread.short["ETH/USD"])

   # Example 3: Omit pair to get spreads for all pairs
   price_impact_spread = await trader_client.asset_parameters.get_price_impact_spread(position_size=1000, is_long=True)
   print("Price Impact Spread for all pairs (Long):", price_impact_spread.long)

   # Example 4: Omit both is_long and pair to get both long and short spreads for all pairs
   price_impact_spread = await trader_client.asset_parameters.get_price_impact_spread(position_size=1000)
   print("Price Impact Spread for all pairs (Long):", price_impact_spread.long)
   print("Price Impact Spread for all pairs (Short):", price_impact_spread.short)

**Notes:**

- The price impact spread is expressed as a percentage and represents the expected price movement due to a trade of the specified size.
- For example, a price impact spread of 0.5% for a long position means that the price is expected to increase by 0.5% due to the trade.
- For example, a negative price impact spread for a long position means that the price is expected to decrease by the specified percentage due to the trade. This can give better entry prices for long positions.
- This method is used with the ``get_opening_price_impact_spread`` and ``get_skew_impact_spread`` method to calculate the expected price movement due to the opening of a new position.


get_skew_impact_spread
^^^^^^^^^^^^^^^^^^^^^^

The ``get_skew_impact_spread`` method retrieves the skew impact spread for all trading pairs. Skew impact spread is a measure of how much the price is expected to move due to the imbalance between long and short positions.

**Parameters:**

- ``position_size`` (int, optional): The size of the position (collateral * leverage). Supports up to 6 decimals. Defaults to 0.
- ``is_long`` (bool, optional): A boolean indicating if the position is a buy (long) or sell (short). Defaults to None. If None, the skew impact spread for both buy and sell will be returned.
- ``pair`` (str, optional): The trading pair for which the skew impact spread is to be calculated. Defaults to None. If None, the skew impact spread for all trading pairs will be returned.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Spread` containing the skew impact spread for each trading pair. The ``long`` and ``short`` dictionaries within the ``Spread`` instance map each trading pair (e.g., "ETH/USD") to its corresponding skew impact spread for long and short positions, respectively.

**Example Usage:**

.. code-block:: python

   # Example 1: Specify position size, is_long, and pair
   skew_impact_spread = await trader_client.asset_parameters.get_skew_impact_spread(position_size=1000, is_long=True, pair="ETH/USD")
   print("Skew Impact Spread for ETH/USD (Long):", skew_impact_spread.long["ETH/USD"])

   # Example 2: Omit is_long to get both long and short spreads for a specific pair
   skew_impact_spread = await trader_client.asset_parameters.get_skew_impact_spread(position_size=1000, pair="ETH/USD")
   print("Skew Impact Spread for ETH/USD (Long):", skew_impact_spread.long["ETH/USD"])
   print("Skew Impact Spread for ETH/USD (Short):", skew_impact_spread.short["ETH/USD"])

   # Example 3: Omit pair to get spreads for all pairs
   skew_impact_spread = await trader_client.asset_parameters.get_skew_impact_spread(position_size=1000, is_long=True)
   print("Skew Impact Spread for all pairs (Long):", skew_impact_spread.long)

   # Example 4: Omit both is_long and pair to get both long and short spreads for all pairs
   skew_impact_spread = await trader_client.asset_parameters.get_skew_impact_spread(position_size=1000)
   print("Skew Impact Spread for all pairs (Long):", skew_impact_spread.long)
   print("Skew Impact Spread for all pairs (Short):", skew_impact_spread.short)

**Notes:**

- The skew impact spread is expressed as a percentage and represents the expected price movement due to the imbalance between long and short positions.
- For example, a skew impact spread of 0.5% for a long position means that the price is expected to increase by 0.5% due to the skew between long and short positions.
- For example, a negative skew impact spread for a long position means that the price is expected to decrease by the specified percentage due to the skew between long and short positions. This can give better entry prices for long positions.
- This method is used with the ``get_price_impact_spread`` and ``get_opening_price_impact_spread`` method to calculate the expected price movement due to the opening of a new position.

get_opening_price_impact_spread
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``get_opening_price_impact_spread`` method retrieves the trade price impact spread for a specific trading pair. This measure indicates how much the price is expected to move due to the opening of a new position.

**Parameters:**

- ``pair`` (str): The trading pair for which the price impact is to be calculated.
- ``position_size`` (int, optional): The size of the position (collateral * leverage). Supports up to 6 decimals. Defaults to 0.
- ``open_price`` (float, optional): The price at which the position was opened. Supports up to 10 decimals. Defaults to 0.
- ``is_long`` (bool, optional): A boolean indicating if the position is a buy (long) or sell (short). Defaults to None. If None, the price impact for both buy and sell will be returned.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Spread` containing the trade price impact for the specified pair. The ``long`` and ``short`` attributes within the ``Spread`` instance represent the price impact for long and short positions, respectively.

**Example Usage:**

.. code-block:: python

   # Specify pair, position size, open price, and is_long
   opening_price_impact_spread = await trader_client.asset_parameters.get_opening_price_impact_spread(
       pair="ETH/USD",
       position_size=1000,
       open_price=3200,
       is_long=True
   )
   print("Opening Price Impact Spread for ETH/USD (Long):", opening_price_impact_spread.long["ETH/USD"])

   # Omit is_long to get both long and short price impacts for a specific pair
   opening_price_impact_spread = await trader_client.asset_parameters.get_opening_price_impact_spread(
       pair="ETH/USD",
       position_size=1000,
       open_price=3200
   )
   print("Opening Price Impact Spread for ETH/USD (Long):", opening_price_impact_spread.long["ETH/USD"])
   print("Opening Price Impact Spread for ETH/USD (Short):", opening_price_impact_spread.short["ETH/USD"])

**Notes:**

- The trade price impact spread is expressed as a percentage and represents the expected price movement due to the opening of a new position.
- For example, an opening price impact spread of 0.5% for a long position means that the price is expected to increase by 0.5% due to the opening of the position.
- For example, a negative opening price impact spread for a long position means that the price is expected to decrease by the specified percentage due to the opening of the position. This can give better entry prices for long positions.
- The open price is used with ``get_price_impact_spread`` and ``get_skew_impact_spread`` to calculate the expected price movement due to the opening of a new position.

Category Parameters
-------------------

The ``category_parameters`` module provides methods to retrieve and calculate various category parameters related to trading. Reference: :meth:`~avantis_trader_sdk.rpc.category_parameters.CategoryParametersRPC`:

get_oi_limits
^^^^^^^^^^^^^

The ``get_oi_limits`` method retrieves the open interest limits for all categories.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.OpenInterestLimits` containing the open interest limits for each category. The ``limits`` dictionary maps each category index to its corresponding open interest limit.

**Example Usage:**

.. code-block:: python

   oi_limits = await trader_client.category_parameters.get_oi_limits()
   print("Open Interest Limits:", oi_limits.limits)

**Notes:**

- The open interest limit for a category represents the maximum allowed open interest for all trading pairs within that category.
- The category index is used to identify different categories, such as crypto, forex, and commodities.
- This method is useful for understanding the maximum exposure allowed for each category on the platform.

get_oi
^^^^^^

The ``get_oi`` method retrieves the current open interest for all categories.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.OpenInterest` containing the long and short open interest for each category. The ``long`` and ``short`` dictionaries within the ``OpenInterest`` instance map each category index to its corresponding long and short open interest, respectively.

**Example Usage:**

.. code-block:: python

   oi = await trader_client.category_parameters.get_oi()
   print("Long Open Interest:", oi.long)
   print("Short Open Interest:", oi.short)

**Notes:**

- Open interest represents the total number of outstanding contracts that have not been settled.
- The category index is used to identify different categories, such as crypto, forex, and commodities.
- This method provides a snapshot of the market's open interest distribution across different categories.

get_utilization
^^^^^^^^^^^^^^^

The ``get_utilization`` method calculates the category utilization for all categories.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Utilization` containing the category utilization percentage for each category. The ``utilization`` dictionary within the ``Utilization`` instance maps each category index to its corresponding utilization percentage.

**Example Usage:**

.. code-block:: python

   utilization = await trader_client.category_parameters.get_utilization()
   print("Category Utilization:", utilization.utilization)

**Notes:**

- Category utilization is a measure of how much of the open interest limits for each category is currently being utilized.
- It is calculated as the current open interest divided by the open interest limit for each category, expressed as a percentage.
- A higher utilization percentage indicates a higher level of activity and risk in that category.

get_category_skew
^^^^^^^^^^^^^^^^^

The ``get_category_skew`` method calculates the category skew for all categories.

**Returns:**

- An instance of :class:`~avantis_trader_sdk.types.Skew` containing the category skew percentage for each category. The ``skew`` dictionary within the ``Skew`` instance maps each category index to its corresponding skew percentage.

**Example Usage:**

.. code-block:: python

   category_skew = await trader_client.category_parameters.get_category_skew()
   print("Category Skew:", category_skew.skew)

**Notes:**

- Category skew is a measure of the imbalance between long and short open interest within each category.
- It is calculated as the percentage of long open interest relative to the total open interest (long + short) for each category.
- A skew of 50% indicates a balanced market with equal long and short interest. A skew higher than 50% indicates a market biased towards long positions, and a skew lower than 50% indicates a market biased towards short positions.
- Skew is returned as a percentage, where 100% means all open interest is in long positions, and 0% means all open interest is in short positions.


Trading Parameters
------------------

The ``trading_parameters`` module provides methods to retrieve and calculate various trading parameters related to opening and closing positions. Reference: :meth:`~avantis_trader_sdk.rpc.trading_parameters.TradingParametersRPC`:


get_loss_protection_tier
^^^^^^^^^^^^^^^^^^^^^^^^

The ``get_loss_protection_tier`` method retrieves the loss protection tier for a trade. Loss protection tiers are part of Avantis's reward system, offering protection against losses under certain conditions. Read more about loss protection tiers in the `Avantis documentation <https://docs.avantisfi.com/rewards/loss-protection>`_. Returned index is 0-based. Indexes are mapped to the tiers.

**Parameters:**

- ``trade`` (:class:`~avantis_trader_sdk.types.TradeInput`): A TradeInput instance containing the trade details.

**Returns:**

- The loss protection tier as an integer (int).

**Example Usage:**

.. code-block:: python

   trade_input = TradeInput(
      pair_index=await trader_client.pairs_cache.get_pair_index("ARB/USD"),
      collateral=1,
      is_long=False,
      leverage=2,
   )
   loss_protection_tier = await trader_client.trading_parameters.get_loss_protection_tier(trade_input)
   print("Loss Protection Tier:", loss_protection_tier)

**Notes:**

- The loss protection tier is determined based on the trade's parameters and the current market conditions.
- A higher tier generally indicates a greater level of protection against losses.
- Read more about loss protection tiers `here <https://docs.avantisfi.com/rewards/loss-protection>`_.

Fee Parameters
--------------

The ``fee_parameters`` module provides methods to retrieve and calculate various fee parameters related to trading. Reference: :meth:`~avantis_trader_sdk.rpc.fee_parameters.FeeParametersRPC`:

get_margin_fee
^^^^^^^^^^^^^^

The ``get_margin_fee`` method retrieves the margin fee for all trading pairs. Margin fees are charged for holding leveraged positions and vary depending on the trading pair and the direction of the trade (long or short).

**Returns:**

- A :class:`~avantis_trader_sdk.types.MarginFee` instance containing the margin fee for each trading pair. The instance includes the base fee, margin fee for long positions, and margin fee for short positions.

**Example Usage:**

.. code-block:: python

   margin_fee = await trader_client.fee_parameters.get_margin_fee()
   print("Base Margin Fee:", margin_fee.base)
   print("Long Margin Fee:", margin_fee.margin_long)
   print("Short Margin Fee:", margin_fee.margin_short)

**Notes:**

- The margin fee is expressed as a percentage of the position size and is typically charged on a per-block basis.
- The base fee is the fee charged for non-leveraged trades.
- The margin_long and margin_short fees are the additional fees charged for leveraged long and short positions, respectively.

get_pair_spread
^^^^^^^^^^^^^^^

The ``get_pair_spread`` method retrieves the spread percentage for all trading pairs. The spread is the difference between the bid and ask prices, expressed as a percentage of the mid-price.

**Returns:**

- A :class:`~avantis_trader_sdk.types.PairSpread` instance containing the spread percentage for each trading pair.

**Example Usage:**

.. code-block:: python

   pair_spread = await trader_client.fee_parameters.get_pair_spread()
   print("Pair Spread:", pair_spread.spread)

**Notes:**

- The spread is an important factor in trading as it affects the cost of entering and exiting positions.
- A lower spread indicates a more liquid market with tighter bid-ask prices, while a higher spread suggests less liquidity and wider bid-ask prices.

get_opening_fee
^^^^^^^^^^^^^^^

The ``get_opening_fee`` method retrieves the opening fee for all trading pairs. The opening fee is a fee charged when opening a new position.

**Parameters:**

- ``position_size`` (int): The size of the position (collateral * leverage). Supports up to 6 decimals. Defaults to 0.
- ``is_long`` (Optional[bool]): A boolean indicating if the position is a buy (long) or sell (short). Defaults to None. If None, the opening fee for both buy and sell will be returned.
- ``pair`` (str, optional): The trading pair for which the opening fee is to be calculated. Defaults to None. If None, the opening fee for all trading pairs will be returned.

**Returns:**

- A :class:`~avantis_trader_sdk.types.Fee` instance containing the opening fee for each trading pair. The ``long`` and ``short`` dictionaries within the ``Fee`` instance map each trading pair (e.g., "ETH/USD") to its corresponding opening fee for long and short positions, respectively.

**Example Usage:**

.. code-block:: python

   # Example 1: Specify position size, is_long, and pair
   opening_fee = await trader_client.fee_parameters.get_opening_fee(position_size=1000, is_long=True, pair="ETH/USD")
   print("Opening Fee for ETH/USD (Long):", opening_fee.long["ETH/USD"])

   # Example 2: Omit is_long to get both long and short fees for a specific pair
   opening_fee = await trader_client.fee_parameters.get_opening_fee(position_size=1000, pair="ETH/USD")
   print("Opening Fee for ETH/USD (Long):", opening_fee.long["ETH/USD"])
   print("Opening Fee for ETH/USD (Short):", opening_fee.short["ETH/USD"])

   # Example 3: Omit pair to get fees for all pairs
   opening_fee = await trader_client.fee_parameters.get_opening_fee(position_size=1000, is_long=True)
   print("Opening Fee for all pairs (Long):", opening_fee.long)

   # Example 4: Omit both is_long and pair to get both long and short fees for all pairs
   opening_fee = await trader_client.fee_parameters.get_opening_fee(position_size=1000)
   print("Opening Fee for all pairs (Long):", opening_fee.long)
   print("Opening Fee for all pairs (Short):", opening_fee.short)

**Notes:**

- The opening fee is expressed as a percentage of the position size.
- The fee is applied when opening a new position and is deducted from the position's initial margin.


Price Feed
----------

The ``price_feed`` module provides methods to register callbacks for real-time price feed updates. Avantis uses Pyth for price feeds. Read more about Pyth here: https://docs.pyth.network/. Reference: :meth:`~avantis_trader_sdk.feed_client.FeedClient`:

register_price_feed_callback
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``register_price_feed_callback`` method registers a callback for price feed updates. This allows you to receive real-time price updates for a specific trading pair or price feed identifier. You can get price feed ids from https://pyth.network/developers/price-feed-ids.

**Parameters:**

- ``identifier`` (str): The identifier of the price feed to register the callback for. This can be either the price feed ID (e.g., "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723") or the trading pair (e.g., "ETH/USD").
- ``callback`` (Callable): The callback function to register. The callback should accept a single argument, which will be the price feed data.

**Raises:**

- ``ValueError``: If the identifier is unknown or not supported.

**Example Usage:**

.. code-block:: python

   def price_update_callback(data):
       print("Price Update:", data)

   # Example 1: Register a callback by using pair name
   feed_client.register_price_feed_callback("ETH/USD", price_update_callback)

   # Example 2: Register a callback by using price feed id
   feed_client.register_price_feed_callback("0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723", price_update_callback)

**Notes:**

- The price feed data passed to the callback will typically include information such as the current price, confidence interval, and timestamp.
- You can register multiple callbacks for the same price feed identifier to handle different aspects of the price update.

unregister_price_feed_callback
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``unregister_price_feed_callback`` method unregisters a previously registered callback for price feed updates. This is useful if you no longer need to receive updates for a specific price feed.

**Parameters:**

- ``identifier`` (str): The identifier of the price feed to unregister the callback for. This can be either the price feed ID (e.g., "0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723") or the trading pair (e.g., "ETH/USD").
- ``callback`` (Callable): The callback function to unregister.

**Example Usage:**

.. code-block:: python

   def price_update_callback(data):
       print("Price Update:", data)

   feed_client.register_price_feed_callback("ETH/USD", price_update_callback)
   # Later, when you no longer need the updates:
   feed_client.unregister_price_feed_callback("ETH/USD", price_update_callback)

**Notes:**

- Make sure the identifier and callback match the ones used during registration with ``register_price_feed_callback``.
- If the specified callback is not found for the given identifier, this method will silently complete without any error.

listen_for_price_updates
^^^^^^^^^^^^^^^^^^^^^^^^

The ``listen_for_price_updates`` method listens for real-time price updates from the Pyth price feed websocket. When a price update is received, all registered callbacks for that price feed are called with the updated price data.

**Raises:**

- ``Exception``: If an error occurs while listening for price updates.

**Example Usage:**

.. code-block:: python

   async def price_update_callback(data):
       print("Price Update:", data)

   feed_client.register_price_feed_callback("ETH/USD", price_update_callback)
   await feed_client.listen_for_price_updates()

**Notes:**

- This method is an asynchronous coroutine and should be called using ``await`` in an asynchronous context.
- The registered callbacks will be called with an instance of :class:`~avantis_trader_sdk.types.PriceFeedResponse`, which contains the updated price data for the subscribed price feed.
- If the websocket connection is closed due to an error, the registered ``on_close`` callback will be called with the exception, if provided. Otherwise, the exception will be printed.
- If any other exception occurs during the listening process, the registered ``on_error`` callback will be called with the exception, if provided. Otherwise, the exception will be re-raised.

get_pair_from_feed_id
^^^^^^^^^^^^^^^^^^^^^

The ``get_pair_from_feed_id`` method retrieves the trading pair string (e.g., "ETH/USD") corresponding to a given price feed ID.

**Parameters:**

- ``feed_id`` (str): The feed ID to retrieve the pair string for.

**Returns:**

- The trading pair string associated with the feed ID, if found. Otherwise, ``None``.

**Example Usage:**

.. code-block:: python

   pair_string = feed_client.get_pair_from_feed_id("0x09f7c1d7dfbb7df2b8fe3d3d87ee94a2259d212da4f30c1f0540d066dfa44723")
   print("Pair String:", pair_string)

**Notes:**

- The feed ID should be a hexadecimal string starting with "0x". If the provided feed ID does not start with "0x", it will be automatically prefixed with "0x" before performing the lookup.
- This method is used internally by the SDK to map price feed updates to their corresponding trading pairs.
