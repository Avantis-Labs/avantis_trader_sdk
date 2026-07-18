"""Open positions with live unrealized PnL (UI-parity math)."""

import asyncio

from avantis_trader_sdk_v2 import AsyncAvantis
from avantis_trader_sdk_v2.compute import position_net_pnl


async def main() -> None:
    async with AsyncAvantis() as client:
        data = await client.account.positions()
        print(f"{len(data.positions)} positions, {len(data.limit_orders)} limit orders\n")

        for pos in data.positions:
            pair = await client.markets.pair(pos.pair_index)
            price = await client.markets.price(pos.pair_index)
            pnl = position_net_pnl(pos, pair, price)
            print(
                f"{pair.symbol:10} {pos.side:5} {float(pos.leverage):.0f}x "
                f"collateral={float(pos.collateral):.2f} entry={float(pos.open_price):.2f} "
                f"liq={float(pos.liquidation_price):.2f} net_pnl={pnl.net:+.2f} "
                f"(gross {pnl.gross:+.2f}, fees {pnl.closing_fee + pnl.rollover_fee + pnl.funding_fee:.2f})"
            )


if __name__ == "__main__":
    asyncio.run(main())
