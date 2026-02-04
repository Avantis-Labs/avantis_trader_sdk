# Avantis Trader SDK

Python SDK for trading on [Avantis](https://avantisfi.com/) - a perpetual trading platform on Base.

## Installation

```bash
pip install avantis-trader-sdk
```

## Quick Start

```python
import asyncio
from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

async def main():
    # Initialize client
    trader_client = TraderClient("https://mainnet.base.org")
    trader_client.set_local_signer("0xYOUR_PRIVATE_KEY")
    
    trader = trader_client.get_signer().get_ethereum_address()
    
    # Check and approve USDC allowance
    allowance = await trader_client.get_usdc_allowance_for_trading(trader)
    if allowance < 100:
        await trader_client.approve_usdc_for_trading(100)
    
    # Open a 10x long ETH position with $100 collateral
    trade_input = TradeInput(
        trader=trader,
        pair_index=1,  # ETH/USD
        collateral_in_trade=100,
        is_long=True,
        leverage=10,
        tp=5000,  # take profit
        sl=2500,  # stop loss
    )
    
    tx = await trader_client.trade.build_trade_open_tx(
        trade_input, TradeInputOrderType.MARKET, slippage_percentage=1
    )
    receipt = await trader_client.sign_and_get_receipt(tx)
    print("Trade opened!", receipt.transactionHash.hex())

asyncio.run(main())
```

## Get Open Trades

```python
trades, pending_orders = await trader_client.trade.get_trades(trader)

for trade in trades:
    print(f"Pair: {trade.trade.pair_index}, Leverage: {trade.trade.leverage}x")
    print(f"Entry: {trade.trade.open_price}, Liq: {trade.liquidation_price}")
```

## Close a Trade

```python
trade = trades[0]
close_tx = await trader_client.trade.build_trade_close_tx(
    pair_index=trade.trade.pair_index,
    trade_index=trade.trade.trade_index,
    collateral_to_close=trade.trade.collateral_in_trade,
    trader=trader,
)
await trader_client.sign_and_get_receipt(close_tx)
```

## AI-Assisted Development

Building with AI tools? We provide optimized documentation:

- [AGENT.md](./AGENT.md) - Comprehensive guide for AI agents. Copy to your project or paste into AI chat.
- [.cursorrules](./.cursorrules) - Auto-loaded by Cursor IDE.

```bash
curl -o AGENT.md https://raw.githubusercontent.com/Avantis-Labs/avantis_trader_sdk/main/AGENT.md
```

## Resources

- [Documentation](https://sdk.avantisfi.com/)
- [Examples](https://github.com/Avantis-Labs/avantis_trader_sdk/tree/main/examples)
- [Avantis Docs](https://docs.avantisfi.com/)

## License

MIT
