import asyncio
import os

from avantis_trader_sdk import FeedClient, TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

RPC_URL = "https://base-testnet-rpc-ovh.avantisfi.com/"

# Fork charges ~253 wei/gas + an L1 data fee; wallet only holds dust ETH,
# so pin fees near the base fee instead of web3's 0.001 gwei tip default.
MAX_FEE_PER_GAS = 10_000
MAX_PRIORITY_FEE_PER_GAS = 1
EXECUTION_FEE_ETH = 2e-9  # 2 gwei, keeper fee budget on the fork


def load_key():
    key = os.environ.get("KEY")
    if not key:
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("KEY not found in env or .env")
    return key


def cheapen(tx):
    tx.pop("gasPrice", None)
    tx["maxFeePerGas"] = MAX_FEE_PER_GAS
    tx["maxPriorityFeePerGas"] = MAX_PRIORITY_FEE_PER_GAS
    return tx


async def get_btc_trades(trader_client, trader, pair_index):
    trades, _ = await trader_client.trade.get_trades(trader, use_api=False)
    return [t for t in trades if t.trade.pair_index == pair_index]


async def main():
    private_key = load_key()

    trader_client = TraderClient(RPC_URL)
    trader_client.set_local_signer(private_key)
    trader = trader_client.get_signer().get_ethereum_address()
    print(f"Trader: {trader}")

    balance = await trader_client.get_usdc_balance(trader)
    print(f"USDC balance: {balance}")

    collateral = 5
    leverage = 50

    allowance = await trader_client.get_usdc_allowance_for_trading(trader)
    print(f"USDC allowance: {allowance}")
    if allowance < collateral:
        print("Approving USDC...")
        await trader_client.approve_usdc_for_trading(collateral)

    pair_index = await trader_client.pairs_cache.get_pair_index("BTC/USD")
    print(f"BTC/USD pair index: {pair_index}")

    feed_client = FeedClient()
    lazer_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index)
    price_data = await feed_client.get_latest_lazer_price([lazer_id])
    btc_price = price_data.price_feeds[0].converted_price
    print(f"BTC price: {btc_price}")

    trade_input = TradeInput(
        trader=trader,
        open_price=None,
        pair_index=pair_index,
        collateral_in_trade=collateral,
        is_long=True,
        leverage=leverage,
        index=0,
        tp=round(btc_price * 1.05, 2),
        sl=0,
        timestamp=0,
    )

    open_tx = await trader_client.trade.build_trade_open_tx(
        trade_input,
        TradeInputOrderType.MARKET,
        slippage_percentage=1,
        execution_fee=EXECUTION_FEE_ETH,
    )
    receipt = await trader_client.sign_and_get_receipt(cheapen(open_tx))
    print(
        f"OPEN tx: {receipt['transactionHash'].hex()} status={receipt['status']} "
        f"gasUsed={receipt['gasUsed']}"
    )

    btc_trades = []
    for i in range(12):
        await asyncio.sleep(5)
        btc_trades = await get_btc_trades(trader_client, trader, pair_index)
        print(f"  poll {i + 1}: {len(btc_trades)} open BTC trade(s)")
        if btc_trades:
            break

    if not btc_trades:
        print("Trade was not executed (no open BTC position found). Stopping.")
        return

    t = btc_trades[-1].trade
    print(
        f"Open trade: pair={t.pair_index} index={t.trade_index} "
        f"collateral={t.open_collateral} lev={t.leverage} open_price={t.open_price} "
        f"tp={t.tp}"
    )

    close_tx = await trader_client.trade.build_trade_close_tx(
        pair_index=t.pair_index,
        trade_index=t.trade_index,
        collateral_to_close=t.open_collateral,
        trader=trader,
        execution_fee=EXECUTION_FEE_ETH,
    )
    receipt = await trader_client.sign_and_get_receipt(cheapen(close_tx))
    print(
        f"CLOSE tx: {receipt['transactionHash'].hex()} status={receipt['status']} "
        f"gasUsed={receipt['gasUsed']}"
    )

    for i in range(12):
        await asyncio.sleep(5)
        btc_trades = await get_btc_trades(trader_client, trader, pair_index)
        print(f"  poll {i + 1}: {len(btc_trades)} open BTC trade(s)")
        if not btc_trades:
            break

    print(f"Remaining BTC trades after close: {len(btc_trades)}")
    balance = await trader_client.get_usdc_balance(trader)
    print(f"Final USDC balance: {balance}")


if __name__ == "__main__":
    asyncio.run(main())
