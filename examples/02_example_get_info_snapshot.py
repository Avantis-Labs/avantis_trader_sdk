import asyncio
from avantis_trader_sdk import TraderClient, __version__

import avantis_trader_sdk

print(avantis_trader_sdk.__version__)


async def main():
    provider_url = "https://sepolia.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    print("----- GETTING SNAPSHOT -----")
    result = await trader_client.snapshot.get_snapshot()
    print(result)

    # Optionally, you can convert the result to a JSON string
    # json_response = json.dumps(result, default=lambda x: x.__dict__)
    # print(json_response)


if __name__ == "__main__":
    asyncio.run(main())
