# Veranta SDK docs (Mintlify)

These docs cover both SDKs, Python and TypeScript, and live in two places that must stay in sync:

- **Source of truth**: `avantis_trader_sdk/docs/mintlify/` (the Python SDK repo). Edit here, alongside the code the pages describe. TypeScript snippets are written against the `avantis-sdk` repo; check method names there.
- **Published mirror**: the `avantis-python-sdk` repo (root), which the Mintlify deployment at https://sdk.veranta.xyz is connected to. Sync by copying this directory over its root; the trees are kept byte-identical (the mirror only adds a LICENSE) so `diff -r` verifies it:

```bash
rsync -a --exclude .git --exclude LICENSE docs/mintlify/ ../avantis-python-sdk/
diff -rq docs/mintlify ../avantis-python-sdk --exclude=.git
```

Layout:

- `docs.json`: site config and navigation. The **API Reference** tab renders the live tx-builder OpenAPI spec (`/openapi.json`) directly; endpoint page names come from `x-mint.metadata.sidebarTitle`, which the tx-builder generates from the route path.
- One `.mdx` page per SDK surface, each with Python and TypeScript tabs, mapping to the runnable scripts in both SDK repos' `examples/`.
- `AGENTS.md`: the writing rules for anyone (human or agent) editing these pages.

Local preview: `npm i -g mint && mint dev` in this directory.
