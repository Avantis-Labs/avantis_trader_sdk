# Avantis SDK docs (Mintlify)

Starter skeleton for hosting the SDK docs on [Mintlify](https://mintlify.com)
(recommended over GitBook/Sphinx: HL-style hosted docs, native OpenAPI
rendering of the tx-builder's `/openapi.json`, MDX authoring, zero build
maintenance).

- `docs.json` — site config + navigation. The **API Reference** tab renders
  the live tx-builder OpenAPI spec directly.
- `introduction.mdx`, `quickstart.mdx` — written; the remaining pages listed
  in the navigation are stubs to author (each maps 1:1 to an example script
  in `examples/`).

Local preview: `npm i -g mint && mint dev` in this directory.
Point sdk.avantisfi.com at the Mintlify deployment when ready.
