# Welcome to Avantis Trader SDK’s documentation!

Avantis Trader SDK is a powerful and flexible toolkit for trading on the Avantis platform. This documentation will guide you through the installation process, basic usage, and advanced features of the SDK.

## 📚 [Read the Full Documentation Here](https://sdk.avantisfi.com/)

Contents:

- [Introduction](#introduction)
  - [About Avantis](#about-avantis)
  - [Purpose of the Avantis Trader SDK](#purpose-of-the-avantis-trader-sdk)
- [Getting Started](#getting_started)
  - [Installation](#installation)
  - [Next Steps](#next-steps)
  - [Examples](#examples)

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
- Execute trades and manage positions on the Avantis platform.

Whether you are a developer building decentralized finance (DeFi) applications, a trader seeking to automate your strategies, or a market maker looking to optimize your operations, the Avantis Trader SDK offers the functionality you need to succeed in the rapidly evolving world of decentralized trading.

# Getting Started

## Installation

To get started with the Avantis Trader SDK, follow these steps to install the package:

1. Ensure you have Python 3.6 or later installed on your system.
2. Install the SDK using pip:

   ```bash
    pip install avantis-trader-sdk
   ```

   or

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

## Examples

You can find practical examples and sample code for using the Avantis Trader SDK in our GitHub repository. These examples are designed to help you get started quickly and explore the capabilities of the SDK.

📂 [Browse the Examples on GitHub](https://github.com/Avantis-Labs/avantis_trader_sdk/tree/main/examples)

## 📚 [Read the Full Documentation Here](https://sdk.avantisfi.com/)
