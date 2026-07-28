"""Bring-your-own delegate (API key) onboarding.

Normally you create an API key on the Avantis API Key Generator
(https://avantis-delegate-ui.preview.avantisfi.link/): one wallet signature,
gasless. This example shows the SDK-assisted equivalent for users who
generate their own delegate keypair. The trader key is used ONCE for the
DelegateReq signature and must not be persisted.
"""

import asyncio
import time

from eth_account import Account

from avantis_trader_sdk import AsyncAvantis, LocalSigner


async def main() -> None:
    trader_key = "0xTRADER_PRIVATE_KEY"       # used transiently, never stored
    delegate = Account.create()               # fresh agent keypair
    print("new delegate:", delegate.address)
    print("store this as AVANTIS_PRIVATE_KEY:", delegate.key.hex())

    trader_signer = LocalSigner(trader_key)
    async with AsyncAvantis(
        private_key=delegate.key.hex(),
        trader_address=trader_signer.address,
    ) as client:
        # 1. one-time USDC approval must come from the trader itself
        allowance = await client.account.allowance()
        print("allowance:", allowance)

        # 2. register the delegate (trader signs; submission is gasless)
        await client.account.register_delegate(
            delegate.address,
            expiry_seconds=int(time.time()) + 90 * 24 * 3600,  # 90 days
            trader_signer=trader_signer,
        )

        # 3. verify: fails fast with a clear error if not authorized
        status = await client.account.delegation_status()
        print("delegation:", status)

        # revoke later with: await client.account.revoke_delegate(delegate.address)
        # (must run with the trader key; kills in-flight intents immediately)


if __name__ == "__main__":
    asyncio.run(main())
