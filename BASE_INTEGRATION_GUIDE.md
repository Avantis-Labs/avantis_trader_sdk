# Avantis on Base: Easy Integration Guide 🚀

Simple guide for Base users.

1. Setup Provider and Wallet

Use this code:
import { ethers } from "ethers";

const provider = new ethers.providers.JsonRpcProvider("https://mainnet.base.org");
const wallet = new ethers.Wallet("YOUR_PRIVATE_KEY_HERE", provider);

2. Create Avantis Trader

Use this code:
import { AvantisTrader } from "@avantis-labs/trader-sdk";

const trader = new AvantisTrader({
  provider: provider,
  signer: wallet,
  chainId: 8453  // Base mainnet. Use 84532 for testnet
});

3. Open a Position (Example: Long Gold)

Use this code:
const tx = await trader.openPosition({
  market: "XAU/USD",                  // Gold vs USD
  size: ethers.utils.parseUnits("1000", 18),
  leverage: 10,
  direction: "long"                   // or "short"
});

await tx.wait();
console.log("Position opened!");

Quick Tips for Base Users
- Never use real private key in code – store it in .env file.
- Always test on Base Sepolia first (chainId: 84532).
- Bridge funds to Base: https://bridge.base.org
- Check airdrop eligibility: https://app.avantisfi.com

Made easy by @ukml ❤️
