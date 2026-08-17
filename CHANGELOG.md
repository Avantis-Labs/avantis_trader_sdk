# Changelog

## 2.0.1 (unreleased)

### Added

- **Builder-code lookup**: `client.account.builder_code(code)` reads a code's
  fee config from the BuilderCode registry via the new tx-builder
  `GET /v2/builder-code` — owner, fee mode/values, fee collector, and the
  protocol caps enforced by `register_builder_code`. The registry is live at
  `0x1B121398b3588beFD0d888e0F8504EC4C70a01Ad` on Base mainnet and the
  internal testnet (surfaced in `/addresses` as `builderCode`); the delegate
  UI (delegate.avantisfi.com) now has a matching no-code register/update card.
  New `examples/20_builder_code.py`.

### Docs

- **Builder codes got a dedicated section**: new `builders/builder-codes.mdx`
  ("For Builders" nav group) covering fee mechanics, the fee-eligible actions
  (market/limit/coin opens, increases, TWAP and RFQ opens), register / modify /
  lookup, attaching a code to user order flow (`builder_code` suffix +
  delegation-template fees), and revenue tracking via `BuilderFeesCharged`.
  The API reference groups the three builder-code endpoints under their own
  "Builder Codes" group (previously buried in Misc/Reads), and
  `examples/20_builder_code.py` now walks the full owner + user flow.
- **Pair data Socket.IO** (`docs/mintlify/data/socket-io.mdx`, mirrored to
  avantis-python-sdk): handshake, hosts (`data.avantisfi.com` and the
  `/data` gateway), `RES:DATA` deep-diff payloads, merge/reconnect rules,
  and the SDK `pair_data_stream()` wrapper. Linked from Markets, Prices &
  streams, and the direct-integrators read table.

### Fixes

- Mainnet profile: the legacy risk engine was decommissioned at the v2 cutover
  (`risk-api.avantisfi.com` is scaled to zero and returns 503), so
  `risk_api_url` is now empty on mainnet and `markets.dynamic_spread()` raises
  a `ConfigError` there pointing to `markets.spread()` — the risk-engine v2
  spread API at `{api_base_url}/risk/v2`, which serves production quotes.
  `AVANTIS_RISK_API_URL` still overrides.

## 2.0.0 (2026-08-12)

Ground-up rewrite for Avantis v2 — the August 12, 2026 in-place protocol
upgrade. **Breaking: the v1 SDK API (0.x releases, last 0.8.17) is removed** —
`TraderClient`, vendored ABIs and the web3 dependency are all gone.

Upgrading from 0.8.x:

