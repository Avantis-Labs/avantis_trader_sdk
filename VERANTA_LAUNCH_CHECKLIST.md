# Veranta launch checklist: SDKs, docs, tx-builder

Everything below is prepared locally and verified. Nothing is committed, pushed or published yet. Work through the steps in order; each one says how to verify it.

## What is ready (uncommitted, per repo)

| Repo | State | Verified |
| --- | --- | --- |
| `avantis_trader_sdk` (Python) | Renamed to `veranta-sdk` 2.1.0, import `veranta_sdk`. Builder codes v2, price fix, KMS example, rename docs, compat shim in `compat/avantis-trader-sdk/`. New Mintlify docs in `docs/mintlify/`. | 170 tests, ruff, mypy. Both wheels build. |
| `avantis-sdk` (TypeScript) | New package `veranta-sdk` with `veranta-sdk/react` and `veranta-sdk/kms`. Builder codes, KMS signer, rename, version sync on build. | 89 tests, lint, typecheck, publint + attw. |
| `avantis-tx-builder` | Veranta naming, Veranta ToS constant, golden vectors regenerated from the deployment branch. Builder codes v2 (pre-existing uncommitted work). | 126 tests, typecheck. |
| `avantis-python-sdk` (docs mirror) | Byte-identical copy of `docs/mintlify` plus its LICENSE. | Mintlify broken-link check passes. |
| `avantis-cd` | Mainnet tx-builder gets `ADDR_BUILDER_CODE` and `ADDR_DELEGATION_TEMPLATE`. Blitz allowlist changes were already there. | Reviewed, not applied. |

Host status today: every `*.veranta.xyz` service resolves and serves. `delegate.veranta.xyz` is live. `sdk.veranta.com` has DNS but no site yet. The testnet RPC and explorer (`base-testnet-rpc-ovh` / `base-testnet-ovh`) stay on `avantisfi.com` by decision.

## 0. Before you start

1. Confirm the mainnet contracts accept the Veranta ToS. The `v2/testnet_deployment` branch has `_TNC_TO_SIGN_V2`; check mainnet by registering a throwaway delegate with the new SDK on mainnet, or read the constant from the deployed `SignatureHelpers` library with `cast call <address> "_TNC_TO_SIGN_V2()(bytes32)"`.
2. Decide the first TypeScript version. `pnpm changeset version` will produce `0.2.0` from the two pending changesets. If you want `1.0.0`, set it in `package.json` before publishing; the build syncs `src/version.ts` for you.
3. Have at hand: a PyPI account that owns `avantis-trader-sdk`, an npm account (and ideally the `veranta` org to hold the `@veranta` scope), the GitHub `NPM_TOKEN` secret, Mintlify dashboard access, DNS control for `sdk.veranta.com`.

## 1. Commit and push, in this order

Suggested messages; adjust to taste.

```bash
cd ~/Work/Avantis/code/avantis-tx-builder
git add -A && git commit -m "Veranta rename: ToS v2 constant, regenerated golden vectors, builder codes v2"

cd ~/Work/Avantis/code/avantis-cd
git add -A && git commit -m "tx-builder mainnet: BuilderCode registry + delegation template addresses"

cd ~/Work/Avantis/code/avantis_trader_sdk
git add -A && git commit -m "veranta-sdk 2.1.0: rename from avantis-trader-sdk, builder codes v2, KMS example, new docs"
git tag v2.1.0

cd ~/Work/Avantis/code/avantis-sdk           # no remote yet: create Avantis-Labs/avantis-sdk on GitHub first
git remote add origin git@github.com:Avantis-Labs/avantis-sdk.git
git add -A && git commit -m "veranta-sdk: rename, KMS entry point, builder-code hardening"

cd ~/Work/Avantis/code/avantis-python-sdk
git add -A && git commit -m "Veranta docs: Python and TypeScript, rename notice"
```

