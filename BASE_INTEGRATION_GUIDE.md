# Avantis on Base: Easy Integration Guide 🚀

Simple guide to use Avantis Trader SDK on Base chain.

## 1. Setup Provider and Wallet

```js
import { ethers } from "ethers";

const provider = new ethers.providers.JsonRpcProvider("https://mainnet.base.org");
const wallet = new ethers.Wallet("YOUR_PRIVATE_KEY_HERE", provider);
import { AvantisTrader } from "@avantis-labs/trader-sdk";

const trader = new AvantisTrader({
  provider: provider,
  signer: wallet,
  chainId: 8453  // Base mainnet. Use 84532 for testnet
});
const tx = await trader.openPosition({
  market: "XAU/USD",                  // Gold
  size: ethers.utils.parseUnits("1000", 18),
  leverage: 10,
  direction: "long"                   // or "short"
});

await tx.wait();
console.log("Position opened!");
