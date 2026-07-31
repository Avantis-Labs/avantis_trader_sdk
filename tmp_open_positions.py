import asyncio
import os

from avantis_trader_sdk import FeedClient, TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

RPC_URL = "https://base-testnet-rpc-ovh.avantisfi.com/"

# Fork charges ~253 wei/gas + an L1 data fee; wallet only holds dust ETH,
# so pin fees near the base fee instead of web3's 0.001 gwei tip default.
MAX_FEE_PER_GAS = 10_000
MAX_PRIORITY_FEE_PER_GAS = 1
EXECUTION_FEE_ETH = 2e-9

COLLATERAL = 5
LEVERAGE = 50


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


async def get_price(trader_client, feed_client, pair_index):
    lazer_id = await trader_client.pairs_cache.get_lazer_feed_id(pair_index)
    data = await feed_client.get_latest_lazer_price([lazer_id])
    return data.price_feeds[0].converted_price


async def count_open(trader_client, trader, pair_index):
    trades, _ = await trader_client.trade.get_trades(trader, use_api=False)
    return len([t for t in trades if t.trade.pair_index == pair_index])


async def open_position(
    trader_client, feed_client, trader, pair, is_long, order_type, leverage
):
    pair_index = await trader_client.pairs_cache.get_pair_index(pair)
    price = await get_price(trader_client, feed_client, pair_index)
    tp = round(price * (1.05 if is_long else 0.95), 2)
    index = await count_open(trader_client, trader, pair_index)

    trade_input = TradeInput(
        trader=trader,
        open_price=None,
        pair_index=pair_index,
        collateral_in_trade=COLLATERAL,
        is_long=is_long,
        leverage=leverage,
        index=index,
        tp=tp,
        sl=0,
        timestamp=0,
    )

    label = f"{pair} {'LONG' if is_long else 'SHORT'} {leverage}x {order_type.name}"
    tx = await trader_client.trade.build_trade_open_tx(
        trade_input, order_type, slippage_percentage=1, execution_fee=EXECUTION_FEE_ETH
    )
    receipt = await trader_client.sign_and_get_receipt(cheapen(tx))
    print(f"{label}: tx {receipt['transactionHash'].hex()} status={receipt['status']}")

    for _ in range(12):
        await asyncio.sleep(5)
        if await count_open(trader_client, trader, pair_index) > index:
            print(f"{label}: executed (trade index {index})")
            return True
    print(f"{label}: NOT executed after 60s")
    return False


async def main():
    trader_client = TraderClient(RPC_URL)
    trader_client.set_local_signer(load_key())
    trader = trader_client.get_signer().get_ethereum_address()
    feed_client = FeedClient()
    print(f"Trader: {trader}")
    print(f"USDC balance: {await trader_client.get_usdc_balance(trader)}")

    btc_index = await trader_client.pairs_cache.get_pair_index("BTC/USD")
    btc_info = (await trader_client.pairs_cache.get_pairs_info())[btc_index]
    lev = btc_info.leverages
    zfp_leverage = max(lev.pnl_min_leverage, min(LEVERAGE, lev.pnl_max_leverage))
    print(
        f"BTC pnl leverage bounds: {lev.pnl_min_leverage}-{lev.pnl_max_leverage}, "
        f"using {zfp_leverage}x for ZFP"
    )

    await open_position(
        trader_client, feed_client, trader,
        "BTC/USD", True, TradeInputOrderType.MARKET, LEVERAGE,
    )
    await open_position(
        trader_client, feed_client, trader,
        "ETH/USD", False, TradeInputOrderType.MARKET, LEVERAGE,
    )
    await open_position(
        trader_client, feed_client, trader,
        "BTC/USD", True, TradeInputOrderType.MARKET_ZERO_FEE, zfp_leverage,
    )

    trades, _ = await trader_client.trade.get_trades(trader, use_api=False)
    print(f"\nOpen positions ({len(trades)}):")
    for t in trades:
        tr = t.trade
        print(
            f"  pair={tr.pair_index} index={tr.trade_index} "
            f"{'LONG' if tr.is_long else 'SHORT'} lev={tr.leverage} "
            f"collateral={tr.open_collateral} open_price={tr.open_price} "
            f"tp={tr.tp} zfp={t.is_zfp}"
        )
    print(f"Final USDC balance: {await trader_client.get_usdc_balance(trader)}")


if __name__ == "__main__":
    asyncio.run(main())
