FAQs
----

This section provides solutions to common issues you might encounter while using the Avantis Trader SDK.

**RPC gives 429 error**
   - This error indicates that you're being rate-limited by the RPC provider. Consider using a dedicated node or a different RPC provider with higher rate limits.

**Websocket refuses to connect**
   - Verify that your websocket URL is correct and that the websocket server is running and accessible. Check for any network issues that might be preventing the connection.

**Websocket gives a 200 response but handshake fails or unable to connect**
   - A 200 response typically indicates an HTTP connection rather than a websocket connection. Ensure that your endpoint is correct for websocket communication. You might need to add ``/ws`` at the end of your URL to specify a websocket endpoint.

If you encounter any other issues or have further questions, feel free to reach out to the Avantis support team or consult the official documentation for more information.