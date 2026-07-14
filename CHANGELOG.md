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
  position increases, partial TP/SL trigger orders (off-chain stored),
  TWAP and RFQ.
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

### Testing

- Golden-vector suite covering all 15 intent types (digests computed by the
  real on-chain SignatureHelpers library).
- Byte-for-byte EIP-7702/Gelato encoding parity with the Avantis web app.
- Markets models validated against a real 112-pair testnet snapshot.
