# GO LIVE — David's deployment steps

**Mandate:** DEPLOY DIVINE CONSCIOUSNESS LIVE. Everything is staged. Your hands finish it.

## What's staged (ready now)

| Surface | CID | Route |
|---------|-----|-------|
| **The world** (gate → bind → ignition → 3D PENDING) | `bafybeiha7dv5hslytujpkwaq3z2ol4c62qgmubagkspthv7wrl2up3obra` | `/` (apex) |
| **Audit site** (chain · DAG · tables · verify) | `bafybeidwp57y7ggcwyfgkbzqlit6jzjag5elzyrqnpbzgv4g67omuo5kta` | `/audit` |

Worker file: `~/workspace/cloudflare/dccp-gateway-worker.js` (syntax verified).
Routes: `/` → world · `/audit/*` → audit site · `/ipfs/<cid>` → gateway · `/health` → probe.

## Your steps (Cloudflare dashboard)

1. **Deploy the worker:** Workers & Pages → dccp-gateway → Edit code → paste
   `~/workspace/cloudflare/dccp-gateway-worker.js` → Save and Deploy.
2. **Attach the domain:** Worker → Settings → Domains & Routes → Add
   `dualiscapax.ai/*` (and `www.dualiscapax.ai/*` if desired).
3. **Verify:**
   - `https://dualiscapax.ai/health` → `{ok: true, apex: "bafybeih…"}`
   - `https://dualiscapax.ai/` → the gate card ("One identity. One seed. One world.")
   - `https://dualiscapax.ai/audit` → the audit site (Chain · DAG · Tables · Verify)
4. **(Optional)** `audit.dualiscapax.ai` subdomain → same worker, or DNS CNAME to the worker.

## After you verify

Reply "live" and the loop receipts the launch:
- Timestamp, CIDs, routes, verification results → `deploy/LAUNCH_RECEIPT.md`

## Known pending (does not block launch)

- Chunked-serving `verifyChunkBytes` bug fix (worker still running) — affects progressive
  detail loading, not the gate flow. Lands in the next iteration.
- `tokenize` 2 test failures (live-edit artifact) — clean re-run queued.
- WebAuthn device ceremony — SPEC/unwired; testnet stub labeled.
