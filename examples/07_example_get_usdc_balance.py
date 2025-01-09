import asyncio

from avantis_trader_sdk import TraderClient

# Trader's wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
trader = "0xmywalletaddress"


# We will first prepare trade input, then open a trade, get opened trade's info and finally close the trade
async def main():
    # Initialize TraderClient
    provider_url = "https://sepolia.base.org"  # Find provider URL for Base Mainnet Chain from https://chainlist.org/chain/8453 or use a dedicated node (Alchemy, Infura, etc.)
    trader_client = TraderClient(provider_url)

    # Get trader's USDC balance
    balance = await trader_client.get_usdc_balance(trader)
    print(f"Balance of {trader} is {balance} USDC")


if __name__ == "__main__":
    asyncio.run(main())
