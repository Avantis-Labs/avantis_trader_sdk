// Reference abi.encode(struct) bytes for intent structs, using viem from the
// avantis-ui-v2 node_modules — mirrors the UI's encode*UserIntent helpers.
// Run: node tests/vectors/gen_intent_encoding_reference.mjs <path-to-avantis-ui-v2>
import { createRequire } from 'module';
import { writeFileSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const uiRoot = process.argv[2];
const require = createRequire(join(uiRoot, 'package.json'));
const { encodeAbiParameters, parseAbiParameters } = require('viem');

const here = dirname(fileURLToPath(import.meta.url));
const vectors = JSON.parse(readFileSync(join(here, 'vectors.json'), 'utf8')).vectors;
const byKind = Object.fromEntries(vectors.map((v) => [v.kind, v.message]));

const out = {};

// OpenTradeReq — same order as typed data
{
  const m = byKind.OpenTradeReq;
  const t = m._t;
  out.OpenTradeReq = encodeAbiParameters(
    parseAbiParameters(
      '((address,uint256,uint256,uint256,uint256,uint256,bool,uint256,uint256,uint256,uint256),uint8,uint256,uint256,uint256)'
    ),
    [[
      [t.trader, BigInt(t.pairIndex), BigInt(t.index), BigInt(t.initialPosToken),
       BigInt(t.positionSizeUSDC), BigInt(t.openPrice), t.buy, BigInt(t.leverage),
       BigInt(t.tp), BigInt(t.sl), BigInt(t.timestamp)],
      Number(m._type), BigInt(m._slippageP), BigInt(m._deadline), BigInt(m._nonce),
    ]]
  );
}

// CloseTradeReq (contracts HEAD — includes _openTimestamp)
{
  const m = byKind.CloseTradeReq;
  out.CloseTradeReq = encodeAbiParameters(
    parseAbiParameters('(address,uint256,uint256,uint256,uint256,uint256,uint256,uint256)'),
    [[m._trader, BigInt(m._pairIndex), BigInt(m._index), BigInt(m._openTimestamp),
      BigInt(m._amount), BigInt(m._wantedPrice), BigInt(m._deadline), BigInt(m._nonce)]]
  );
}

// DelegateReq — Solidity struct order: trader, delegate, expiry, tnc, deadline, nonce
{
  const m = byKind.DelegateReq;
  out.DelegateReq = encodeAbiParameters(
    parseAbiParameters('(address,address,uint256,string,uint256,uint256)'),
    [[m.trader, m.delegate, BigInt(m.expiry), m.tnc, BigInt(m.deadline), BigInt(m.nonce)]]
  );
}

// TpSlReq — typed order (incl. negative int256 percentage)
{
  const m = byKind.TpSlReq;
  out.TpSlReq = encodeAbiParameters(
    parseAbiParameters(
      '(address,uint256,uint256,uint8,uint256,bool,uint256,int256,uint256,uint256,uint8,uint256)'
    ),
    [[m.trader, BigInt(m.pairIndex), BigInt(m.index), Number(m.triggerType),
      BigInt(m.coinSize), m.buy, BigInt(m.price), BigInt(m.percentage),
      BigInt(m.timestamp), BigInt(m.signTimestamp), Number(m.orderType), BigInt(m.nonce)]]
  );
}

writeFileSync(join(here, 'intent_encoding_reference.json'), JSON.stringify(out, null, 2));
console.log('wrote intent_encoding_reference.json:', Object.keys(out).join(', '));
