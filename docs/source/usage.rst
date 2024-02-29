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

WIP

Category Parameters
-------------------

WIP

Trading Parameters
------------------

WIP

Fee Parameters
--------------

This section describes the various fee-related parameters and methods available in the Avantis Trader SDK.

get_opening_fee
^^^^^^^^^^^^^^^

The ``get_opening_fee`` method retrieves the opening fee for a given trading pair, position size, and direction (long or short). This fee is applicable when opening a new position and is calculated based on the current market conditions and the size of the position.

**Parameters:**

- ``position_size`` (int, optional): The size of the position (collateral * leverage). Supports up to 6 decimals. Defaults to 0.
- ``is_long`` (Optional[bool], optional): A boolean indicating if the position is a buy (long) or sell (short). Defaults to None. If None, the opening fee for both buy and sell will be returned.
- ``pair`` (str, optional): The trading pair for which the opening fee is to be calculated. Defaults to None. If None, the opening fee for all trading pairs will be returned.

**Returns:**

- A ``Fee`` instance containing the opening fee for each trading pair.

**Example Usage:**

.. code-block:: python

   opening_fee_long = await trader_client.fee_parameters.get_opening_fee(position_size=1000, is_long=True, pair="ETH/USD")
   opening_fee_short = await trader_client.fee_parameters.get_opening_fee(position_size=1000, is_long=False, pair="ETH/USD")
   print("Opening Fee (Long):", opening_fee_long)
   print("Opening Fee (Short):", opening_fee_short)



