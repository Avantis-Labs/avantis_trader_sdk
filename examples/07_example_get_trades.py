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
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    # Get open and pending trades
    trades, pendingOpenLimitOrders = await trader_client.trade.get_trades(trader)
    print("Trades: ", trades)
    print("Pending Open Limit Orders: ", pendingOpenLimitOrders)


if __name__ == "__main__":
    asyncio.run(main())
