# Welcome to Avantis Trader SDK’s documentation!

Avantis Trader SDK is a powerful and flexible toolkit for trading on the Avantis platform. This documentation will guide you through the installation process, basic usage, and advanced features of the SDK.

Contents:

- [Introduction](#introduction)
  - [About Avantis](#about-avantis)
  - [Purpose of the Avantis Trader SDK](#purpose-of-the-avantis-trader-sdk)
- [Getting Started](#getting_started)
  - [Installation](#installation)
  - [Next Steps](#next-steps)

* [Configuration](#configuration)

# Introduction

Welcome to the Avantis Trader SDK, a powerful tool designed to interact with the Avantis decentralized exchange (DEX) and leverage its advanced features for trading and market-making in cryptocurrencies, forex, and commodities.

## About Avantis

[Avantis](https://avantisfi.com/) is at the forefront of decentralized leveraged trading platforms, offering users the ability to take long or short positions in synthetic crypto, forex, and commodities using perpetuals—a financial instrument that provides leverage without an expiration date. With synthetic leverage and a USDC stablecoin liquidity pool, Avantis achieves high capital efficiency, enabling a diverse selection of tradable assets and leverage up to 100x.

The platform also introduces fine-grained risk management for liquidity providers (LPs) through time and risk parameters. This innovation allows any LP to become a sophisticated market maker for a wide range of derivatives, starting with perpetuals.

Read more about Avantis at [https://docs.avantisfi.com/](https://docs.avantisfi.com/).

## Purpose of the Avantis Trader SDK

The Avantis Trader SDK is designed to simplify and enhance the experience of interacting with the Avantis DEX. It provides developers and traders with a set of tools to:

- Access real-time price feeds for supported trading pairs.
- Retrieve and analyze key parameters for assets, categories, and trading strategies.
- Integrate live price updates into applications or trading algorithms.
- Execute trades and manage positions on the Avantis platform. (Coming soon)

Whether you are a developer building decentralized finance (DeFi) applications, a trader seeking to automate your strategies, or a market maker looking to optimize your operations, the Avantis Trader SDK offers the functionality you need to succeed in the rapidly evolving world of decentralized trading.

# Getting Started

## Installation

To get started with the Avantis Trader SDK, follow these steps to install the package:

1. Ensure you have Python 3.6 or later installed on your system.
2. Install the SDK using pip:

   ```bash
   pip install git+https://github.com/Avantis-Labs/avantis_trader_sdk.git
   ```

   Alternatively, if you have a local copy of the source:

   ```bash
   git clone https://github.com/yourusername/avantis-trader-sdk.git
   cd avantis-trader-sdk
   pip install .
   ```

3. Verify the installation:

   ```python
   import avantis_trader_sdk
   print(avantis_trader_sdk.__version__)
   ```

   If the installation was successful, this command should print the version number of the Avantis Trader SDK.

## Next Steps

Once you have installed the Avantis Trader SDK, you can start using it to interact with the Avantis platform. Here are some things you might want to do next:

- Explore the SDK’s features and capabilities.
- Access real-time price feeds for various trading pairs.
- Integrate the SDK into your trading algorithms or DeFi applications.

For detailed usage instructions and examples, refer to the subsequent sections of this documentation.

# Configuration

To configure the Avantis Trader SDK for use in your project, follow these steps:

1. Import the required modules and classes from the SDK:
   ```python
   from avantis_trader_sdk import TraderClient, FeedClient, __version__
   from avantis_trader_sdk.types import TradeInput
   ```
2. Print the version of the SDK to verify the installation (optional):
   ```python
   import avantis_trader_sdk
   print(avantis_trader_sdk.__version__)
   ```
3. Create an instance of the TraderClient class with the provider URL for the [https://docs.base.org/network-information/](base mainnet network).
   ```python
   provider_url = "https://mainnet.base.org"
   trader_client = TraderClient(provider_url)
   ```
4. Create an instance of the FeedClient class with the WebSocket URL for real-time price feeds.
   > **Parameters:**
   >
   > - ws_url (str): The WebSocket URL for real-time price feeds.
   > - on_error (Callable, optional): A callback function to handle WebSocket errors.
   > - on_close (Callable, optional): A callback function to handle WebSocket close events.
   ```python
   ws_url = "wss://<YOUR-WEBSOCKET-ENDPOINT>"
   feed_client = FeedClient(
       ws_url, on_error=ws_error_handler, on_close=ws_error_handler
   )
   ```
5. Register callbacks for price feed updates:

   You can register callbacks using either the feed ID or the pair name (e.g., “ETH/USD”).

   ```python
   # Using feed ID
   feed_client.register_price_feed_callback(
       # Feed ID for ETH/USD
       "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
       lambda data: print(data),
   )

   # Using pair name
   feed_client.register_price_feed_callback("ETH/USD", lambda data: print(data))
   ```

6. Start listening for price updates:
   ```python
   await feed_client.listen_for_price_updates()
   ```
7. Define a handler for WebSocket errors:
   ```python
   def ws_error_handler(e):
       print(f"Websocket error: {e}")
   ```

With this configuration, you can now use the Avantis Trader SDK to interact with the Avantis platform, and receive real-time price updates.
