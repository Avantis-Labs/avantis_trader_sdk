# Veranta SDK docs: instructions for agents

This is the Mintlify site behind https://sdk.veranta.xyz. It documents both official SDKs, Python (`veranta-sdk` on PyPI, import `veranta_sdk`) and TypeScript (`veranta-sdk` on npm, plus `veranta-sdk/react` and `veranta-sdk/kms`).

## Where things live

- Source of truth: `avantis_trader_sdk/docs/mintlify/` (the Python SDK repo). Edit here, then sync to the mirror repo `avantis-python-sdk` (root), which Mintlify deploys. See README.md for the sync command.
- `docs.json` holds the site config and navigation. The API Reference tab renders the live tx-builder OpenAPI spec at `https://tx-builder.veranta.xyz/openapi.json`.
- One page per SDK surface. Each page maps to a runnable script in `examples/` of both SDK repos.

## Writing rules

- Every code sample shows both languages in a `<CodeGroup>` with a `Python` and a `TypeScript` block, in that order. Bash installs use the same pattern. Use `<Tabs>` only when the prose itself differs per language.
- Parameter tables carry both spellings: a Python column (`snake_case`) and a TypeScript column (`camelCase`).
- Conversational and plain. Second person, short sentences, one idea per sentence. Explain jargon the first time (notional, delegate, intent).
- No em dashes or en dashes anywhere. Use commas, periods or colons. Do not use arrows in prose.
- Sentence case headings. Code formatting for identifiers, files, commands and env vars.
- Start each page with one or two sentences saying what it covers.
- Keep pages self-contained and AI friendly: exact method names, explicit defaults, tables over prose for reference material.

## Terminology

- The product is **Veranta**. Never write Avantis except on the rename page, in the changelog-style migration notes, and for the on-chain constants below.
- **API key** and **delegate** mean the same thing; prefer "API key" in user-facing prose and mention "delegate" once.
- **Notional** is collateral times leverage. **Collateral** is the USDC put into a position.
- **Upside markets** are the `_UPSIDE` pairs (never "zero-fee" or "ZFP").

## Things that must stay as they are

- The EIP-712 domain name is `AvantisTrading`. It is a deployed on-chain constant.
- Contract, service and repo names: `Avantis-Labs` GitHub org and repo URLs, `avantis-contracts-v2`, `avantis-python-sdk` (the docs mirror repo).
- Hosts are `*.veranta.xyz` for services, `delegate.veranta.xyz` for the API Key Generator, `sdk.veranta.xyz` for these docs. Exception: the testnet RPC `base-testnet-rpc-ovh.avantisfi.com` and explorer `base-testnet-ovh.avantisfi.com` stay on `avantisfi.com` until told otherwise.

## Before you publish

- Every page in `docs.json` exists and every internal link resolves.
- `grep -rnP "\x{2014}|\x{2013}" .` returns nothing.
- Both code tabs compile against the current SDKs. Method names come from the SDK source, not from memory.
