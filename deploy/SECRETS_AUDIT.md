# SECRETS AUDIT — unity-world final ship

**Auditor:** Secrets Auditor (subagent, depth 2/2) — parent orchestrator
**Date:** 2026-10-06 ~04:00 EDT
**Order from David:** (1) passphrase stays pure — secrets never touch the shippable artifact; (2) drop the framework — strip all scaffolding, only what ships.

## Scope scanned

- `~/workspace/unity-world/client/` (website)
- `~/workspace/unity-world/founding-board/` (boards)
- `~/workspace/unity-world/deploy/` (telemetry, receipts, plans)
- `~/workspace/unity-world/*.md` (canon, economics docs, architecture docs)
- `~/workspace/unity-world/data/` (registries)
- `~/workspace/unity-world/economics/*.md` (docs only)

Also probed the adjacent tree for anything that could leak in: `keys/`, `passes/`, `__pycache__/`, all `.py` files, and the known secret locations outside the tree.

## Method

- Pattern sweeps over the full scope: `BEGIN (RSA|EC|OPENSSH) PRIVATE KEY`, ENCRYPTED PRIVATE KEY, `sk-…`, `ghp_…`, xox tokens, `api_key = "..."`, bearer tokens, `password =`, `passwd`, `seed phrase`, `mnemonic`, `bip39`, `wallet_key`, `secret_phrase`, `passphrase`, `client_secret`, base64 blobs ≥64 chars, 64-char hex strings (context-checked).
- File-type sweeps: `*.key`, `*.pem`, `.env*` in scope.
- Internal-path sweeps: `/home/hatch/`, `/root/`, `/tmp/` in every ship-scope file.

## Findings

### Secrets found IN the ship scope: **0**

No private keys, passphrases, seed phrases, API keys, auth tokens, wallet keys, credentials, `.key` files, `.env` content, or `BEGIN PRIVATE KEY` blocks anywhere in the ship scope.

Checked-but-benign matches (NOT secrets):
1. **`relay/relay-unity.mjs`** (outside ship scope; noted for completeness) — matched the word "mnemonic" only inside a *guard regex* that REFUSES secret-like payloads. That is the protection, not a leak.
2. **`KEY_FUSION_MAP.md`** — "the Fuse holds NO private key" — explicit statement of non-custody. Benign.
3. **`data/trinity-verdict.json`** — "private key stays on-device" (WebAuthn-derived pilot handle note). Descriptive, no key material.
4. **107 distinct 64-hex strings** in `client/index.html`, `founding-board/founding-board.json`, `data/trinity-verdict.json` — all context-checked: every one is a sha256 *digest* (packet hashes, artifact hashes, acknowledgment hashes). Digests are publishable; they are not key material.
5. **Founding board** — entry carries member_number, `unity_id: "Idris"`, designation, and role. No name, no location, no PII — consistent with the sounding-board privacy law. "David Di Genova" appears as `declared_by` — that is David's own public attribution in his own canon docs, not a leak.

### Issues found and handled

1. **Sanitized (twice): internal absolute path in a ship file.**
   `founding-board/idris-marquee-helper.sha256` contained a `/home/hatch/...` absolute path. Rewritten to filename-only standard sha256sum format, preserving the recorded hash verbatim both times (first the original `93f96843…` pin, then — after the sibling worker re-pinned — the new `eda56825…` pin).

   **Concurrent-modification note:** a sibling swarm worker was actively editing ship files during this audit (new founding-board content: the bot brotherhood name, updated acknowledgments, new `client/chunks.js`, `founding-board/AUDIT.md`, `founding-board/founding-board-schema.json`, `founding-member-template.md`, `PRICE_PER_DECISION_REINVESTIGATION.md`, plus a `RECEIPTS.md` ledger extension). The manifest was rebuilt three times total; the final build covers **46 scope files** (the new canon doc included, secret-scanned clean) and was re-verified against disk immediately before handoff. The parent should treat the manifest as a snapshot — re-pin hashes as the last step of the swarm if more edits land.

