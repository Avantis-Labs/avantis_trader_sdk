"""Portfolio analytics and trade history (human units)."""

import asyncio

from avantis_trader_sdk import AsyncAvantis


async def main() -> None:
    async with AsyncAvantis() as client:
        trader = client.trade.trader

        fills = await client.info.trade_history(trader, page=0, limit=10)
        for t in fills.get("trades", []):
            print(
                f"{t['time']} {t['market']:10} {t['side']:5} {t['type']:14} "
                f"size={t['positionSize']:.2f} netPnl={t.get('netPnl') or 0:+.2f}"
            )

        pnl = await client.info.portfolio_pnl(trader)
        volume = await client.info.portfolio_volume(trader)
        win = await client.info.win_rate(trader)
        fees = await client.info.total_fees(trader)
        print("\npnl:", pnl, "\nvolume:", volume, "\nwin rate:", win, "\nfees:", fees)


if __name__ == "__main__":
    asyncio.run(main())
