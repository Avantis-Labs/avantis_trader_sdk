// Generates a reference EIP-7702 encodeCallData payload using the REAL
// @gelatocloud/gasless implementation (from avantis-ui-v2 node_modules).
// Output: tests/vectors/eip7702_reference.json
//
// Run: node tests/vectors/gen_eip7702_reference.mjs <path-to-avantis-ui-v2>
import { createRequire } from 'module';
import { writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const uiRoot = process.argv[2];
const require = createRequire(join(uiRoot, 'package.json'));
const { privateKeyToAccount } = require('viem/accounts');
const { createWalletClient, http } = require('viem');
const { base } = require('viem/chains');
const { toGelatoSmartAccount } = require('@gelatocloud/gasless');

// Tiny JSON-RPC stub so signAuthorization can fetch the account nonce (0).
import { createServer } from 'http';
const server = createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    const { id, method } = JSON.parse(body);
    const result = method === 'eth_chainId' ? '0x2105' : '0x0';
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ jsonrpc: '2.0', id, result }));
  });
});
await new Promise((r) => server.listen(18545, r));

const TEST_KEY = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80';
const owner = privateKeyToAccount(TEST_KEY);
const client = createWalletClient({ account: owner, chain: base, transport: http('http://127.0.0.1:18545') });
const account = toGelatoSmartAccount({ client, owner });

const calls = [
  {
    to: '0x5aF42746a8Af42d8a4708dF238C53F1F71abF0E0',
    data: '0xdeadbeef00112233',
    value: 0n,
  },
  {
    to: '0x1111111111111111111111111111111111111111',
    data: '0x',
    value: 5n,
  },
];
const nonce = (1234567890123n << 64n) | 0n;

const data = await account.encodeCallData({ calls, nonce });
const authorization = await account.signAuthorization();

const out = {
  privateKey: TEST_KEY,
  owner: owner.address,
  chainId: base.id,
  calls: calls.map((c) => ({ to: c.to, data: c.data, value: c.value.toString() })),
  nonce: nonce.toString(),
  encodeCallData: data,
  authorization: {
    address: authorization.address,
    chainId: authorization.chainId,
    nonce: Number(authorization.nonce),
    r: authorization.r,
    s: authorization.s,
    yParity: Number(authorization.yParity),
  },
};

const here = dirname(fileURLToPath(import.meta.url));
writeFileSync(join(here, 'eip7702_reference.json'), JSON.stringify(out, null, 2));
console.log('wrote eip7702_reference.json');
console.log(JSON.stringify(out, null, 2));
server.close();