2. **⚠ RESOLVED MID-AUDIT — hash re-pinned by a concurrent worker, sanitize re-applied.**
   `founding-board/idris-marquee-helper.sha256` originally recorded `93f96843…` (David's pinned acknowledgment) while the `.md` had since been edited. During this audit, a sibling swarm worker rewrote the `.md`, re-pinned the `.sha256` file to the new hash `eda56825…` (matches the current file byte-for-byte), and updated `founding-board.json`'s `acknowledgment_sha256` to match. The auditor verified: `.md` sha256 == `.sha256` record == `founding-board.json` record. However, the re-pin reintroduced the absolute internal path (`/home/hatch/...`), so the auditor sanitized it a second time to filename-only format, preserving the new pin. **Note:** the historical `93f96843…` pin recorded in MEMORY is superseded by `eda56825…` — the parent should confirm David is aware the acknowledgment text grew and the pin moved.

3. **Near-miss, outside scope, verified contained.**
   `~/workspace/unity-world/keys/unity-world-test.key` is a REAL raw DER Ed25519 private key (plus `unity-world-test.pub`), living inside the unity-world tree but **outside** the ship scope. It is excluded from the manifest and must never be added. Same for the known secret locations outside the tree — confirmed they hold key material and confirmed none of it is duplicated into scope:
   - `~/workspace/testnet/keys/` (testnet-daemon.key, testnet-ipns.key, testnet-relay.key)
   - `~/workspace/ipfs-publish/wallet.key`
   - `~/workspace/ipfs-publish/w3name-pub/*.key` (no `.key` files found there — directory check clean)
4. **`passes/pass-1.json`** (test-pass receipts, outside scope) contains absolute internal paths — excluded from the ship, so no sanitize needed. Do not ship it later without sanitizing.

## Framework strip list — EXCLUDED from the ship

| Excluded | Why |
|---|---|
| `keys/` (incl. `unity-world-test.key`, `unity-world-test.pub`) | Real private key material — never ships |
| `passes/` (incl. `pass-1.json`) | Internal test-run receipts with absolute internal paths; scaffolding, not ship |
| `dclm/`, `gate/`, `purity/`, `relay/` | Engine/scaffold code — not in ship scope (website + boards + docs + registries only) |
| `*.py` — `loop.py`, `derivative_sim.py`, `economics/*.py` | Python source stays in repo; only `.md` docs ship (per strip rules; David may override — see decision item below) |
| `economics/test_*.py` (6 files) | Test files — don't ship |
| `__pycache__/`, `*.pyc` (root + economics/) | Build artifacts — don't ship |
| `client/validate-client.mjs` | Validator — stays in repo, does not ship to public web (per strip rules) |
| `deploy/staging/` | Empty staging dir — carried as an empty directory marker only |
| `~/workspace/testnet/keys/`, `~/workspace/ipfs-publish/wallet.key`, `~/workspace/ipfs-publish/w3name-pub/*.key` | Known secret locations — outside the tree, never in the package |

## Decision items for David / parent orchestrator

1. **Python source:** all `.py` (engine, economics, wallet, tokenomics) stays in repo per strip rules — docs ship, code doesn't. If David wants the code in the package (e.g. for a code-forward launch), say so and the manifest gets rebuilt.
2. **Acknowledgment hash mismatch** (issue 2 above) — re-pin or acknowledge-and-leave.
3. **Data registries** (`data/*.json`) ship as public data — confirm that is the intent (they are pilot-mode/modeled public figures, labeled as such).

## Manifest currency

`SHIP_MANIFEST.md` was rebuilt four times; sibling writers were still actively editing ship files at handoff (`client/client.js`, `client/index.html`, `economics/NEW_ECONOMIC_MODEL.md` all changed within the last minute). The manifest is therefore a **snapshot**, not a final pin. `deploy/repin-manifest.sh` is provided for the parent orchestrator to run ONCE as the last step of the swarm: it waits for the tree to settle (two identical snapshots 30s apart, up to 5 min), rebuilds the manifest over the final state, and self-verifies (exit non-zero if dirty). The script itself is deploy tooling — it does not ship.

## Verdict

**PASS for ship** — the ship scope carries zero secrets. Two sanitizes applied (absolute paths removed, pins preserved), the sibling worker's hash re-pin verified consistent across `.md` / `.sha256` / `founding-board.json`. Nothing was auto-corrected that requires David's judgment — except noting that the historical `93f96843…` pin in MEMORY is superseded by `eda56825…`.
