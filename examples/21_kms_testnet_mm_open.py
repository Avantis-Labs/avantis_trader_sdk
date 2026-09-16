"""Testnet MM fast path: KMS trader EOA opens a BTC market order.

The KMS key *is* the trader (no ``trader_address``, no delegate). The order
is built and signed locally and submitted intent-only, no EIP-7702 leg.

Requires ``pip install 'veranta-sdk[kms]'`` and AWS credentials
(default: profile ``skords``, key ``alias/testnet/mm-avantis``).
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from veranta_sdk import AsyncVeranta, BatchedMarketEvent
from veranta_sdk.errors import RelayError
from veranta_sdk.signing import KmsSigner
from veranta_sdk.types import AggregatorOrderType

os.environ.setdefault("AWS_PROFILE", "skords")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

KMS_KEY_ID = "alias/testnet/mm-avantis"
# Testnet rpc-proxy (EIP-7702 nonce for USDC approve; not used on the hot path).
RPC_URL = "https://devnet-rpc.veranta.xyz"

PAIR = "BTC/USD"
COLLATERAL_USDC = 300  # positionSizeUSDC = collateral, not notional
LEVERAGE = 20
SLIPPAGE_PERCENT = 5


def journey(ev: BatchedMarketEvent) -> None:
    code = ev.data.get("code")
    print(f"  [{ev.seq}] {ev.type}" + (f" code={code}" if code else ""))


async def ensure_usdc_approval(client: AsyncVeranta, needed: Decimal) -> Decimal:
    info = await client.account.allowance()
    balance = Decimal(str(info.get("balanceUsdc") or 0))
    allowance = Decimal(str(info.get("allowanceUsdc") or 0))
    print(f"USDC balance={balance}  allowance={allowance}")
    if allowance < needed:
        print("approving unlimited USDC to TradingStorage...")
        receipt = await client.account.approve_usdc()
        print("approve", receipt.route, receipt.tx_hash)
        info = await client.account.allowance()
        allowance = Decimal(str(info.get("allowanceUsdc") or 0))
        print(f"allowance after={allowance}")
    return balance


async def main() -> None:
    signer = KmsSigner(KMS_KEY_ID, region_name="us-east-1")
    async with AsyncVeranta(
        signer=signer,
        network="testnet",
        rpc_url=RPC_URL,
        # no trader_address: the KMS wallet is the trader
    ) as client:
        trader = client.trade.trader
        print("trader", trader)
        assert trader.lower() == signer.address.lower(), "signer must be the trader"

        btc = await client.markets.pair(PAIR)
        if not (btc.leverages.min_leverage <= LEVERAGE <= btc.leverages.max_leverage):
            raise SystemExit(
                f"leverage {LEVERAGE} outside {btc.leverages.min_leverage}-"
                f"{btc.leverages.max_leverage} on {btc.symbol}"
            )

        notional = Decimal(COLLATERAL_USDC) * Decimal(LEVERAGE)
        if notional < Decimal(str(btc.min_lev_pos_usdc)):
            raise SystemExit(
                f"notional {notional} below minLevPosUSDC {btc.min_lev_pos_usdc}"
            )

        balance = await ensure_usdc_approval(client, Decimal(COLLATERAL_USDC))
        if balance < Decimal(COLLATERAL_USDC):
            raise SystemExit(
                f"insufficient USDC: have {balance}, need >= {COLLATERAL_USDC} "
                f"collateral (plus open fee) on {trader}"
            )

        price = await client.markets.price(PAIR)
        print(
            f"{btc.symbol} index={btc.index} live_price={price} "
            f"collateral={COLLATERAL_USDC} leverage={LEVERAGE}x "
            f"slippage={SLIPPAGE_PERCENT}%"
        )

        builder = await client.local_intents()
        payload = builder.open_trade(
            trader=trader,
            pair_index=btc.index,
            is_long=True,
            collateral_usdc=COLLATERAL_USDC,
            leverage=LEVERAGE,
            open_price=price,
            slippage_percent=SLIPPAGE_PERCENT,
        )
        print("submitting intent-only (MM fast path)")
        try:
            receipt = await client.engine.submit_intent_batch(
                payload,
                AggregatorOrderType.MARKET_OPEN,
                wait=True,
                on_event=journey,
            )
        except RelayError as exc:
            print("order failed:", exc)
            if getattr(exc, "code", None):
                print("code", exc.code)
            raise

        print("route", receipt.route)
        print("tx", receipt.tx_hash)
        print("tracking_id", receipt.tracking_id)
        print("order_id", receipt.order_id)

        data = await client.account.positions()
        print("open positions", len(data.positions))
        for pos in data.positions:
            print(
                f"  pair={pos.pair_index} idx={pos.index} {pos.side} "
                f"collat={pos.collateral} lev={pos.leverage} "
                f"notional={pos.position_size} px={pos.open_price}"
            )


if __name__ == "__main__":
    asyncio.run(main())
