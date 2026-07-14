# Avantis v2 SDK — Research Notes (memory file)

Condensed findings from deep dives into `avantis-contracts-v2`, `avantis-ui-v2`,
`avantis-tx-builder`, `avantis-server`, `avantis-cd`, `avantis-data-service`,
`avantis-backend-monorepo`, and the v1 SDK. This is the single reference for
implementation. Verify anything ambiguous against the cited source files.

---

## 1. Service map (testnet base URLs)

| Purpose | URL | Source repo |
|---|---|---|
| tx-builder (meta, calldata, intents, raw-tx relay) | `https://tx-builder.avantisfi.com` (confirm testnet host via `avantis-cd/services/avantis-tx-builder`) | `avantis-tx-builder` |
| Operator relayer (intent batches + type4 passthrough) | `https://relayer-testnet.avantisfi.com` | deployed `relayer-app` (source not local) |
| Data API (pair/trading snapshot, Socket.IO) | `https://testnet-data.avantisfi.com/v2/trading` | `avantis-data-service` |
| Core API (positions, limit orders, twaps, offchain orders) | `https://core-testnet.avantisfi.com` | `avantis-backend-monorepo` core-backend |
| History/analytics API | `https://testnet-api.avantisfi.com` (`/v1`, `/v2`) | `avantis-server` |
| Risk API (dynamic spread) | `https://risk-api-testnet.avantisfi.com` | `avantis-backend-monorepo` risk-engine |
| Feed v3 (prices SSE, candles, price-update-data) | `https://feed-v3.avantisfi.com` (confirm testnet host) | `avantis-backend-monorepo` |
| Pyth Hermes WS | `wss://hermes.pyth.network/ws` | external |

Chain: Base (8453); internal testnet is a Tenderly fork with the same chainId
and addresses. Bootstrap all addresses/domains/enums/units from
`GET {tx-builder}/v2/meta` — never hard-code.

## 2. Units

| Field | Scale |
|---|---|
| USDC amounts | 1e6 |
| Prices, leverage, slippage %, coin exposure | 1e10 |
| Intent `deadline`/`_deadline` | unix **milliseconds** (`deadline/1000 >= block.timestamp` on-chain) |
| `DelegateReq.expiry` | unix **seconds** |
| `TpSlReq.signTimestamp` | unix ms, must not be in the future; NO deadline field |
| Builder fee percent | 1e10 = 1% (`fee = collateral * feePercent / 1e12`) |

## 3. Execution routes

### 3.1 Relayer route (default; gasless)

Two submission shapes on `POST {relayer}/v2/relay/queue`
(`{ wallet, action, payload }` → returns requestId as plain string or `{requestId|id}`):

1. **Intent batch** — `action: BATCH_MARKET_EXECUTION | BATCH_POSITION_UPDATE`,
   `payload: { erc712: { orderType, userIntent, userSignature, pairIndex }, type4 }`.
   - `orderType` = AggregatorOrderType (below), `userIntent` = abi-encoded struct
     (tx-builder returns it as `encodedIntent`), `userSignature` = 65-byte EIP-712 sig.
   - **`type4` companion is required** (confirmed decision): EIP-7702 tx executing the
     same action via the signer's Gelato-style smart account (see §5). UI reference:
     `avantis-ui-v2/apps/web-app/src/hooks/transaction/useTransaction.ts` (`submitViaBatch`).
2. **Passthrough** — `action: TX_RELAY`, `payload: { type4 }` — relayer forwards any
   Gelato-style type-4 tx to chain. Used for everything without an intent path:
   limit open (UI routes LIMIT_OPEN here), limit update/cancel, margin update, TWAP
   cancel, referral direct calls, claimRebate, `setDelegateWithSig` onboarding.

`type4` serialization (`relayer.ts serializeType4`):
`{ chainId: string, to, data, gas: string, authorizationList: [{address, chainId: hex, nonce: hex, r, s, yParity: hex1}] }`.

Status poll `GET {relayer}/v2/relay/{requestId}`:
- 404 → still pending (NOT an error)
- `{ errorMessage }` → failed
- `{ success: true, receipt: { transactionHash } }` → settled
- UI polls every 1s, 60s timeout.