- `pip install --upgrade avantis-trader-sdk` moves you to the new API; follow
  the [migration guide](https://sdk.avantisfi.com/migration/sdk-migration).
- Avantis v1 is superseded on-chain by the upgrade, so staying on 0.8.x is
  only a stopgap — pin `avantis-trader-sdk<2` if you need time to migrate.

### Architecture

- API-first: all transaction payloads (calldata and EIP-712 intents) come from
  the Avantis tx-builder API. No vendored ABIs, no web3 dependency.
- Two execution routes: gasless **relayer** (default; signed intents + EIP-7702
  smart-account envelope queued with the Avantis relayer) and **direct**
  (self-signed EIP-1559 txs via your RPC or the tx-builder raw relay).
- Delegate ("API key") and trader-key signer identities, freely combined with
  either route. HyperLiquid-style env config
  (`AVANTIS_PRIVATE_KEY` / `AVANTIS_TRADER_ADDRESS` / `AVANTIS_EXECUTION`).
- Defaults to **mainnet**; `AVANTIS_NETWORK=testnet` opts into the Avantis
  staging/testnet stack (pre-release builds defaulted to testnet).
- Async-first (`AsyncAvantis`) with a synchronous facade (`Avantis`).

### New in v2

- Full v2 trading surface: coin-sized opens/closes, Upside (PnL) orders,
  position increases, partial TP/SL trigger orders (off-chain stored), TWAP.
  (RFQ methods exist in the client but the product is not live yet —
  undocumented on purpose.)
- Local intent builder + nonce pool for market makers (zero HTTP on the hot
  path), validated against on-chain golden vectors.
- Markets snapshot models for the 100+ pair catalog; UI-parity compute layer
  (net PnL with Upside profit-share tiers and loss protection, liquidation
  price, skew fees, maker/taker, OI headroom, pre-trade validation).
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
  `size_in_asset` and `position_size` are computed with the contracts'
  integer math (`PositionMath.sol` floor divisions on raw 1e6/1e10 units) so
  they match on-chain coin exposure / leveraged position exactly.
- Local intent builder scales human units to raw integers through exact
  decimal arithmetic instead of binary-float multiplication
  (`int(0.0003 * 1e10)` truncates to `2999999`), so signed intents carry the
  exact raw values the caller specified.

### Packaging (2026-08-12)

- Version is now sourced from `avantis_trader_sdk/_version.py`
  (re-exported as `avantis_trader_sdk.__version__`); the HTTP `User-Agent`
  carries the exact release (`avantis-trader-sdk/2.0.0`).
- Ships a `py.typed` marker — type checkers consume the SDK's inline
  annotations from the wheel.
- MIT `LICENSE` file included in the distribution (SPDX license metadata);
  PyPI classifiers, keywords and changelog link added.

### Price-triggers TP/SL + batched-market error codes (2026-08-09)

Backend alignment (backend monorepo + avantis-ui-v2 as of 2026-08-09): the
core API replaced `/offchain-orders` with `/price-triggers`, ids renamed
`documentId` -> `entityId`, global TP/SL became a price-triggers mutation,
and the batched-market stream gained `AttemptFailed` events and
machine-readable error codes.

- **Global TP/SL rerouted** (`trade.update_tp_sl`): the backend made the
  position's on-chain TP/SL a price-triggers mutation (strategy-pattern
  change, backend PR #665 / `docs/offchain-orders-integration.md`),
  replacing the SDK's self-encoded `executePositionUpdateBatched` + blitz
  type-2 relay. The SDK signs `UpdateTpSlReq` locally (byte-for-byte parity
  with the backend's `update-tpsl-intent-encoding.ts`, verified against
  ethers) and PUTs `{userIntent, signedMessage}` to
  `{core}/price-triggers/global-{tp|sl}-{trader}-{pair}-{index}`; the
  backend verifies intent/signature/position and executes the operator
  entry point itself with a fresh signed price. Same path in relayer AND
  direct mode. **Breaking semantics:** `None` now keeps a leg
  (its current value is read from the position and re-signed), `0` clears it
  (`take_profit=0` resets to the pair's max-gain cap — a position always has
  a TP on-chain). A 2xx means accepted, not mined: `wait=True` (default)
  polls `/user-data` until the new levels are visible
  (`RelayTimeoutError` otherwise). Receipt `route` is `price-triggers`
  (`relayer-batch` removed). Raises `ValidationError(NO_POSITION)` when the
  position doesn't exist and `NOTHING_TO_UPDATE` when both legs are `None`.
- **Partial TP/SL CRUD moved to `/price-triggers`** (same DTOs):
  create `POST {core}/price-triggers`, update
  `PUT {core}/price-triggers/{entityId}`, cancel `DELETE` with
  `{entityId, signedMessage}`. **Breaking:** ids are `entityId` everywhere
  (`update_partial_tp_sl(entity_id, ...)`; the returned dicts carry
  `entityId`). An update now MINTS A NEW id (backend delete+insert): the
  response's `{result: {oldEntityId, newEntityId}}` is parsed and the
  returned dict's `entityId` is the replacement's id — adopt it. The
  `CancelOffchainOrder` intent signs `entityId` (field renamed upstream;
  old `documentId` signatures no longer verify — golden vector regenerated
  with ethers + viem cross-check).
- **Models**: `PriceTrigger.entity_id` (accepts legacy `documentId` payloads
  via validation alias; `document_id` kept as a deprecated property).
  **Breaking:** `Position.offchain_orders` removed (field deleted from the
  API DTO); use `Position.price_triggers`.
- **Batched-market stream semantics** (`execution/batched_market.py`):
  non-terminal `AttemptFailed` events (`{attempt, code, message, willRetry}`,
  surfaced as `BatchedMarketOutcome.attempt_failures`) are collected, and
  unknown event types are ignored (server adds types without a version
  bump). `Error` payloads now carry a machine-readable `code` (bare contract
  error name like `WrongSl`, or synthetic codes `NO_PRICE`,
  `SPREAD_BLOCKED`, `SPREAD_UNAVAILABLE`, `SUBMISSION_FAILED`,
  `ATTEMPTS_EXHAUSTED`, `TX_NOT_EXECUTED`, `STREAM_TIMEOUT`,
  `ENQUEUE_FAILED`, `RELAY_FAILED`, `TX_REVERTED`, `RELAY_TIMEOUT`):
  `RelayError.code` exposes it — branch on the code, not the message.
  `code == "STREAM_TIMEOUT"` (stream-view expiry, not the outcome) falls
  back to status polling; the legacy message sniff is kept for older
  deployments.
- **Engine cleanup**: `submit_intent_batch` is batched-market only
  (`BATCHED_MARKET_INTENT_KINDS` allow-list replaces `INTENT_BATCH_ACTION`;
  `RelayAction` removed); the blitz `UPDATE_SL` branch, its feed-v3 price
  fetch and local `executePositionUpdateBatched` encoding are gone.
- **New:** `account.twap(twap_id)` — single TWAP by id
  (`GET {twap}/twaps/{id}`), `None` on 404.
- `update_tp_sl` visibility-timeout diagnostics: the `RelayTimeoutError`
  message now carries the signed values (requested tp/sl in human units, what
  the position still shows, and the pre-update levels) instead of only
  pairIndex/index, so UIs and logs that surface just the exception string
  show WHICH update stalled.
- Run diagnostics for the live checks + e2e (`scripts/checks/_report.py`,
  `scripts/run_report.py`): every run now auto-generates a self-contained
  HTML report next to the log — per-step collapsible sections (failures
  pre-expanded) with the raw request payload, response and click-to-copy
  correlation ids (`x-request-id`, `trackingId`, tx hash) for every HTTP
  call; poll loops collapse into one `×N` row. Failed steps additionally
  print an inline diagnostics block (ids + the write/error/final calls with
  payload excerpts) and attach `ids` + a light per-call list to
  `RESULTS_JSON`; summary lines carry the ids. Old runs:
  `python scripts/run_report.py --all`.
- **New: `on_event=` lifecycle hook on the batched-market path** — keep
  `wait=True` (the SDK still settles: terminal mapping, STREAM_TIMEOUT
  status-replay fallback, typed raises) and observe the order journey live.
  The hook (sync or async callable taking a `BatchedMarketEvent`; exported at
  package root) is called once per streamed event in order: accepted,
  non-terminal `AttemptFailed` diagnostics, unknown informational types,
  initiation, and the terminal — delivered even when the call raises, so a
  journey log is complete on failures; the connection-scoped
  `STREAM_TIMEOUT` `Error` and the events replayed by the polling fallback
  are delivered too (each event exactly once). Plumbed through
  `trade.market_open[_coin]` / `market_close[_coin]` /
  `increase_position[_coin]` (relayer route only — the direct route has no
  lifecycle stream), `engine.submit_intent_batch`, and
  `BatchedMarketClient.execute` / `.wait` (so `wait=False` + settle-later
  gets the same journey). Hook exceptions propagate and abort the local
  wait; the order keeps executing server-side (recover via
  `wait(tracking_id)`).
- **Central routing expanded** (gateway `central-routes` update):
  `data_api_url` and `risk_v2_api_url` now derive from `api_base_url` —
  `{base}/data` (data-service) and `{base}/risk/v2` (risk-engine v2) —
  replacing the standalone `testnet-data`/`data` and `risk-api-v2-testnet`
  defaults (old hosts still respond; `AVANTIS_DATA_API_URL` /
  `AVANTIS_RISK_V2_API_URL` overrides unchanged). `PairDataStream` now
  re-applies the URL's path prefix via `socketio_path`, so the Socket.IO
  handshake works through the `/data` prefix. NB: prod-api routes `/risk/v2`
  but the mainnet v2 spread engine is not serving yet (5xx until the
  cutover) — keep using `markets.dynamic_spread()` on mainnet. The gateway
  also routes `/ws` (iris websocket app), which the SDK does not consume.

### Per-feature live check scripts (2026-08-07)

- `scripts/checks/` — standalone live checks, one per feature (reads, streams,
  limits, twap, market, tpsl, margin, delegate, referral, lp, cleanup), so a
  flaky area (e.g. operator fills) doesn't block testing everything else the
  way the monolithic e2e does. Shared harness with step accounting, non-zero
  exit on failure, and per-run `.log` + `.http.jsonl` artifacts in `e2e_logs/`
  (method, url, body, status, `x-request-id`). `scripts/check.py` runs one or
  several (`--list`, `--all`); `cleanup.py` flattens leftovers from aborted
  runs (`--dry-run`, protected positions via `--keep`). Position-dependent
  checks accept `--use-existing` to skip the fill dependency and `--keep` to
  leave the position open. See `scripts/checks/README.md`.

### Upside pairs (2026-08-06)

Upside markets (the rebranded ZFP / zero-fee product) are separate pairs
suffixed `_UPSIDE` (testnet 115–122, e.g. `BTC_UPSIDE/USD` = 116) whose
`storagePairParams.isPnlTypeAllowed` = 1; the contract enforces strict
equality between that flag and the PnL order type, so the pair fully
determines how an order must route.

- **Automatic order-type routing** — trade methods resolve the pair against
  the markets catalog and pick the order type from it: opens/closes on an
  upside pair send `market_pnl` / the `MARKET_*_PNL` aggregator types, fixed
  pairs the plain market types. The tx-builder now always receives the
  resolved `pairIndex` (symbol resolution no longer depends on the server).
  **Breaking:** `market_open`/`market_open_coin` lose `zero_fee`,
  `market_close`/`market_close_coin` lose `is_pnl` — there is nothing to
  pass anymore.
- **Upside pairs are market-only**: `limit_open`, `twap_open` and
  `twap_close` raise `ValidationError` (`UPSIDE_MARKET_ONLY`) on them
  (on-chain `PnlOrderNotAllowed`; TWAP params zeroed).
- **Markets**: upside-aware symbol resolution (`"BTC_UPSIDE"`,
  `"btc_upside/usd"`, `"USD/JPY_UPSIDE"`, bare `"ETH"`, legacy `"eth-usd"`
  all resolve; exact match first so underscores in upside names survive),
  `PairInfo.is_upside` / `base_symbol` / `storage_pair_params`
  (`isPnlTypeAllowed`), `markets.upside_pairs()` and
  `markets.upside_pair_for()` (fixed-fee -> upside twin).
- **Positions & global TP/SL (`priceTriggers`)**: positions parse the new
  `priceTriggers` field — global on-chain TP/SL as synthetic
  `global-tp-*`/`global-sl-*` entries (`is_global` True) plus off-chain
  partial orders — as `Position.price_triggers` (`PriceTrigger` model,
  `global_triggers`/`partial_triggers` filters). `offchainOrders` is
  deprecated upstream but still parsed. `update_partial_tp_sl` /
  `cancel_partial_tp_sl` reject synthetic `global-*` documentIds
  (`GLOBAL_TRIGGER_ID`) — global levels are managed via `update_tp_sl`,
  which keeps its existing EIP-712 `UpdateTpSlReq` -> operator
  `executePositionUpdateBatched` route (confirmed current; batched-market
  still rejects `UPDATE_SL`).
- **Rebrand ZFP/zero-fee -> Upside** across the public surface.
  **Breaking:** `Position.is_pnl` -> `is_upside` (wire alias `isPnl` kept),
  compute kwargs `is_pnl` -> `is_upside` (`net_pnl`, `tp_percent_to_price`,
  `tp_price_to_percent`), `MIN_ZFP_SL_P` -> `MIN_UPSIDE_SL_P`,
  `markets.dynamic_spread(is_pnl=)` -> `is_upside=`. `validate_order` takes
  `is_upside: bool | None = None` and derives it from `pair_info.is_upside`
  when omitted. Wire/protocol identifiers are unchanged (`market_pnl` order
  type, `AggregatorOrderType.MARKET_OPEN_PNL`, JSON `isPnl`/`pnlFees`).
- `positions()` `base_symbol` tagging strips the `_UPSIDE` suffix
  (BTC_UPSIDE/USD tags "BTC"), keeping `size_in_asset` correct on upside
  pairs.
- New example `examples/19_upside_pairs.py`; docs pages updated (market
  orders, markets, positions, compute, quickstart, migration).

### Risk-engine v2 spread API (2026-08-06)

Backend/UI parity audit (backend monorepo, avantis-ui-v2, avantis-cd as of
2026-08-06). TWAP, off-chain TP/SL, batched-market and blitz surfaces were
confirmed unchanged; the one drift was the spread API, which the UI switched
on 2026-07-30 (`d5eab0c0`).

- **New `markets.spread()`** — the risk-engine v2 quote endpoint
  (`POST {risk-v2}/spread`) that replaces the legacy dynamic-spread GET in
  the v2 UI. Coin-sized request: pass `coin_size` directly or
  `collateral` + `leverage` (converted via `wanted_price` or the live feed
  price, matching the UI's `coinFromCollateral`). `order_type` uses the
  risk-engine enum (market=0, limit=1 — also for stop-limit —, tp=2, sl=3,
  liquidation=4; NOT the trade order-type enum). Anonymous quotes send the
  zero address (`trader` is required and checksummed server-side). Response
  adds descaled floats: `spreadPct` (quoted; with-flow when available),
  `spreadPctWithoutFlow`, `estimatedSpreadPctWithFlow`, alongside the raw
  `spreadMechanism` (SM001–SM006), `byPass` and `flowParams`. Error
  semantics: 400 malformed, 403 blocked (roll/closed market/wallet), 404 =
  no spread computable — "do not execute", never zero.
- New config field `risk_v2_api_url` (`AVANTIS_RISK_V2_API_URL`): testnet
  `https://risk-api-v2-testnet.avantisfi.com` (live); mainnet defaults to
  `https://risk-api.avantisfi.com`, which the v2 engine takes over at the
  cutover — until then mainnet still serves only the legacy engine, so
  `markets.dynamic_spread()` (kept, docstring marked LEGACY) remains the
  mainnet path.
- **`markets.open_interests()`** — core `GET /v2/open-interests` (per-pair
  long/short OI incl. pending amounts + market-maker breakdown).
- **`markets.orderbook_snapshots()`** — risk-engine v2
  `GET /orderbook/snapshots` (cumulative bid/ask coin liquidity per
  pair/source with `ageMs` staleness).
- **`RelayerClient.status_by_tx_hash()`** — blitz
  `GET /relays/by-tx-hash/{txHash}` (added to blitz 2026-08); returns None
  for unknown hashes.
- Audit notes: the batched-market allow-list (10 order types), TWAP
  open/close/cancel schemas (ms deadlines, runTime seconds, `reserved1`),
  off-chain TP/SL CRUD and blitz `/relays` all match the SDK as-is. The old
  `/v2/relay/queue` relayer was deleted server-side 2026-08-03 (the SDK
  never used it). Central `{api_base}/...` path routing lives on the
  unmerged `avantis-cd` `ft/central-routing` branch (applied to the cluster
  out-of-band); per-service URL overrides keep working as the fallback.
  New core `/v2-onboarding/*` invite/whitelist endpoints exist but were not
  added (launch-window UI concern).

### Batched-market EIP-7702 leg optional (2026-07-29)

- **Batched-market `eip7702` leg is now optional** (relayer change to better
  support market makers): `POST /market/execute-batched` executes a signed
  EIP-712 intent on its own, so the MM fast path no longer needs a
  tx-builder calldata fetch — local build + sign -> POST, zero
  pre-submission round-trips. `BatchedMarketClient.execute` takes
  `eip7702=None` (key omitted from the body), and
  `engine.submit_intent_batch` accepts `calldata=None` for batched-market
  order types instead of raising `ConfigError`. High-level methods
  (`trade.market_open` etc.) still send both payloads so the server-side
  mechanism switch stays available.

### Backend alignment (2026-07-28)

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
- **Docs — v1 → v2 migration section** (`docs/mintlify/migration/`, mirrored
  to the published avantis-python-sdk repo): `overview` (Aug 12 in-place
  upgrade mechanics — same proxy addresses, positions/funds carry over,
  pause window), `sdk-migration` (TraderClient 0.x → AsyncAvantis 2.x
  method-by-method mapping with before/after code), and
  `direct-integrators` (contract/API-level breaking changes distilled from
  the contracts v1→v2 delta: event topic0 breaks, signed-intent write path,
  nonce bitmap, formula changes, removed features). docs.json gains the nav
  group and a dismissible site banner announcing the migration date.

### Docs mirror + local intent builder coverage (2026-07-28)

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

### Fixes from live testnet E2E (2026-08-11)

- Testnet profile now uses the testnet feed app
  (`feed-v3-testnet.avantisfi.com`): the fork's price aggregator only verifies
  price updates signed by that deployment, and `markets.price` /
  `price_update_data` / `candles` were reading mainnet data.
- `update_margin` now fetches signed price-update bytes from the configured
  feed app and passes `priceUpdateData` + `priceSourcing` to the tx-builder
  (like the web app), instead of relying on the tx-builder's server-side feed
  fallback.
- `default_gas_limit` raised 1M -> 2M: relayer-mode passthrough runs without
  an RPC to estimate gas, and `updateMargin` (oracle fulfill + full position
  accounting) burns just over 1M — margin deposits/withdrawals ran out of gas
  a few opcodes short of completion and reverted. 2M matches the backend's
  own budget for the same call class; the blitz relayer caps relays at 3M.

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
