# Changelog

## 2.0.0a1 (unreleased)

Ground-up rewrite for Avantis v2. **Breaking: the 1.x API is removed.**

### Packaging

- Import / distribution name is now `avantis_trader_sdk_v2` /
  `avantis-trader-sdk-v2` (was `avantis_trader_sdk` / `avantis-trader-sdk`).

### Architecture

- API-first: all transaction payloads (calldata and EIP-712 intents) come from
  the Avantis tx-builder API. No vendored ABIs, no web3 dependency.
- Two execution routes: gasless **relayer** (default; signed intents + EIP-7702
  smart-account envelope queued with the Avantis relayer) and **direct**
  (self-signed EIP-1559 txs via your RPC or the tx-builder raw relay).
- Delegate ("API key") and trader-key signer identities, freely combined with
  either route. HyperLiquid-style env config
  (`AVANTIS_PRIVATE_KEY` / `AVANTIS_TRADER_ADDRESS` / `AVANTIS_EXECUTION`).
- Async-first (`AsyncAvantis`) with a synchronous facade (`Avantis`).

### New in v2

- Full v2 trading surface: coin-sized opens/closes, zero-fee (PnL) orders,
  position increases, partial TP/SL trigger orders (off-chain stored), TWAP.
  (RFQ methods exist in the client but the product is not live yet —
  undocumented on purpose.)
- Local intent builder + nonce pool for market makers (zero HTTP on the hot
  path), validated against on-chain golden vectors.
- Markets snapshot models for the 100+ pair catalog; UI-parity compute layer
  (net PnL with ZFP tiers and loss protection, liquidation price, skew fees,
  maker/taker, OI headroom, pre-trade validation).
- Portfolio/history/referral/vault analytics clients.
- Streams: Lazer SSE + Pyth Hermes prices, Socket.IO pair data, Pusher order
  execution events.
- LP (ERC-4626 tranche) and referral namespaces, builder codes, claims.
- Typed error taxonomy; digest verification on every signed intent.
- AWS KMS signer (optional extra), EIP-7702 authorization support.

### Fixes from live testnet E2E (2026-07-16)

- `market_open_coin` / `increase_position_coin` now take the contract-required
  `leverage` (target fill leverage) in addition to the min/max bounds; calls
  without it were rejected by the tx-builder.
- Markets snapshot: `GroupInfo` now reads the live `groupMaxOI` / `groupOI`
  fields (compute OI-headroom / `validate_order` previously saw zero group
  headroom and rejected valid orders).
- Lazer SSE stream: feed-v3 sends `timestampUs` as a string — price updates no
  longer crash the callback loop.

### Docs

- Complete Mintlify docs site (docs/mintlify): 20 pages covering the full SDK
  surface — getting started (configuration, core concepts), trading (market,
  limit, TP/SL, margin/size, TWAP), account & portfolio (positions, analytics,
  delegates, approvals), data & compute, LP vault, referrals, and advanced
  (execution modes, MM fast path, security model, error taxonomy).
- MM fast path ("Settling relays") + example 13: after `wait=False`, reconcile
  queued relays by `request_id` via `engine.relayer.wait()` / `.status()` —
  a queued relay can still revert or time out.

### Testing

- Golden-vector suite covering all 15 intent types (digests computed by the
  real on-chain SignatureHelpers library).
- Byte-for-byte EIP-7702/Gelato encoding parity with the Avantis web app.
- Markets models validated against a real 112-pair testnet snapshot.