AggregatorOrderType enum (`relayerEip712.ts`):
```
MARKET_OPEN=0, MARKET_CLOSE=1, LIMIT_OPEN=2, LIMIT_CLOSE=3, UPDATE_MARGIN=4,
UPDATE_SL=5, MARKET_OPEN_PNL=6, MARKET_CLOSE_PNL=7, LIMIT_CLOSE_PNL=8,
INCREASE_SIZE=9, DECREASE_SIZE=10, LIMIT_PARTIAL_CLOSE=11,
MARKET_OPEN_WITH_COIN_EXPOSURE=12, MARKET_OPEN_PNL_WITH_COIN_EXPOSURE=13,
INCREASE_SIZE_WITH_COIN_EXPOSURE=14, MARKET_CLOSE_WITH_COIN_EXPOSURE=15,
MARKET_CLOSE_PNL_WITH_COIN_EXPOSURE=16
```
Intent → action mapping: open/close (± coin, ± pnl) → BATCH_MARKET_EXECUTION;
increase/tpsl-update/tpsl-partial → BATCH_POSITION_UPDATE.

### 3.2 Direct route

Calldata from tx-builder (`/v2/trade/open`, `/v2/trade/close`, `/v2/limit/*`,
`/v2/margin/update`, `/v2/position/increase*`, `/v2/twap/*`, `/v2/rfq/*`,
`/v2/delegate/*`, `/v2/token/approve`, `/v2/lp/*`, `/v2/referral/*`, `/v2/misc/*`)
→ `{ to, from, data, value(hex wei), chainId, description, meta }`.
- `&delegate=0x…` wraps in `delegatedAction(trader, inner)`, `from` = delegate.
- Broadcast: user RPC (eth-account signs type-2 tx; JSON-RPC via httpx) or
  `POST {tx-builder}/v2/relay { rawTransaction }` (whitelist + simulation;
  status at `GET /v2/relay/{hash}` → pending|confirmed|reverted).
- msg.value: open/close market = operator execution fee (default 0 from meta);
  margin update = oracle fee (1 wei guard); increase/TWAP/RFQ = none.
- **No direct TP/SL calldata endpoint** — TP/SL update is intent-only in v2.
- **No trader-side RFQ cancel** (operator-only). TWAP cancel is user-callable.

## 4. Intents (tx-builder `/v2/intents/*`)

Response: `{ intent, signerRule, domain, primaryType, types (no EIP712Domain),
message (uints as decimal strings), digest, encodedIntent, meta }`.

**Always assert locally-computed digest == `digest` before submitting.**
Signature must be 65-byte r||s||v (v ∈ {27,28}); never EIP-2098.

15 intent kinds (golden vectors in `avantis-tx-builder/tests/golden-vectors/vectors.json`,
file-level domain, chainId 31337):
OpenTradeReq, OpenTradeCoinExposureReq, CloseTradeReq, CloseTradeCoinExposureReq,
IncreasePositionSizeReq, IncreasePositionSizeWithCoinExposureReq, UpdateTpSlReq,
TpSlReq, TwapOpenOrder, TwapCloseOrder, RfqOpenOrder, RfqCloseOrder, DelegateReq,
RegisterCodeReq, SetTraderReferralCodeByUserReq.

Two EIP-712 domains, both `("AvantisTrading","1", chainId)`:
- trading intents → verifyingContract = TradingRouter proxy
- referral intents → verifyingContract = Referral contract (separate nonce bitmap)

Key rules:
- Nonces: unordered Permit2-style bitmap, signer-chosen 256-bit random;
  `GET /v2/nonce?trader=` suggests one. TradingRouter and Referral bitmaps separate.
- Close intents bind `_openTimestamp == Trade.timestamp` (re-read position right
  before signing; margin update / partial close changes it → `PositionMismatch()`).
  **Testnet runs contracts HEAD: `_openTimestamp` IS in CloseTradeReq** (the UI's
  `relayerEip712.ts` omits it — UI is stale; trust tx-builder/golden vectors).
- `DelegateReq`: trader-only signer; `tnc` slot hashes a fixed ToS constant — sign
  message exactly as returned. ABI encode order differs from typed-data order
  (trader, delegate, expiry, tnc, deadline, nonce) — tx-builder handles.
- `TpSlReq` (partial TP/SL): no deadline; `signTimestamp` ms; `triggerType`
  fixed(price) | percentage(signed 1e10 = 1%); binds to position timestamp.
