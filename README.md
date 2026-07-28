# Avantis Trader SDK v2

Python SDK for [Avantis](https://www.avantisfi.com) v2, leveraged perpetuals
on Base. API-first: no ABIs, no web3, no RPC required. The
SDK signs locally and everything else comes from Avantis services.

```python
import asyncio
from avantis_trader_sdk import AsyncAvantis

async def main():
    async with AsyncAvantis() as client:              # reads AVANTIS_* env vars
        await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
        positions = await client.account.positions()
        print(positions.positions)

asyncio.run(main())
```

## Install

```bash
pip install avantis-trader-sdk            # core
pip install "avantis-trader-sdk[kms]"     # + AWS KMS signing
pip install "avantis-trader-sdk[streams]" # + Socket.IO pair-data stream
```

Python 3.10+.

## Setup (default: gasless API key)

1. Create an **API key** with the
   [Avantis API Key Generator](https://avantis-delegate-ui.preview.avantisfi.link/).
   One wallet signature registers it
   as a trading delegate for your account (it can trade, but can never move
   funds to itself; payouts always go to your wallet).
2. Approve USDC once (prompted on the UI).
3. Configure:

```bash
export AVANTIS_PRIVATE_KEY=0x...      # the API key
export AVANTIS_TRADER_ADDRESS=0x...   # your wallet
```

(Or copy [`.env.example`](.env.example) to `.env`; it documents every
supported variable, including the optional ones.)

That's it. Every action is now a signed message relayed by Avantis. No gas,
no RPC, no ETH.

## Execution modes

Two independent axes; any combination works:

| | signer = API key (delegate) | signer = trader key |
|---|---|---|
| **relayer** (default, gasless) | sign intents, Avantis submits | same |
| **direct** (own RPC + ETH) | `delegatedAction`-wrapped txs | plain txs |

```bash
export AVANTIS_EXECUTION=direct       # opt into self-broadcasting
export AVANTIS_RPC_URL=https://...    # your Base RPC
```

Market makers can additionally use the **local intent builder**
(`client.local_intents()`) to build and sign orders with zero HTTP
round-trips on the hot path; see `examples/13_mm_fast_path.py`.

## What's covered

- **Trading**: market/limit opens (incl. coin-sized and zero-fee/PnL orders),
  partial/full closes, margin updates, position increases, TP/SL updates,
  partial TP/SL trigger orders, TWAP.
- **Account**: positions with liq price/rollover/funding, limit orders, TWAPs,
  balances, allowances, delegation management, USDC approvals, rebate and
  keeper-reward claims, builder codes.
- **Markets**: full 100+ pair catalog (funding rates, spreads, OI and caps,
  fees, leverage envelopes, market hours), live prices, dynamic spread,
  OHLCV candles.
- **Info**: trade/order history with full fee breakdowns, portfolio analytics
  (PnL, win rate, volume, fees), referral stats, vault APY.
- **Compute** (pure functions, UI parity): net PnL incl. ZFP fee tiers and
  loss protection, liquidation price, skew-adjusted open fees, maker/taker
  classification, OI headroom, TP/SL bounds, pre-trade validation.
- **Streams**: Lazer SSE + Pyth Hermes prices, pair-data updates, order
  execution events.
- **LP**: vault deposit/withdraw (ERC-4626), previews, utilization, APY.
- **Referral**: codes (incl. gasless registration), tiers, rebates.

## Correctness guarantees

- Every EIP-712 intent is **digest-verified locally** against the API before
  submission, so encoding drift fails loudly instead of reverting on-chain.
- The signing implementation is tested against **golden vectors computed by
  the actual on-chain hashing library** (all 15 intent types).
- The EIP-7702 relayer envelope is byte-for-byte compatible with the Avantis
  web app's implementation.

## Examples

See [`examples/`](examples/): one runnable script per flow, from
`01_configure_and_meta.py` to `18_sync_and_kms.py`.

## Errors

All failures raise typed exceptions from `avantis_trader_sdk.errors`:
`ValidationError` (pre-trade checks, human-readable), `RelayError`,
`DigestMismatchError`, `DelegationError`, `RateLimitedError`, `RpcError`, etc.

## Security model

The API/delegate key can trade on your account but **cannot** withdraw funds,
approve USDC, or add other delegates. Worst case for a leaked key is
malicious trading until you revoke it (`client.account.revoke_delegate`) or
it expires. Keep expiries short (90 days recommended) and never commit keys.

## Development

```bash
pip install -e ".[dev]"
pytest            # 80+ tests incl. golden vectors and EIP-7702 parity
ruff check .
mypy avantis_trader_sdk
```
