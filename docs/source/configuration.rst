Configuration
=============

To configure the Avantis Trader SDK for use in your project, follow these steps:

Trading Configuration
----------------------
Used for opening trades and getting trade-related parameters.

1. Import the required modules and classes from the SDK:

   .. code-block:: python

      from avantis_trader_sdk import TraderClient, FeedClient
      from avantis_trader_sdk.types import TradeInput

2. Create an instance of the `TraderClient` class with the provider URL for the Base Mainnet Chain: https://docs.base.org/network-information/ or https://chainlist.org/chain/8453.

   .. code-block:: python

      provider_url = "https://sepolia.base.org"
      trader_client = TraderClient(provider_url)

The final file should look like this:

.. code-block:: python

   from avantis_trader_sdk import TraderClient, FeedClient
   from avantis_trader_sdk.types import TradeInput

   import avantis_trader_sdk

   # Trader client configuration (used for getting trade related parameters)
   provider_url = "https://sepolia.base.org" # Replace with the provider URL for the Base Mainnet Chain
   trader_client = TraderClient(provider_url)

Feed Configuration (Optional)
--------------------------
Used for getting real-time price updates. This step can be skipped if you don't need real-time price updates.

1. Create an instance of the `FeedClient` class with the WebSocket URL for real-time price feeds.

    **Parameters:**

    -  `ws_url` (str): The WebSocket URL for real-time price feeds.
    -  `on_error` (Callable, optional): A custom user-defined callback function to handle WebSocket errors.
    -  `on_close` (Callable, optional): A custom user-defined callback function to handle WebSocket close events.

   .. code-block:: python

      ws_url = "wss://<YOUR-WEBSOCKET-ENDPOINT>"

      feed_client = FeedClient(
          ws_url, on_error=ws_error_handler, on_close=ws_error_handler
      )

2. Register callbacks for price feed updates:

   You can register callbacks using either the feed ID or the pair name (e.g., "ETH/USD"). For more details on this method, see :meth:`~avantis_trader_sdk.feed.feed_client.FeedClient.register_price_feed_callback`.

   .. code-block:: python

      # Using feed ID
      # Get the feed ID from https://pyth.network/developers/price-feed-ids
      feed_client.register_price_feed_callback(
          # Feed ID for ETH/USD
          "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
          lambda data: print(data),
      )

      # Using pair name
      feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))


3. Start listening for price updates. For more details on this method, see :meth:`~avantis_trader_sdk.feed.feed_client.FeedClient.listen_for_price_updates`:

   .. code-block:: python

      await feed_client.listen_for_price_updates()

4. Define a handler for WebSocket errors:

   .. code-block:: python

      def ws_error_handler(e):
          print(f"Websocket error: {e}")
          # Trigger custom error handling logic here
          # For example, reconnect to the WebSocket server

With this configuration, you can now use the Avantis Trader SDK to interact with the Avantis platform, and receive real-time price updates.

The final file should look like this:

.. code-block:: python

   from avantis_trader_sdk import TraderClient, FeedClient
   from avantis_trader_sdk.types import TradeInput

   import avantis_trader_sdk

   # Trader client configuration (used for getting trade related parameters)
   provider_url = "https://sepolia.base.org" # Replace with the provider URL for the Base Mainnet Chain
   trader_client = TraderClient(provider_url)

   # Real-time price feed configuration (used for getting real-time prices of the pairs)
   # **This can be skipped if you don't need real-time price updates**
   ws_url = "wss://<YOUR-WEBSOCKET-ENDPOINT>"

   def ws_error_handler(e):
       print(f"Websocket error: {e}")

   feed_client = FeedClient(
       ws_url, on_error=ws_error_handler, on_close=ws_error_handler
   )

   feed_client.register_price_feed_callback(
       "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
       lambda data: print(data),
   )

   feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))

   await feed_client.listen_for_price_updates()

   def ws_error_handler(e):
       print(f"Websocket error: {e}")