- `UpdateTpSlReq`: tp/sl of 0 = remove sentinel.
- Field `_` prefixes are inconsistent by design; never normalize; trust API `types`.
- Delegate authorization checked at SUBMISSION time; revocation kills in-flight
  intents; expiry boundary differs by route (`>` for delegatedAction, `>=` for
  intent verify) — use `/v2/delegation` booleans.

## 5. EIP-7702 / Gelato smart account (type4 companion)

Sources: `@gelatocloud/gasless` (in `avantis-ui-v2/node_modules`),
`avantis-contracts-v2/src/EIP7702Template/Eip7702Template.sol`.

- Delegation target: `GELATO_DELEGATION_ADDRESS = 0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0`
  (make configurable; default this).
- Authorization: EIP-7702 auth signed by the sending key (delegate key) over
  (chainId, delegation address, EOA account nonce). eth-account ≥0.13 `sign_authorization`.
  UI attaches it on every tx (idempotent).
- `encodeCallData(calls, nonce)`:
  1. Sign EIP-712 `Execute(bytes32 mode,Call[] calls,uint256 nonce)` /
     `Call(address to,uint256 value,bytes data)` with domain
     `{name:"GelatoDelegation", version:"0.0.1", chainId, verifyingContract: <signer EOA>}`.
  2. `mode = 0x0100000000007821000100000000000000000000000000000000000000000000`
     (callType 0x01 batch, execType 0x00, selector 0x78210001).
  3. `opData = abi.encodePacked(uint192 nonceKey, bytes signature)` where
     `nonceKey = nonce >> 64`.
  4. `executionData = abi.encode(Call[] calls, bytes opData)` (ERC-7821 encodeCalls).
  5. Final tx data = `execute(bytes32 mode, bytes executionData)`
     selector `keccak("execute(bytes32,bytes)")[:4]` on the signer's own address (`to = signer EOA`).
- Nonce scheme: `nonce = (key << 64) | seq`; UI uses `key = Date.now()(±*1000+i)`,
  `seq = 0` — fresh key ⇒ on-chain `nonceSequenceNumber[key] == 0`, no RPC read.
- Builder code: UI appends a 32-byte builder-code suffix to the outer tx data
  (`data + builderCode.slice(2)`). Suffix comes from `getBuilderCode()`; make optional.
- Calls content for trading: `[{to: TradingRouter, value: 0, data: delegatedAction(trader, innerCalldata)}]`
  for delegate mode; plain calldata for trader mode.
- Gas: `max(1_000_000, estimateGas)` with 1M fallback when estimation unavailable.
- Delegation "deployed" check: `eth_getCode(EOA) == 0xef0100 ++ delegationAddress`.

## 6. Reads

### tx-builder
`/v2/meta`, `/v2/pairs`, `/v2/nonce`, `/v2/positions?trader=`,
`/v2/delegation?trader&delegate`, `/v2/allowance?trader[&spender]`, `/v2/lp/state[?owner]`.

### Data API `/v2/trading` (human units)
`{ dataVersion, pairCount, maxTradesPerPair, totalOi, maxOpenInterest,
pairInfos{idx}, groupInfo{idx} }`. Per pair: leverages (min/max, pnlMin/pnlMax),
spreadP/pnlSpreadP, openFeeP/closeFeeP, maker/taker (`additionalPairParams2`),
openInterest{long,short}, coinOI, marginFee{long,short}, fundingRate{long,short},
fundingFeePerHourP, accPerOiLong/Short, pnlFees{tierP[],feesP[]},
lossProtectionMultiplier, long/shortSkewConfig, skewEqParams, values{maxGainP,
maxSlP, maxLongOiP, maxShortOiP, maxWalletOI…}, feed.attributes market hours
{isOpen,nextOpen,nextClose,schedule}, lazerFeed, pairTwapParams{minRunTime,
maxRunTime,frequency,twapFee}, liquidity{buy,sell}, isPairListed,
closeOnlyMode, minLevPosUSDC, storagePairParams (posSpreadCap etc.), hedgingParams.
Socket.IO on same host: event `RES:DATA` = partial/full snapshot updates.

### Core API (raw on-chain scales, uints as strings)
- `GET /user-data?trader=` → `{ positions[], limitOrders[] }` with liquidationPrice,
  rolloverFee, unrealisedFundingFee, lossProtection, isPnl, openedAt, offchainOrders.
