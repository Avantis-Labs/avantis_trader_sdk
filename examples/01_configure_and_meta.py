"""Bootstrap the SDK and inspect protocol metadata.

Environment (the default setup):
    export VERANTA_PRIVATE_KEY=0x...      # your API/agent key from the Veranta UI
    export VERANTA_TRADER_ADDRESS=0x...   # your wallet address
    # optional: VERANTA_NETWORK=mainnet|testnet (default mainnet)
"""

import asyncio

from veranta_sdk import AsyncVeranta


async def main() -> None:
    async with AsyncVeranta() as client:
        meta = await client.meta()
        print("chainId:", meta["chainId"])
        print("tradingRouter:", meta["addresses"]["tradingRouter"])
        print("units:", meta["units"])
        print("defaults:", meta["defaults"])


if __name__ == "__main__":
    asyncio.run(main())
