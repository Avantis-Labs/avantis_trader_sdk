import json
import websockets
from pathlib import Path
from ..types import PriceFeedResponse


class FeedClient:
    """
    Client for interacting with the Pyth price feed websocket.
    """

    def __init__(self, ws_url, on_error=None, on_close=None):
        """
        Constructor for the FeedClient class.

        Args:
            ws_url: The websocket URL to connect to.
            on_error: Optional callback for handling websocket errors.
            on_close: Optional callback for handling websocket close events.
        """
        if not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
            raise ValueError("ws_url must start with ws:// or wss://")

        self.ws_url = ws_url
        self.pair_feeds = {}
        self.feed_pairs = {}
        self.price_feed_callbacks = {}
        self._socket = None
        self._connected = False
        self._on_error = on_error
        self._on_close = on_close
        self._load_pair_feeds()

    async def listen_for_price_updates(self):
        """
        Listens for price updates from the Pyth price feed websocket.
        When a price update is received, the registered callbacks will
        be called with the updated price feed data.

        Raises:
            Exception: If an error occurs while listening for price updates.
        """
        try:
            async with websockets.connect(self.ws_url) as websocket:
                self._socket = websocket
                self._connected = True
                await websocket.send(
                    json.dumps(
                        {
                            "type": "subscribe",
                            "ids": list(self.price_feed_callbacks.keys()),
                        }
                    )
                )
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if data["type"] == "price_update":
                            price_feed_id = data["price_feed"]["id"]
                            if price_feed_id in self.price_feed_callbacks:
                                pair_string = self.get_pair_from_feed_id(price_feed_id)
                                data["price_feed"]["pair"] = pair_string
                                for callback in self.price_feed_callbacks[
                                    price_feed_id
                                ]:
                                    callback(PriceFeedResponse(**data["price_feed"]))
                    except websockets.exceptions.ConnectionClosed as e:
                        if self.on_close:
                            self.on_close(e)
                        else:
                            print(f"Connection closed with error: {e}")
                        break
                    except Exception as e:
                        if self.on_error:
                            self.on_error(e)
                        else:
                            raise e
        except Exception as e:
            if self.on_error:
                self.on_error(e)
            else:
                raise e

    def _load_pair_feeds(self):
        """
        Loads the pair feeds from the json file.
        """
        feed_path = Path(__file__).parent / "feedIds.json"
        with open(feed_path) as feed_file:
            self.pair_feeds = json.load(feed_file)
            self.feed_pairs = {v["id"]: k for k, v in self.pair_feeds.items()}

    def get_pair_from_feed_id(self, feed_id):
        """
        Retrieves the pair string from the feed id.

        Args:
            feed_id: The feed id to retrieve the pair string for.

        Returns:
            The pair string.
        """
        if not feed_id.startswith("0x"):
            feed_id = "0x" + feed_id
        return self.feed_pairs.get(feed_id)

    def register_price_feed_callback(self, identifier, callback):
        """
        Registers a callback for price feed updates.

        Args:
            identifier: The identifier of the price feed to register the callback for.
            callback: The callback to register.

        Raises:
            ValueError: If the identifier is unknown.
        """
        if identifier in self.pair_feeds:
            price_feed_id = self.pair_feeds[identifier]["id"]
        elif identifier in self.feed_pairs:
            price_feed_id = identifier
        elif identifier in self.price_feed_callbacks:
            price_feed_id = identifier
        else:
            raise ValueError(f"Unknown identifier: {identifier}")

        if price_feed_id.startswith("0x"):
            price_feed_id = price_feed_id[2:]

        if price_feed_id not in self.price_feed_callbacks:
            self.price_feed_callbacks[price_feed_id] = []
        self.price_feed_callbacks[price_feed_id].append(callback)

    def unregister_price_feed_callback(self, identifier, callback):
        """
        Unregisters a callback for price feed updates.

        Args:
            identifier: The identifier of the price feed to unregister the callback for.
            callback: The callback to unregister.
        """
        if identifier in self.pair_feeds:
            price_feed_id = self.pair_feeds[identifier]["id"]
        else:
            price_feed_id = identifier

        if price_feed_id in self.price_feed_callbacks:
            self.price_feed_callbacks[price_feed_id].remove(callback)
            if not self.price_feed_callbacks[price_feed_id]:
                del self.price_feed_callbacks[price_feed_id]