Push each one. The docs mirror deploys on push; publish the tx-builder and the SDKs first so the docs never point at something that does not exist yet.

## 2. Deploy the tx-builder (do this first)

1. Push `avantis-tx-builder`. CI builds the image and the CD action bumps `global.version` in `avantis-cd/services/avantis-tx-builder/values.yaml`.
2. Push `avantis-cd` with the mainnet env vars. Without them mainnet would serve the testnet registry and template addresses.
3. Verify:

```bash
curl -s https://tx-builder.veranta.xyz/v2/meta | jq '.data.addresses | {builderCode, delegationTemplate}'
# mainnet: 0xeDA810c70769a7221fB7e640D974534026719975 / 0x92F8ab16f6322a11d9f629baF081094c22A3a362
curl -s https://tx-builder-testnet.veranta.xyz/v2/meta | jq '.data.addresses | {builderCode, delegationTemplate}'
# testnet: 0x4edE46D47C1f38d614ADda0BeCF4eBfF7722289d / 0x8Ee65f19929F30F1d85a1dDd4c38a6745483818d
curl -s "https://tx-builder.veranta.xyz/v2/intents/delegate-set?trader=0x...&delegate=0x...&expiry=1900000000" | jq '.data.message.tnc'
# starts with "I accept the Veranta Terms of Service"
```

## 3. Publish the Python SDK (`veranta-sdk` 2.1.0)

```bash
cd ~/Work/Avantis/code/avantis_trader_sdk
source .venv/bin/activate
pip install -e ".[dev]"
rm -rf dist && python -m build
twine check dist/*
twine upload dist/*                 # first upload creates the veranta-sdk project on PyPI
```

Verify in a clean environment:

```bash
python -m venv /tmp/v && /tmp/v/bin/pip install veranta-sdk==2.1.0
/tmp/v/bin/python -c "import veranta_sdk; print(veranta_sdk.__version__)"
```

Then on pypi.org: add the other maintainers to the new project, and consider Trusted Publishing for future releases (there is no publish workflow in this repo; releases are manual today).

## 4. Publish the final `avantis-trader-sdk` 2.1.0 shim

This is the last release under the old name. It only depends on `veranta-sdk` and re-exports it.

```bash
cd ~/Work/Avantis/code/avantis_trader_sdk/compat/avantis-trader-sdk
rm -rf dist && python -m build
twine check dist/* && twine upload dist/*
```

Verify:

```bash
/tmp/v/bin/pip install --upgrade avantis-trader-sdk
/tmp/v/bin/python -W default -c "import avantis_trader_sdk as a; print(a.__version__, a.AsyncAvantis)"
# prints a DeprecationWarning pointing at veranta_sdk, then 2.1.0 and the AsyncVeranta class
```

## 5. Publish the TypeScript SDK (`veranta-sdk` on npm)

Names are free on npm today: `veranta-sdk`, `veranta`, and the `@veranta` scope. Create the `veranta` org on npmjs.com so nobody else can take the scope.

Option A, from your machine:

```bash
cd ~/Work/Avantis/code/avantis-sdk
pnpm install
pnpm changeset version            # writes CHANGELOG.md, bumps package.json (0.2.0), consumes .changeset/*.md
git add -A && git commit -m "Version packages"
npm login
pnpm check:package                # build (syncs src/version.ts) + publint + attw
pnpm release                      # build + changeset publish; publishConfig.access is public
git push && git push --tags
```

Option B, through CI: add `NPM_TOKEN` to the GitHub repo secrets and push to `main`. The changesets action opens a "Version Packages" PR; merging it publishes.

Verify:

```bash
npm view veranta-sdk version
mkdir /tmp/t && cd /tmp/t && npm init -y >/dev/null && npm i veranta-sdk viem
node -e "import('veranta-sdk').then(m => console.log(Object.keys(m).includes('Veranta')))"
node -e "import('veranta-sdk/kms').then(m => console.log(typeof m.KmsSigner))"
```

