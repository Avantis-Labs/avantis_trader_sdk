# Avantis v2 SDK — Progress (memory file)

Plan: `.cursor/plans/avantis_v2_python_sdk_8be24d1c.plan.md` (do not edit).
Research reference: `docs/v2/RESEARCH.md`.

## Status

- [x] Phase 0 — groundwork (RESEARCH.md, PROGRESS.md, scaffold, pyproject, ruff/mypy/pytest)
- [x] Phase 1 — core loop: config/signers/transport/meta, eip7702 encoder
      (byte-for-byte parity with @gelatocloud/gasless, tests/test_eip7702.py),
      intent sign + digest assert, relayer batch submit/poll, market open/close,
      positions, golden vectors (all 15 kinds green)
- [x] Phase 2 — execution surface: direct route via RPC (EIP-1559 signing),
      tx-builder raw relay, TX_RELAY passthrough, all intents (open/close ± coin,
      increase ± coin, tpsl-update, tpsl-partial, twap, rfq, delegate-set,
      referral sigs), limit orders, margin, approvals (trader-only guard),
      off-chain partial TP/SL (PUT/DELETE /offchain-orders), register/revoke
      delegate, claims, add-to-buffer, builder codes, LP deposit/mint/withdraw/
      redeem, referral namespace (direct + gasless withSig), KMS signer
- [x] Phase 3 — information parity: markets snapshot models (validated against the
      real 112-pair testnet payload in tests/vectors/trading_snapshot.json),
      compute layer (gross/net PnL incl. ZFP tiers + loss protection, liq price,
      skew open fee, maker/taker, OI headroom, TP/SL conversions, pnlOrderMinSL,
      validate_order), info API (trade/order history v2, portfolio analytics,
      referral stats, vault APY), candles, dynamic spread, price reads
- [x] Phase 4 — streams (Lazer SSE + Hermes WS with reconnect, Socket.IO
      RES:DATA, native Pusher order events) + MM fast path (LocalIntentBuilder:
      digest parity with golden vectors for all 15 kinds; encodedIntent parity
      with viem for OpenTradeReq/CloseTradeReq/DelegateReq/TpSlReq; NoncePool)
- [x] Phase 5 — docs + release: 18 runnable examples (examples/01…18), new
      README + CHANGELOG, Mintlify docs starter (docs/mintlify: docs.json with
      live tx-builder OpenAPI tab, introduction + quickstart MDX), rewritten
      .cursorrules, release script for pyproject-based 2.x, removed all v1
      artifacts (Sphinx docs, ABIs, setup.py, AGENT.md)

## Second-pass review fixes (pre-testing)

- Client refactor: removed the async-lazy namespace proxies (they broke
  property access like `client.trade.trader`); ExecutionEngine now resolves
  chain_id lazily from meta, so all namespaces construct eagerly.
- LocalIntentBuilder bool bug fixed: top-level bools (TwapOpenOrder.isCoin,
  RfqOpenOrder.buy) were being stringified — "False" is truthy in EIP-712
  encoding (verified: eth_account hashes "False" == False only by luck of the
  vectors; now bools pass through untouched, with a decimal-string-input test).
- abi encoding in LocalIntentBuilder now uses the int-coerced message (string
  inputs accepted); payload message serialization guards nested bools.
- Engine: single encode+sign per type4 (pinned exec nonce; deterministic RFC
  6979 signatures make build_type4 reuse byte-identical), authorization always
  attached (UI parity), removed dead delegation-code check.
- Relayer queue POST is no longer retried (duplicate enqueue of the same
  signed action would surface as a confusing InvalidNonce on the second run).
- submit_intent_batch now raises for non-batch intents (TWAP/RFQ/TpSlReq)
  instead of defaulting to BATCH_MARKET_EXECUTION.
- KMS: address derivation passed a non-0x hex string to to_checksum_address
  (now bytes); usdc_balance uses the exact raw `balance` field.
- TWAP/RFQ method signatures: defaultLeverage/maxLeverage/maxSlippagePercent
  are contract-required — now required kwargs (verified against
  tx-builder twap/rfq route zod schemas; wire param is `side`, matches).
- dynamic_spread metadata descaling made robust (was breaking on floats).
- Removed unused pysher extra.

## Notes / discoveries during implementation

- Golden-vector domain (chainId 31337, router 0x5fbdb2…) reused in tests/conftest META.
- Partial TP/SL is stored OFF-CHAIN (core API /offchain-orders); operator executes
  executePartialTpSl when the trigger hits. Cancel = re-sign same TpSlReq fields.
- Referral / USDC approve / claims / LP are msg.sender-scoped — blocked in
  delegate mode with a clear ConfigError (delegatable=False guard in base_api).
- setDelegateWithSig + referral *WithSig calldata are encoded locally (fixed
  2-bytes-arg ABI, no contract ABI files) since tx-builder has no calldata
  endpoint for them.
- UI cancel offchain order re-signs the same TpSlReq → identical signature;
  SDK reproduces this (test_offchain_partial_tpsl_cancel_signs_same_digest).

## Open items to verify against live testnet (pre-2.0.0 release checklist)

- tx-builder testnet base URL (config.py TESTNET currently points at
  tx-builder.avantisfi.com — confirm the testnet host in avantis-cd)
- feed-v3 testnet host; Pusher app key for order events (config.pusher_key)
- End-to-end smoke on internal testnet: market open/close via relayer
  (SDK-built type4 accepted?), limit order passthrough, tpsl-update
  erc712-only acceptance, offchain partial TP/SL PUT/DELETE
- Whether `GET /v2/relay/{requestId}` exposes reverted status/receipt
- mainnet relayer/data/risk URLs in config.py MAINNET are guesses — fill in
  real hosts before a mainnet release
- Publish 2.0.0a1 to TestPyPI first; author remaining Mintlify pages
