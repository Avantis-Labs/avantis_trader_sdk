"""Bootstrap the SDK and inspect protocol metadata.

Environment (the default HyperLiquid-style setup):
    export AVANTIS_PRIVATE_KEY=0x...      # your API/agent key from the Avantis UI
    export AVANTIS_TRADER_ADDRESS=0x...   # your wallet address
    # optional: AVANTIS_NETWORK=testnet|mainnet (default testnet)
"""

import asyncio

from avantis_trader_sdk_v2 import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        meta = await client.meta()
        print("chainId:", meta["chainId"])
        print("tradingRouter:", meta["addresses"]["tradingRouter"])
        print("units:", meta["units"])
        print("defaults:", meta["defaults"])


if __name__ == "__main__":
    asyncio.run(main())
