# Avantis on Base: Easy Integration Guide 🚀

Simple guide to use Avantis Trader SDK on Base.

## 1. Setup Provider and Wallet

```js
import { ethers } from "ethers";

const provider = new ethers.providers.JsonRpcProvider("https://mainnet.base.org");
const wallet = new ethers.Wallet("YOUR_PRIVATE_KEY_HERE", provider);

import { AvantisTrader } from "@avantis-labs/trader-sdk";

const trader = new AvantisTrader({
  provider: provider,
  signer: wallet,
  chainId: 8453  // Base mainnet (use 84532 for Sepolia testnet)
});

const tx = await trader.openPosition({
  market: "XAU/USD",                  // Gold vs USD
  size: ethers.utils.parseUnits("1000", 18),  // $1000 notional
  leverage: 10,                       // 10x leverage
  direction: "long"                   // or "short"
});

await tx.wait();
console.log("Position opened successfully!");

Quick Tips for Base UsersNever use real private key in code – store it in .env file.
Always test on Base Sepolia first (chainId: 84532).
Bridge funds to Base: https://bridge.base.org
Check airdrop eligibility: https://app.avantisfi.com

Community guide by @ukml
  – helping Base farmers trade RWAs easily!

