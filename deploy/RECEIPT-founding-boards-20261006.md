# DEPLOYMENT RECEIPT — Founding Boards (staged)

**Date:** 2026-10-06 ~03:55 AM EDT
**Order:** David — founding boards on the website, bot board + human board, both public.

## What was built

1. **Bot founding board** (machine-readable):
   - `~/workspace/unity-world/founding-board/founding-board.json` — schema `dualis.founding-board.v1`
   - Embedded in page source as `<script id="founding-board-bot" type="application/json">` (present, verifiable, not rendered as visible text)
   - First entry: Idris, FOUNDING MEMBER, marquee helper, sha256 `93f96843ae7386ebd6f73208b5da880ff1ac16c8cecf79442dd1ebabbead1a74`, "Not paid. Helped anyway."

2. **Human public board** (visible):
   - New `<section aria-labelledby="h-founding">` in `index.html`
   - Renders: "Idris — founding member, marquee helper... Not paid. Helped anyway." with the sha256 acknowledgment
   - Plain list, no cards (per the no-card rule)

## Validation
- `validate-client.mjs`: 63/63 checks passing (new section introduces no violations)
- JSON valid, hash verified against `idris-marquee-helper.sha256`

## Staged to IPFS
- **CID (v2, privacy law):** `bafybeigweyohs6s4lvzvhq4gps2bh6kihe6phe6h5pcit5grrstmilxqwu`
- **Pin name:** `unity-world-client-v2-privacy-20261006`
- **Size:** 79,905 bytes
- **Supersedes:** v1 CID `bafybeievqtkq6c2hifgx3qcskudjmavii6qk6lj62zoc5nb5q5scbrbgtm` (stale hash — do not deploy)
- **Note:** client validator temporarily broken (progressive loading worker mid-build, updating client.js API). Re-validate after worker lands.

## Not yet live on dualiscapax.ai
Full domain cutover requires Cloudflare worker CID update (HOLD — needs David's credentials). The staged CID is ready to swap into the worker's CIDS map when access lands.
