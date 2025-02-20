import asyncio

from avantis_trader_sdk import TraderClient

# Trader's private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own private key
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
private_key = "0xmyprivatekey"


async def main():
    # Initialize TraderClient
    provider_url = "https://mainnet.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # Set local signer
    trader_client.set_local_signer(
        private_key
    )  # Alternatively, you can use set_aws_kms_signer() to use a key from AWS KMS or create your own signer by inheriting BaseSigner class

    trader = trader_client.get_signer().get_ethereum_address()

    # Check allowance of USDC
    allowance = await trader_client.get_usdc_allowance_for_trading()
    print(f"Allowance of {trader} is {allowance} USDC")

    # Approve USDC for trading
    await trader_client.approve_usdc_for_trading(1000000)

    allowance = await trader_client.get_usdc_allowance_for_trading()
    print(f"New allowance of {trader} is {allowance} USDC")


if __name__ == "__main__":
    asyncio.run(main())
