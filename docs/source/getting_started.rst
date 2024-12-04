Getting Started
===============

Installation
------------

To get started with the Avantis Trader SDK, follow these steps to install the package:

1. Ensure you have Python 3.6 or later installed on your system.

2. Install the SDK using pip:

   .. code-block:: bash

      pip install avantis-trader-sdk

   or

   .. code-block:: bash

      pip install git+https://github.com/Avantis-Labs/avantis_trader_sdk.git

   Alternatively, if you have a local copy of the source:

   .. code-block:: bash

      git clone https://github.com/yourusername/avantis-trader-sdk.git
      cd avantis-trader-sdk
      pip install .

3. Verify the installation:

   .. code-block:: python

      import avantis_trader_sdk
      print(avantis_trader_sdk.__version__)

   If the installation was successful, this command should print the version number of the Avantis Trader SDK.

4. Get pair information:

   .. code-block:: python

      import asyncio
      from avantis_trader_sdk import TraderClient, __version__

      import avantis_trader_sdk

      print(avantis_trader_sdk.__version__)


      async def main():
         provider_url = "https://mainnet.base.org"
         trader_client = TraderClient(provider_url)

         print("----- GETTING PAIR INFO -----")
         result = await trader_client.pairs_cache.get_pairs_info()
         print(result)


      if __name__ == "__main__":
         asyncio.run(main())

   This command should print a list of trading pairs with their information available on the Avantis platform.

Next Steps
----------

Once you have installed the Avantis Trader SDK, you can start using it to interact with the Avantis platform. Here are some things you might want to do next:

- Explore the SDK's features and capabilities.
- Access real-time price feeds for various trading pairs.
- Integrate the SDK into your trading algorithms or DeFi applications.

For detailed usage instructions and examples, refer to the subsequent sections of this documentation.