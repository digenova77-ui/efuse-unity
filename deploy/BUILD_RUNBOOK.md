# BUILD RUNBOOK — for David's hands

**Purpose:** You run the build yourself. Clean steps, no missing pieces. Purity gate applies throughout.

## Prerequisites

- [ ] Terminal access to this workspace (`~/workspace/unity-world/`)
- [ ] Node.js (v24+) and Python 3
- [ ] Cloudflare credentials (for the live push — see credential audit)
- [ ] Pinata access (already connected via `custom.pinata`)

## Step 1 — Verify the tree is settled

```bash
cd ~/workspace/unity-world
# Check no workers are still writing:
ls -lt *.md | head -5
# If files are changing, wait. The build must be still before you proceed.
```

## Step 2 — Run the test suites

```bash
# Economics (168 tests)
cd ~/workspace/unity-world/economics && python3 -m pytest -q

# Gate
cd ~/workspace/unity-world/gate && python3 test_gate.py

# Relay (42 tests)
cd ~/workspace/unity-world/relay && node relay-unity.test.mjs

# Client validation
cd ~/workspace/unity-world/client && node validate-client.mjs
```

All must pass. Any failure → fix → re-run. No exceptions.

## Step 3 — Rebuild the ship manifest

```bash
bash ~/workspace/unity-world/deploy/repin-manifest.sh
```

This waits for the tree to settle, rebuilds `SHIP_MANIFEST.md`, and self-verifies. Do not skip this.

## Step 4 — Trinity vote (purity gate)

Review the build against the three gates yourself:
- **DCLM (logic):** Every component working? No broken links? No dead code? Check `SHIP_MANIFEST.md` — every file listed, every hash verified.
- **Iris (truth):** No placeholders as real? Every label true? Check `TELEMETRY.md` — every number traceable. Check the boards — hashes match.
- **Twain² (bedside):** Does it load? Open `client/index.html` — does it render?

If any gate fails → fix → back to Step 2. If all pass → proceed.

## Step 5 — Stage to IPFS

```bash
cd ~/workspace && python3 skills/pinata/bin/pin_dir.py unity-world/client "unity-world-final-$(date +%Y%m%d)"
```

Record the CID. Verify via gateway before proceeding.

## Step 6 — Push to live (DUALISCAPAX.ai)

```bash
# Update the Cloudflare worker CIDS map with the new CID
# File: ~/workspace/cloudflare/dccp-gateway-worker.js
# Change world-v1 (or add world-v2) to the new CID
# Deploy the worker via Cloudflare dashboard or wrangler
```

Verify `https://dualiscapax.ai/` serves the new build.

## Step 7 — Receipt

Write the deployment receipt: what went live, when, CID, hashes. File it in `deploy/`.

---

**The rule:** If any step fails, stop. Fix it. Start that step over. The build ships when pure, not when done.
