# WEBSITE DEPLOYMENT PLAN — dualiscapax.ai

**Order:** David, 2026-10-06 ~03:48 AM EDT — "bring the newest build to website existence now."

**Product vision (David, 2026-10-06):** Architectural playground for everything everywhere every way every kind every time. Not a website ABOUT the system — the system itself, playable. The 3D world is the playground. The diamond is the ground. Iris is the guide. DCLM is the law.

## Domain Estate (scanned 2026-10-06)

| Domain | Status | Serves |
|--------|--------|--------|
| dualiscapax.ai | LIVE (Cloudflare) | OLD Grok DCCP World build ("Unity playground", broken gate button) |
| www.dualiscapax.ai | DNS only | Nothing (connection refused) |
| test/staging/dev.dualiscapax.ai | DNS only | Nothing |
| api/app/world/3d/testnet/main.dualiscapax.ai | DNS only | Nothing |

**Architecture:** Cloudflare Worker (`dccp-gateway`) serves IPFS CIDs via R2 backup + gateway fallback. Current CIDs: `world-v1`, `shell-v1`.

## Deployment Strategy

### Phase 1 — Build (in progress)
- unity-world coordinator: DCLM core, thin client, economics, canon (STILL BUILDING — do not interfere)
- Progressive loading workers: thin client IndexedDB cache + DCLM chunked serving (IN PROGRESS)
- Trinity verdict worker: future manifestation + readjustment accounting (IN PROGRESS)

### Phase 2 — Package
- Assemble: progressive thin client + chunked data + 3D Rosetta spec + canon reference
- The 2D explainer stays OFF the public site (David's rule)
- Economic docs (README, schematics) for builders — repo only, not public web

### Phase 3 — Stage (IPFS via Pinata)
- Pin deployment package → get CID
- Verify via public gateway before cutover

### Phase 4 — Cutover (HOLD — needs David)
- Update Cloudflare Worker CIDS map with new CID
- Deploy worker (needs Cloudflare credentials)
- Verify dualiscapax.ai serves new build
- Old build archived, not deleted

### Phase 5 — Subdomain Purity
Assign each subdomain its pure function:
- `world.` → 3D world (free to look)
- `api.` → DCLM compute endpoints (metered)
- `testnet.` → testnet surfaces (clearly labeled)
- `app.` → wallet/app surfaces
- `test.`/`staging.`/`dev.` → staging environments
- `main.` → canonical main
- `www.` → redirect to apex
- `3d.` → 3D renderer dedicated

### Phase 6 — Cleanup
- Remove stale deployments, dead versions
- Archive old CIDs with receipts
- Domain estate ends clean

## HOLDs (need David's hand)
1. **Cloudflare credentials** — to update worker CIDS and deploy. No creds in workspace.
2. **DNS changes** — if subdomain routing needs changes beyond current DNS.
3. **Production cutover approval** — before replacing the live build.

## Purity Rules
- Every surface has one clear purpose. No mixed concerns.
- No production keys, no mainnet state in any deployment.
- Testnet surfaces clearly labeled TESTNET.
- Every deployment receipted (what, where, when, hashes).