## 6. Publish the docs

1. Replace the Avantis artwork: `docs/mintlify/logo/light.svg`, `docs/mintlify/logo/dark.svg`, `docs/mintlify/favicon.svg`. Colors in `docs.json` are still the old purple; change them if the brand palette changed.
2. Re-sync the mirror and push it (Mintlify deploys from `avantis-python-sdk`):

```bash
cd ~/Work/Avantis/code
rsync -a --delete --exclude .git --exclude LICENSE avantis_trader_sdk/docs/mintlify/ avantis-python-sdk/
diff -rq avantis_trader_sdk/docs/mintlify avantis-python-sdk --exclude=.git   # only LICENSE may differ
cd avantis-python-sdk && git add -A && git commit -m "Veranta docs" && git push
```

3. In the Mintlify dashboard set the custom domain to `sdk.veranta.com` and add the DNS record it asks for. Keep `sdk.avantisfi.com` pointed at the same site for a while so old links keep working.
4. Verify `https://sdk.veranta.com`, the API Reference tab (it renders `https://tx-builder.veranta.xyz/openapi.json` live), and `https://sdk.veranta.com/llms.txt`.

## 7. Hosts still on `avantisfi.com`, flip later

When `base-testnet-rpc-ovh.veranta.xyz` and `base-testnet-ovh.veranta.xyz` exist, update these five places, run the tests, and cut patch releases:

- `avantis-sdk/src/config.ts` (`TESTNET_RPC_URL`) and `avantis-sdk/tests/config.test.ts`
- `avantis-sdk/src/testnet.ts` (`TESTNET_EXPLORER_URL`)
- `avantis_trader_sdk/examples/21_kms_testnet_mm_open.py`
- `avantis_trader_sdk/docs/mintlify/configuration.mdx` and `migration/rename.mdx`, then re-sync the mirror

## 8. Not covered here

- The API Key Generator UI (`avantis-delegate-ui`) and the web app copy: brand text and the ToS link, if they still say Avantis.
- GitHub org display name (the `Avantis-Labs` slug and repo names stay, as decided). Update repo descriptions and topics.
- Infra names (Kubernetes, images, metrics, alert names) stay `avantis-*` by decision.
- The old Sphinx docs repo `avantis_trader_sdk_docs` is not hosted anywhere. Archive it.
- Contracts: nothing to change. The rename only relies on the Veranta ToS constant already deployed.

## 9. After launch

- Announce with a link to `https://sdk.veranta.com/migration/rename`.
- Watch for `DeprecationWarning` reports from `AVANTIS_*` env vars and the old class names.
- Plan Python 3.0.0 (drop the deprecated aliases and the `AVANTIS_*` fallback) after a couple of releases. Do the same in the TypeScript SDK at its next major.

## Appendix: what changed for users

| | Before | Now |
| --- | --- | --- |
| Python package / import | `avantis-trader-sdk` / `avantis_trader_sdk` | `veranta-sdk` / `veranta_sdk` |
| Python classes | `AsyncAvantis`, `Avantis`, `AvantisConfig`, `AvantisError` | `AsyncVeranta`, `Veranta`, `VerantaConfig`, `VerantaError` (old names are deprecated aliases) |
| TypeScript package | none | `veranta-sdk`, `veranta-sdk/react`, `veranta-sdk/kms` |
| Env vars | `AVANTIS_*` | `VERANTA_*` (old names still read, with a warning) |
| Hosts | `*.avantisfi.com` | `*.veranta.xyz`, except the testnet RPC and explorer |
| Delegate ToS text | Avantis | Veranta (contracts accept both) |
| EIP-712 domain | `AvantisTrading` | unchanged, on-chain constant |
| Docs | sdk.avantisfi.com, Python only | sdk.veranta.com, Python and TypeScript side by side |
