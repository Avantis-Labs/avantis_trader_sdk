# Changelog

## 2.0.0a1 (unreleased)

Ground-up rewrite for Avantis v2. **Breaking: the 1.x API is removed.**

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
- `Position.size_in_asset`: position size in the base asset
  (collateral × leverage ÷ open price; for USD-base pairs like USD/JPY the
  USDC notional is returned as-is). `account.positions()` tags each position
  with `base_symbol` from the markets pair catalog to support this.

### Unreleased additions (2026-07-28) — backend alignment

Aligns the SDK with the new Avantis backend topology (central routing,
batched-market execution, twap-app, off-chain order CRUD).

- **Central routing**: service URLs now derive from a single
  `api_base_url` (`https://prod-api.avantisfi.com` mainnet /
  `https://staging-api.avantisfi.com` testnet): `{base}/core`,
  `{base}/twap`, `{base}/batched-market`, `{base}/blitz`. New config fields
  `api_base_url`, `twap_api_url`, `batched_market_url` with
  `AVANTIS_API_BASE_URL` / `AVANTIS_TWAP_API_URL` /
  `AVANTIS_BATCHED_MARKET_URL` env overrides; individual URL overrides still
  win over derivation.
- **Batched-market execution** (new `execution/batched_market.py`): market
  opens/closes/increases (10 order types) now go to
  `POST {batched-market}/market/execute-batched`, which requires BOTH a
  signed EIP-712 intent and a pre-signed EIP-7702 type-4 transaction per
  order (server-side mechanism switch, no client release needed). The order
  lifecycle streams back as SSE (`MarketOrderAccepted` -> initiation ->
  terminal); a dropped stream is recovered via
  `GET /tracking-id/{id}/status?afterSeq=`. `ExecutionReceipt` gains
  `tracking_id` (lifecycle replay id) and `order_id` (on-chain id), and a new
  `batched-market` route label. `MarketOrderCanceled` (tx landed, fill
  declined — e.g. slippage) raises `RelayError`.
- **Blitz relayer scope narrowed**: `UPDATE_SL` (excluded from the
  batched-market allow-list) keeps the locally-encoded
  `executePositionUpdateBatched` + blitz type-2 relay; limit orders, margin,
  claims etc. keep the type-4 passthrough.
- **TWAP rework** (twap-app API): `twap_open` / `twap_close` sign the
  tx-builder intent and POST it to `{twap}/twaps/open|close`; the twap-app
  sends the tx itself and responds synchronously with
  `{twapId, transactionHash, blockNumber}` (receipt: `order_id` = twapId).
  `twap_cancel(twap_id)` signs the new `TwapCancelReq` intent locally (no
  tx-builder route) and POSTs `{twap}/twaps/cancel`. `account.twaps()` moved
  from the core API to `{twap}/twaps` (0-based `pageNum`). The `wait` kwarg
  is gone from all three (no relayer involved).
- **Partial TP/SL CRUD**: create is now `POST {core}/offchain-orders`
  (was PUT) and returns the stored order incl. `documentId`; new
  `update_partial_tp_sl(document_id, ...)` does an atomic in-place
  replacement via `PUT {core}/offchain-orders/{documentId}`;
  `cancel_partial_tp_sl` signs the new `CancelOffchainOrder` intent (EIP-712
  over the `documentId`) and sends `DELETE` with a JSON body — it also
  accepts a bare documentId string.
- **New intent kinds**: `TwapCancelReq` and `CancelOffchainOrder` added to
  `intents_schema` and `LocalIntentBuilder` (`twap_cancel`,
  `cancel_offchain_order`), with golden vectors (ethers `TypedDataEncoder` —
  the twap-app/core-backend verify these off-chain with ethers).
- **EIP-7702 authorization nonce**: relayer-mode type-4 transactions now sign
  the authorization over the correct EOA protocol nonce. Delegate/API keys
  (register in the UI, export the key — the normal setup) are fresh EOAs, so
  nonce 0 is correct and no RPC is needed. Signing with the trader EOA
  directly now requires `rpc_url` / `AVANTIS_RPC_URL` (any Base endpoint) and
  fails fast with a `ConfigError` otherwise. Found in the 2026-07-28 live
  E2E: a stale-nonce authorization is silently skipped by the protocol,
  which bricks every smart-account call for EOAs that carry a foreign
  delegation (e.g. MetaMask-upgraded wallets).
- `account.register_delegate` docstring now spells out that the expiry is an
  ABSOLUTE unix timestamp in seconds (the tx-builder rejects durations).

### Unreleased additions (2026-07-28)

- **Docs overhauled and mirrored**: `docs/mintlify/` is now byte-identical
  with the published `avantis-python-sdk` repo (sync = plain copy, see the
  docs README). Market-orders page documents the batched-market lifecycle
  (`tracking_id`, `wait=False`, seq-resumable status replay); the MM
  fast-path page and `examples/13_mm_fast_path.py` were rewritten for the
  dual-payload architecture (market orders need the EIP-7702 calldata leg;
  settlement via `engine.batched_market.wait`); the delegates page example
  passes an absolute unix expiry; execution-modes documents the trader-EOA
  `rpc_url` requirement. API Reference endpoint names now render as route
  paths (`positions`, `trade/open`) via `x-mint.metadata.sidebarTitle`
  emitted by the tx-builder OpenAPI generator (was operationId-style
  `V2Positions`).
- `market_open` / `market_open_coin` accept an optional `open_price` — the
  reference price the fill is validated against (± `slippage_percent`);
  resolved from the live feed when omitted (matching `increase_position`).
- LocalIntentBuilder now covers the full non-RFQ intent surface with typed
  helpers: `open_trade_coin`, `close_trade_coin`, `increase_position`,
  `increase_position_coin`, `partial_tp_sl` (TpSlReq: no deadline,
  `signTimestamp` freshness), `twap_open`, `twap_close`, `register_code`,
  `set_referral_code` (referral domain; requires the Referral address).
  RFQ intents remain reachable via the raw `build(kind, message)`.

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

- Golden-vector suite covering all 17 intent types (digests computed by the
  real on-chain SignatureHelpers library; the two off-chain-verified kinds,
  TwapCancelReq and CancelOffchainOrder, by ethers TypedDataEncoder).
- Byte-for-byte EIP-7702/Gelato encoding parity with the Avantis web app.
- Markets models validated against a real 112-pair testnet snapshot.
