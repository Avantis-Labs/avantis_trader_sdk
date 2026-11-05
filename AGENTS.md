# Veranta Trader SDK v2 - Codex Rules

## About This SDK
Official Python SDK for Veranta v2 - perpetuals on Base (8453). API-first
(HyperLiquid-style): NO ABIs, NO web3. Payloads come from the tx-builder API;
the SDK signs locally and submits via the Veranta relayer (default, gasless)
or the user's own RPC (direct mode).

User-facing docs live in docs/mintlify/ (source of truth; mirrored to the
avantis-python-sdk repo, see docs/mintlify/README.md for the sync). For
endpoint/unit/gotcha details, the docstrings in the modules below are the
reference.

## Core Patterns

### Async-first
```python
from veranta_sdk import AsyncVeranta
async with AsyncVeranta() as client:          # env: VERANTA_PRIVATE_KEY, VERANTA_TRADER_ADDRESS
    await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)
```
Sync facade: `Veranta()` (same surface, blocking).

### Namespaces
- client.trade    - opens/closes/limits/margin/increase/tpsl/twap/rfq
- client.account  - positions, allowance, delegation, approvals, claims
- client.markets  - pair catalog, prices, dynamic spread, candles
- client.info     - history, portfolio, referral stats, vault APY
- client.referral / client.lp - actions (caller-scoped; trader key only)
- veranta_sdk.compute  - pure UI-parity math (PnL, liq, validation)

### Execution routing (execution/engine.py): central routing base URL
Service URLs derive from api_base_url (prod-api/staging-api.veranta.xyz):
/core, /twap, /batched-market, /blitz, /data, /risk/v2 (the gateway also
routes /ws = iris, not consumed by the SDK).
- relayer mode + market open/close/increase (10 types) -> batched-market
  POST /market/execute-batched with a signed EIP-712 intent + an OPTIONAL
  pre-signed EIP-7702 type-4 tx (high-level flows send both for the
  server-side mechanism switch; intent-only is the MM fast path); lifecycle
  streamed back as SSE (incl. non-terminal AttemptFailed events; Error
  payloads carry a machine `code`), replayable via
  GET /tracking-id/{id}/status (execution/batched_market.py)
- global TP/SL (UpdateTpSlReq) -> signed intent PUT to the core API
  /price-triggers/global-{tp|sl}-{trader}-{pair}-{index} (userIntent +
  signedMessage); the backend executes executePositionUpdateBatched itself.
  Same path in relayer AND direct mode (no public contract entry point).
- relayer mode + everything else -> type-4 passthrough via blitz (SDK-built
  EIP-7702 smart-account tx via eip7702/account.py)
- TWAP open/close/cancel -> signed intents POSTed to the twap-app API
  (no relayer; responds {twapId, transactionHash} synchronously)
- direct mode -> EIP-1559 tx via rpc_url

## Critical Invariants (do not break)

1. Every signed intent MUST pass the digest assert (signing/intents.py).
   Golden vectors in tests/vectors/vectors.json prove all 17 intent kinds -
   tests/test_golden_vectors.py and test_local_intents.py must stay green.
2. EIP-7702 encoding (eip7702/account.py) is byte-for-byte compatible with
   @gelatocloud/gasless - tests/test_eip7702.py guards this.
3. intents_schema.py mirrors contracts SignatureHelpers.sol verbatim - never
   "normalize" field names (`_t`, `_deadline` vs `trader`, `nonce`).
4. deadline/deadlineMs = MILLISECONDS; delegate expiry = SECONDS.
5. Human units at the API boundary (100 = 100 USDC); send numbers as strings.
6. Referral/approve/claims/LP are msg.sender-scoped: blocked in delegate mode
   (delegatable=False guard in base_api.py).
7. TP/SL update is intent-only in v2; both global and partial TP/SL go
   through core API /price-triggers (ids are `entityId`; partial updates
   mint a NEW entityId, global ids are deterministic and stable).

## Base Denim (200 ms blocks, mainnet 2026-11-05 18:00 UTC)

- A block every 200 ms, whole-second block timestamps, no Flashblocks.
  Receipt polls match that: `JsonRpcClient.wait_for_receipt` defaults to
  0.25 s (`poll_s` overrides it). Do not put multi-second sleeps between a
  transaction (or an order) and its receipt; poll.
- `ExecutionConfirmedInFlashblock` (order events) is deprecated and never
  emitted again; `OrderEventStream` still forwards it if one arrives. Do not
  wait for it.
- `eth_getTransactionCount(..., "pending")` stays the default for nonces. It
  still works but no longer means preconfirmed: keep the default, and do not
  treat it as inclusion proof.
- `Trade.timestamp` is a whole second and can be shared by a close and a
  reopen of the same slot inside one second. Intents bound to it
  (`close_trade`, `close_trade_coin`, `partial_tp_sl` in
  execution/local_intents.py) must be re-requested after any same-second
  change; never cache a signed one.

## When Modifying
- Keep methods async; pydantic v2 models; typed errors from errors.py.
- Add an example for new features; update CHANGELOG.md and docs/mintlify/
  (then re-sync the avantis-python-sdk mirror).
- Run: pytest && ruff check --fix && mypy veranta_sdk
