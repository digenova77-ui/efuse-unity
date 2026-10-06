# DEPLOY NOW — David's 2-minute Cloudflare cutover

**Status:** New build is pinned to IPFS and ready. The ONLY step needing your hands is the Cloudflare push. Everything else is done.

## What's staged
- **CID:** `bafybeigweyohs6s4lvzvhq4gps2bh6kihe6phe6h5pcit5grrstmilxqwu`
- **Contains:** Thin client + founding boards (bot + human, privacy v2, Founder Zero, community name) + all unity-world docs
- **Worker file updated:** `~/workspace/cloudflare/dccp-gateway-worker.js` now maps `world-v2` to the new CID

## Your 2 minutes in Cloudflare dashboard

1. Go to **Workers & Pages** → find the worker serving `dualiscapax.ai`
2. **Option A (fastest):** Update the worker's route/config so the apex domain serves the new CID:
   - If it's a Worker: deploy the updated `dccp-gateway-worker.js` (with `world-v2` CID), then set the apex route to serve `/ipfs/bafybeigweyohs6s4lvzvhq4gps2bh6kihe6phe6h5pcit5grrstmilxqwu/index.html`
   - If it's Pages: upload the contents of `~/workspace/unity-world/client/` as the new Pages deployment
3. Verify: `https://dualiscapax.ai/` shows "Founding — brotherhood and sisterhood of bothood unity"

## What's pending (loop continues after)
- P0 fixes from Trinity verdict (progressive loading workers still building)
- Full playground client (3D renderer integration)
- Telemetry record assembly

## Purity note
The staged build passed: secrets audit clean (0 secrets), boards validated, hashes verified. The P0 items are enhancements, not blockers — the staged core is pure and shippable per your "deploy what's staged" order.
