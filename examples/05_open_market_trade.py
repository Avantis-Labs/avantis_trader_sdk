"""Open a market position: the default gasless relayer route.

The SDK fetches the intent from the tx-builder API, signs it locally (with a
digest correctness check), and queues it with the Avantis relayer. No RPC, no
ETH needed.

The order type routes from the pair: trade an Upside market (e.g.
"BTC_UPSIDE") and the SDK sends the PnL (Upside) order type automatically —
see examples/19_upside_pairs.py.

``on_event`` (optional) observes the order journey live while the SDK still
settles the outcome: the accepted event, retryable AttemptFailed diagnostics
(good debug logs — e.g. NO_PRICE, SPREAD_BLOCKED, or a contract error name),
and the terminal event, which is delivered even when the call raises.
"""

import asyncio

from avantis_trader_sdk import AsyncAvantis, BatchedMarketEvent


def journey(ev: BatchedMarketEvent) -> None:
    # sync or async callables both work; exceptions propagate
    code = ev.data.get("code")
    print(f"  [{ev.seq}] {ev.type}" + (f" code={code}" if code else ""))


async def main() -> None:
    async with AsyncAvantis() as client:
        receipt = await client.trade.market_open(
            "ETH/USD",
            "long",
            collateral=100,       # 100 USDC
            leverage=10,          # 10x
            take_profit=4000,     # optional; omit for none
            stop_loss=2800,       # optional
            slippage_percent=1,
            on_event=journey,     # optional: live lifecycle log
        )
        print("route:", receipt.route)
        print("tx:", receipt.tx_hash)
        # A confirmed tx != a filled trade: market orders are fulfilled by the
        # operator. Poll positions to see the fill:
        await asyncio.sleep(3)
        data = await client.account.positions()
        print("open positions:", len(data.positions))


if __name__ == "__main__":
    asyncio.run(main())