- `GET /twaps?trader&includeCanceled&pageNum&pageSize`
- `PUT /offchain-orders` (signed partial TP/SL), `DELETE /offchain-orders?trader&pairIndex&index&signedMessage`
- `GET /user-data/config?wallet=` → `{ globallyEnabled, enabledForWallet }`
- `GET /v2/open-interests`

### History API (avantis-server, human units)
v2: `/v2/history/trade-history/{addr}/{page}/{limit≤20}` (fills w/ full fee breakdown:
grossPnl, netPnl, openFee, closeFee, borrowFee, funding, profitSharingFee,
usdcSentToTrader), `/v2/history/order-history/...`, `/v2/history/portfolio/profit-loss/...`,
`/v2/history/referral/stats/{addr}`, `/v2/vault/share-rate-returns`.
v1: `/v1/history/portfolio/{total-size,win-rate,total-fees,loss-protection,history,top,leader-board}/...`,
`/v1/history/portfolio/profit-loss/history/{addr}/{period}/{dateGroup}`,
`/v1/vault/returns`, `/v1/history/vaults/apr/...`, `/v1/history/recent-trades/{pairIndex}`.
Wrapper: `{ success, ...data }`.

### Risk API
`GET /v2/dynamic-spread/{pairIndex}?collateralUsdc&isLong&leverage&isPnl&precision=18[&trader]`
→ `{ dynamicSpreadPct, metadata: { fixedSpreadPct, priceImpactSpreadPct, skewImpactSpreadPct } }`
(divide by 10^precision).

### Feed v3
`GET /v1/price-feeds/last-price`, `GET /v1/latest_price?price_feed_ids=`,
SSE `GET /v1/stream?price_feed_ids=` (event `price_update`,
`{timestampUs, priceFeeds:[{priceFeedId, price, exponent, bestBid/Ask, confidence}]}`,
heartbeat 30s), `GET /v1/shims/tradingview/history?symbol&resolution&from&to` (OHLCV),
`GET /v2/pairs/{pairIndex}/price-update-data` → `{core:{price,priceUpdateData,...}, pro:{...}}`.

### Pusher (order execution events)
Channel `events-{traderAddress}`; events: `OrderPickedUpForExecution`,
`ExecutionConfirmedInFlashblock`, `OrderFilled`, `OrderCanceled`.
Needs `PUSHER_ID` + cluster (default us2) — config values.

## 7. Compute formulas (UI parity)

Sources: `avantis-ui-v2/apps/web-app/src/lib/utils.ts`, `hooks/user/positions.helper.ts`,
`hooks/trade/*`, `packages/shared/src/*`, contracts `PairInfos.sol`/`PairStorageExtension`.

- **Gross PnL**: `(current-open)*dir/open * leverage * collateral` (dir=+1 long/-1 short).
- **Percent profit cap**: `maxGainP` per pair (e.g. 2500%), floor -100%.
- **Net PnL (fixed-fee)**: `gross - closingFee - rolloverFee + funding? + lossProtection`
  where closingFee = `(collateral*leverage + pnl) * closeFeeP * (1 - feeDiscount) / 100`;
  loss protection (only pnl<0): `-pnl * lossProtectionP/100`, capped by
  `initialPosToken * lossProtectionP/100`. Funding from core API `unrealisedFundingFee`.
- **Net PnL (ZFP/isPnl)**: `grossPnlP = gross/collateral*100`;
  `feeP = pnlFeeByGrossProfitP(tierP, grossPnlP, feesP)` (0 if gross ≤ 0; scan tiers
  from top: first tierP ≤ grossPnlP → feesP[i]); `net = gross * (1 - feeP/100)`.
  Adjusted max TP: `maxGainP * (100 - feeAt(maxGainP)) / 100`.
- **Liquidation price (estimate)**: `liqThreshold = 85%`;
  `dist = openPrice * (collateral*0.85 - rolloverFee - fundingFee) / (collateral*leverage)`;
  long: open - dist; short: open + dist. Authoritative value from core API / Multicall.
- **Execution price**: `price ± price * dynamicSpread/100` (+ long, - short);
  `priceImpactOnOpen = spread/2`.
