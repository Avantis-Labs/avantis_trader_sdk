# Avantis Python SDK docs (Mintlify)

These docs live in two places and must stay in sync:

- **Source of truth**: `avantis_trader_sdk/docs/mintlify/` (this SDK repo) —
  edit here, alongside the code the pages describe.
- **Published mirror**: the `avantis-python-sdk` repo (root) — the repo the
  Mintlify deployment is connected to. Sync = copy this directory over its
  root; the trees are kept byte-identical so a plain `diff -r` verifies it.

Layout:

- `docs.json` — site config + navigation. The **API Reference** tab renders
  the live tx-builder OpenAPI spec (`/openapi.json`) directly; endpoint page
  names come from `x-mint.metadata.sidebarTitle`, which the tx-builder
  generates from the route path (`positions`, `trade/open`, …).
- One `.mdx` page per SDK surface, each mapping to a runnable script in
  `examples/`.

Local preview: `npm i -g mint && mint dev` in this directory.