- **Skew-adjusted open fee**: after hypothetical OI shift,
  `oiPct = floor(100*oppOI/(newSameOI+oppOI))`; `idx=min(floor(oiPct/10), len-1)`;
  `feeP = (skewEqParams[idx][0]*oiPct + skewEqParams[idx][1]) / 10000`;
  discount, then `fee = size * feeP/100`. Maker/taker via coin-OI skew before/after
  (`useMakerTakerFee.ts` `makerOrTakerFeeP`).
- **Max position / OI checks** (`lib/trade.ts availableLiquidity`): sequential
  constraints — pair maxOI-totalOI, group headroom, long/short skew caps
  (`maxLongOiP/maxShortOiP` of pairMaxOI), wallet OI cap. Validation errors when
  `lev*collateral` > maxPosition or < minLevPosUSDC.
- **TP/SL math**: tp% → price: `add = base*(pct/100)/lev` (ZFP: `/(100-feeP)*100`),
  short negates; price → pct inverse. SL: `diff = base*(pct/100)/lev`.
  Bounds: TP ≤ adjustedMaxGainP; SL ≤ maxSlP (default 80); fixed SL min
  `(spread + 0.01) * lev`; ZFP SL min `max(5, pnlOrderMinSL(lev))` (piecewise, see
  `packages/shared/src/utils.ts`); spread error if `spread/2 > 0.5%` or
  `spread*lev ≥ 25.1%`.
- **TWAP**: `numSlices = floor(runTime/frequency)`; per-slice `lev*collateral/numSlices ≥ minLevPosUSDC`;
  runTime within pair minRunTime..maxRunTime.
- **Market hours**: groups 2,3,6 use `feed.attributes` (isOpen || now>nextOpen; now<nextClose).
- **Funding**: display server rates `fundingRate.long/short`;
  est hourly = `positionSize * rate/100`. On-chain: coin-OI price-aware accumulators.
- **Rollover/borrow**: directional per-block rates; per-trade
  `(accNow-accAtOpen) * initialPosToken * leverage / 1e10`.

Default UI constants: slippage 3%, min collateral 1 USDC, liq threshold 85%,
SL buffer 1%, ZFP SL floor 5%, positions poll 2s, spread poll 10s.

## 8. On-chain user surface not covered by tx-builder endpoints

(For completeness; mostly Phase 2/3 via TX_RELAY or direct calldata from tx-builder misc/referral routes.)
- `TradingStorage.claimRebate()`; `Execute.claimTokens()` (keeper rewards);
  `VaultManager.addToBuffer(amount)` (needs USDC approve to VaultManager).
- Referral direct: registerCode, setTraderReferralCodeByUser, requestSpecialCode,
  cancelRequest, relinquishCode, setTraderReferralCodeByOwner,
  setPendingCodeOwnershipTransfer, acceptCodeOwnership.
- `BuilderCode.registerBuilderCode/modifyBuilderCode`.
- LP tranche = ERC-4626 (deposit/mint/withdraw/redeem, previews, maxWithdraw);
  approve USDC **to tranche**; no lock/epoch, utilization-gated.
- Multicall reads (`getPositions`, `getDynamicDataForPosition`, `getLiquidationPrice`,
  `getPairDynamicSnapshots`) — fallback only; prefer APIs.

## 9. v1 SDK pain points to avoid

RPC-heavy multicall fan-outs; vendored ABIs; hard-coded mainnet config; sync
`requests` inside async; `asyncio.run` in `__init__`; delegate method duplication;
magic constants (1 wei value, 1M gas hard-coded); floats for money; printing errors
instead of raising; no tests; undeclared deps (aiohttp/requests/pycryptodome).

## 10. Decisions log

- Repo: this repo, package `avantis_trader_sdk`, PyPI `avantis-trader-sdk` 2.0.0 (breaking).
- Relayer endpoint: existing `/v2/relay/queue`; SDK builds `type4` companion itself.
- API key = delegate private key only; no separate auth header today.
- Local intent building: API-first; optional local builder later (needs tx-builder
  schema endpoint) — Phase 4.
- Scope: trading + positions + portfolio + history + referral + LP/vault APY +
  candles + builder codes. Streams: prices, pair-data Socket.IO, Pusher.
- Off-chain partial TP/SL flow: yes (core API /offchain-orders).
- History testnet base: `https://testnet-api.avantisfi.com`.
- Docs: Mintlify recommended (Phase 5).
