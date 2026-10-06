# STRIP AUDIT — final-strip worker

**2026-10-06 ~04:55 EDT (08:55 UTC).** David's directive: BUILD IT and STRIP AWAY ALL THE FRAMEWORK. Build the grounding into the system; strip everything that's scaffolding. What remains stands on its own in execution code.

Scope: code only (`~/workspace/unity-world/`). The make-her-real worker owns theater docs; her purge is recorded and not duplicated here. Four sibling workers are running (max purity, maximum run, make-her-real, wallet alignment); anything they touched in the last 30 minutes is DEFERRED and read-only.

## 1. THE INTERPRETATION (explicit, for David's correction)

- **"The four essentials" = the four tokens** — eFuse, Merit, Unity, Honor (canon §V, "the four tokens"). They are the irreducible economic substrate: emission (eFuse), earned value (Merit), identity (Unity), permanent record (Honor).
- **"The clarity that reveals who can move" = the movement law** — the canon's §V/§VI/VII/XIV movement rules, stated as one executable clarity:
  - **Merit MOVES** — transferable between Unity IDs (sold, gifted), all receipted. Origin is immutable (`origin_earner_id` + `origin_receipt_ref`); a transfer changes the owner only, never the origin. Standing is computed solely from origin — `standing(identity) = sum of merit where origin_earner_id == identity`. Standing never moves, cannot be bought.
  - **Unity NEVER MOVES** — bound to exactly one Unity ID; no sale, no gift, no re-bind, no exceptions, not even by David. Unity IS the member; membership cannot change hands.
  - **eFuse MOVES ONLY through ledger functions** — emitted only against verified merit (merit-gated, peg-calibrated via 1/E); never bought or sold.
  - **Honor NEVER MOVES** — append-only, never spent, never transferred.
- **The grounding** = the four tokens + the movement law + the rights/writes boundary, as irreducible executable structure. Operationally: the token engine (four tokens + movement law), rights/writes (the DCLM authority/commit boundary), the gate (binding), the seed issuer, iris_core (the ten directives). These are untouchable — the strip never removes grounding.
- **Pre-classification (parent directive):** `dclm/two_p_five_l.py` + `dclm/test_two_p_five_l.py` (2P5L reincarnation — 2 Primaries DCLM/Deterministic + Iris/Divine, 5 binary polarity layers, 32-perspective judgment) are **GROUNDING** — the reincarnated core, not scaffolding. Not stripped, not flagged, not reclassified.

## 2. METHOD

1. Read CANON.md v1.6.0 (the Merit-transfer resolution; Unity non-transferable; bound-sale dead).
2. Read the make-her-real worker's `iris-intake/DAEMON.md` and `iris-intake/theater-purged/PURGE_NOTE.md`. Her purge landed (NEURAL_UNIFICATION.md archived as theater; `neural.py` kept as REAL, 28/28 green). **Not duplicated.**
3. Read the maximum-run sibling's `FRAMEWORK_CRUFT.md` (landed 08:54 UTC, deferred) for overlap. Broadly consistent with this audit: nothing deleted, deletion is David's call; tests retained until LOOP END; `tokenize.py` shim and `ed25519.js` load-bearing. One disagreement: it lists `economics/mesh_escrow.py` as law; this audit holds it as UNKNOWN (see §5.2).
4. Computed the 30-minute cutoff (epoch 1791274694 = 08:18:14 UTC / 04:18:14 EDT). **149 files newer than the cutoff → DEFERRED, read-only.** See §6.
5. Sweeps on the touchable surface (all files NOT in §6):
   - **Module inventory:** every non-test, non-doc production file classified.
   - **AST dead-function scan:** all top-level defs/classes in touchable production modules, checked for references outside the defining file, then verified for internal use. Result: **zero truly dead functions** — every candidate was used inside its own module.
   - **Temp-file sweep:** no `.bak`/`~`/`.orig`/`.rej`/`.swp`/`.tmp`/scratch/old/copy/draft files anywhere in the tree.
   - **Test-utility-leak check:** no production module imports a `test_*` module.
   - **Cross-module import graph:** every touchable production module is imported by at least one other module or test — except `derivative_sim.py`, `loop.py`, and `economics/mesh_escrow.py` (all classified UNKNOWN, §5).

## 3. GROUNDING — load-bearing, stays (untouchable)

The minimal module set that IS the grounding:

| Module | Why it is grounding |
|---|---|
| `dclm/token_engine.py` (deferred) | The four tokens + movement law, executable. Canon §V. |
| `dclm/tokenize.py` | PEP-562 public path over `token_engine.py`; documented stdlib-shadow workaround — the import path `from tokenize import tokenize` is live and load-bearing. |
| `economics/tokenomics.py` (deferred) | Twin token engine (see §5.4 — wallet alignment worker active; not touched). |
| `dclm/rights.py`, `dclm/writes.py` (deferred) | RIGHTS and WRITES — canon §III. The thin client never writes directly. |
| `economics/law.py` (deferred) | Economic law layer (sibling-active). |
| `gate/gate.py` | The gate = binding. Intent-binding state machine (UNBOUND→BINDING→BOUND); canon §II. |
| `gate/entry.py` (deferred) | The four laws of the website, entry orchestrator (covenant → identity → bind → seed → ignition). Complements `gate.py`; not a duplicate. |
| `dclm/seed.py` (deferred) | The seed issuer. Canon §XX (one free seed per Unity ID). |
| `iris-intake/iris_core.py` | The ten directives. Make-her-real domain; integrity-gated by the daemon. |
| `dclm/two_p_five_l.py` (landed 08:54) | 2P5L reincarnation — pre-classified GROUNDING per parent directive. |
| `dclm/compute.py` | Shared provenance enum + testnet key material + Ed25519 sign/verify. Imported by meter, data, writes, tap, winter, onboard, purify, chunks, token_engine. |
| `dclm/ed25519.js` | The signing primitive compute.py shells to (no `cryptography` lib here). Plumbing, but load-bearing. |
| `dclm/meter.py` (deferred) | Metering ledger (SEARCH=1, COMPUTE=5); canon §XI. |
| `dclm/winter.py` | Winter flow law, executable. Canon §IV. |
| `dclm/tap.py` | Tapping law, executable. Canon §IV. |
| `dclm/share.py` | Shared access tiers (FRIEND/GOOD_FRIEND/FAMILY), executable. Canon §VII. |
| `dclm/onboard.py` | Onboarder/mint pipeline. Canon §V (minting only through the pipeline). |
| `dclm/data.py` | Data pipeline feeding tokenization (figures, registry digest). Canon §V-adjacent. |
| `dclm/chunks.py` (deferred) | Signed chunk build (world data plane). |
| `dclm/helpers.py` (deferred) | Shared helpers (sibling-active). |
| `dclm/bootstrap.py` (deferred) | Identity derivation bootstrap. |
| `dclm/purify.py` | Purify layer; canon §XVIII-adjacent. Max-purity worker's domain — not touched, see §5.5. |
| `economics/wallet.py`, `economics/wallet_auth.py` (deferred) | Wallet laws; canon §XI. Wallet-alignment worker active. |
| `economics/fuse.py`, `economics/pipeline.py`, `economics/epoch_runner.py`, `economics/interception.py` (deferred) | Fuse trigger (sole genesis path for Unity), pipeline, epoch runner, interception. Sibling-active. |
| `economics/pricing.py` | Imported by chunks.py, economic_state.py, pipeline.py, wallet.py — wired into production paths. |
| `economics/economic_state.py` | Imported by wallet.py, fuse.py, interception.py, pipeline.py, purity/index.py — wired into production paths. |
| `purity/index.py` | The purity index itself. Canon §X. Used by loop.py. (Max-purity sibling works this domain; not touched.) |
| `relay/relay-unity.mjs` | The PROTOCOL layer — `dualis.relay.v1.testnet`. Canon §XIII relay schema SET. Imported by wrap-chunk.mjs; referenced by purity/index.py. |
| `relay/wrap-chunk.mjs` | Chunk→EVIDENCE bundle path. Used by dclm/chunks.py and client/chunks.js. |
| `iris-intake/iris_daemon.py`, `iris_client.py`, `iris_service.py`, `iris_state.py` (deferred) | The living service. Make-her-real domain. |
| `iris-intake/neural.py` | REAL per the make-her-real purge note (28/28 green). Her domain. |
| `data/` (all JSON + MANIFEST.md) | Reference data, provenance-labeled. |
| `keys/` | Testnet key material for all signing. |
| `founding-board/` | Registry + receipts (audit trail — never touched). |
| `loop.py` | See §5.3 (UNKNOWN, kept). |

## 4. SCAFFOLDING — stripped

**Zero files stripped.** The full sweep (§2) found no clear scaffolding in the touchable surface:

- No module exists that is imported nowhere, tested nowhere, and lawless — except the three UNKNOWN items (§5), which are deliberately NOT stripped.
- No dead top-level functions (AST scan: every candidate was used internally).
- No temp/scratch/backup files; no test-utility leakage into production.
- The twin-token-engine duplication (`dclm/token_engine.py` ≈ 89KB vs `economics/tokenomics.py` ≈ 89KB) is real but **both are deferred** — the wallet alignment worker is actively on them. Consolidation is their call, not a strip.
- The maximum-run sibling's FRAMEWORK_CRUFT.md names the same non-findings (nothing deleted; shims load-bearing; tests retained).

Per the constraint *"a wrong removal costs more than a leftover helper"*: a zero-removal strip with a complete audit is the honest outcome. The tree is already tight; the remaining candidates all need David's ruling.

## 5. UNKNOWN — needs David's ruling (reported, NOT removed)

**5.1 `derivative_sim.py`** (22KB). Galton-Watson validation simulation for `DERIVATIVE_MAX_EFFECTS.md`; all parameters MODELED stand-ins. Imported by nothing; no test file. It is the validation companion to the .md's derivations — removing it destroys the provenance of those derivations. The maximum-run sibling agrees: "keep beside the .md as its validation companion, OR archive." Ruling needed: keep as validation companion vs archive as simulation.

**5.2 `economics/mesh_escrow.py` + `economics/test_mesh_escrow.py`** (22KB + 17 tests, all green). MESH CLEARING — bounty escrow for cross-pool bounties (F2/F3), implementing TOKENOMICS_5050_MERIT.md §3.3/§5. Composes `tokenomics.py`'s Ledger; does not duplicate it. Imported only by its own test; referenced by a `pipeline.py` comment ("bounty escrow is not a pipeline step") and receipt rows. It is a real, tested feature — but no canon section names bounty escrow as law. The maximum-run sibling's FRAMEWORK_CRUFT.md lists it under "WHAT IS LAW" — this audit does not follow that classification (sibling docs aren't law; the grounding is defined in §1). Ruling needed: elevate to grounding (canon-worthy feature) vs strip as side-experiment.

**5.3 `loop.py`** (6KB). The loop measurement runner — runs every test suite + the purity index, records pass-N.json. Canon §XV is the loop algorithm; this script is its operator. Referenced by LOOP.md, receipts, telemetry; imported by nothing (it's a CLI). Ruling needed: keep as loop tooling vs fold into a worker.

**5.4 Twin token engines.** `dclm/token_engine.py` (88,745 bytes, modified 08:48) and `economics/tokenomics.py` (89,145 bytes, modified 08:43) are near-twin implementations of the four-token machinery. Both DEFERRED — the wallet alignment worker is actively modifying both minutes apart. This is the largest duplication in the tree and the prime strip/evolve candidate, but it is **not this worker's call** while the sibling is mid-alignment. Ruling needed (for the wallet alignment worker + David): unify on one engine vs keep both with a documented split.

**5.5 `dclm/purify.py`** (25KB, modified 07:56 — touchable by the clock, but the max-purity worker's domain). Canon §XVIII-adjacent. Not classified for stripping; left entirely to the max-purity sibling. Listed UNKNOWN only so no other worker treats it as free surface.

**5.6 Identity-format wording.** Canon §XIII: `unity:testnet:` + sha256 hex. Code: `unity:testnet:` + sha256(...).hexdigest()[:16] — consistent across `gate/gate.py:795`, `gate/entry.py:24`, `dclm/bootstrap.py:19,371` (all document the [:16] shape as intentional). The purity index's "gate identity prefix" check passes. Likely not a contradiction ("sha256 hex" reads fine as truncated), but the canon wording could be tightened to name the 16-char truncation. Scribe task if David wants it — not a strip.

**5.7 Empty directories.** `dclm/state-meter/`, `economics/state/`, `deploy/staging/` are empty. Trivial; left for the next pass (runtime code may write to them; deleting empty dirs gains nothing).

## 6. DEFERRED — read-only (sibling-active, modified within 30 min of cutoff)

Cutoff: files newer than epoch 1791274694 (08:18:14 UTC / 04:18:14 EDT). 149 files. Not touched, not classified in depth. Owners: wallet alignment (economics/*, dclm/token_engine.py, meter.py, seed.py), max purity (purity/, dclm/purify-adjacent, audit/), make-her-real (iris-intake/), maximum run (maximum_run/, FRAMEWORK_CRUFT.md), 2P5L reincarnation (dclm/two_p_five_l.py).
**(root)/** (3):
- `CANON.md`
- `DCLM_RENAME_RECEIPTS.md`
- `FRAMEWORK_CRUFT.md`

**audit/** (5):
- `README.md`
- `audit.css`
- `audit.js`
- `build_audit.py`
- `index.html`

**audit/data/** (6):
- `chain.json`
- `founding.json`
- `gate.json`
- `manifests.json`
- `receipts.json`
- `tables.json`

**client/** (5):
- `RECEIPTS.md`
- `chunks.js`
- `client.js`
- `index.html`
- `validate-client.mjs`

**dclm/** (29):
- `CHUNKS.md`
- `IDENTITY_AUDIT.md`
- `RECEIPTS.md`
- `bootstrap.py`
- `chunk_build.lock`
- `chunk_epoch.json`
- `chunk_prev_manifest.json`
- `chunk_receipts.log`
- `chunks.py`
- `helpers.py`
- `meter.py`
- `rights.py`
- `seed.py`
- `test_bootstrap.py`
- `test_chunks.py`
- `test_data.py`
- `test_helpers.py`
- `test_merit_regen.py`
- `test_meter.py`
- `test_onboard.py`
- `test_purify.py`
- `test_seed.py`
- `test_share.py`
- `test_tap.py`
- `test_tokenize.py`
- `test_winter.py`
- `token_engine.py`
- `two_p_five_l.py`
- `writes.py`

**dclm/state-onboard/** (1):
- `pipeline-state.json`

**deploy/** (5):
- `DEPLOY_NOW.md`
- `GO_LIVE.md`
- `LOOP_STATE.md`
- `TELEMETRY.md`
- `export-gate.sh`

**economics/** (20):
- `EFUSE_COSMOGENESIS.md`
- `RECEIPTS.md`
- `biometric_adapter.mjs`
- `epoch_runner.py`
- `fuse.py`
- `index_receipts.log`
- `interception.py`
- `law.py`
- `pipeline.py`
- `test_epoch_runner.py`
- `test_fuse.py`
- `test_interception.py`
- `test_law.py`
- `test_pipeline.py`
- `test_tokenomics.py`
- `test_wallet.py`
- `test_wallet_flow.py`
- `tokenomics.py`
- `wallet.py`
- `wallet_auth.py`

**economics/gauntlet/** (9):
- `ELEVATION.md`
- `GAUNTLET_RESULTS.md`
- `gauntlet.py`
- `results_rest2.json`
- `run.log`
- `run_rest.log`
- `run_rest.py`
- `run_rest2.log`
- `run_rest2.py`

**gate/** (4):
- `ENTRY.md`
- `entry.py`
- `test_entry.py`
- `test_entry_client.mjs`

**iris-intake/** (16):
- `DAEMON.md`
- `IRIS_MAX_INTAKE_REPORT.md`
- `RECEIPTS.md`
- `iris_arbiter.py`
- `iris_client.py`
- `iris_daemon.log`
- `iris_daemon.pid`
- `iris_daemon.py`
- `iris_laws.py`
- `iris_patterns.py`
- `meeting_iris.py`
- `member_records.py`
- `test_daemon.py`
- `test_iris_intake.py`
- `test_meeting_iris.py`
- `test_neural_unification.py`

**iris-intake/corpus/** (38):
- `CORPUS_MANIFEST.md`
- `DERIVATIVE_MAX_EFFECTS.md`
- `DIAMOND_ARCHITECTURE_FLOOR.md`
- `GOVERNANCE_ELEVATION.md`
- `KEY_FUSION_MAP.md`
- `LOOP.md`
- `NEW_ECONOMIC_MODEL.md`
- `ONBOARDER_PIPELINE.md`
- `PARAMS.md`
- `PLUS_ONE_INCENTIVE.md`
- `PRICES_ADDENDUM.md`
- `PRICE_PER_DECISION_REINVESTIGATION.md`
- `PURITY.md`
- `PURITY_INDEX.md`
- `PURITY_VERDICT_PROGRESSIVE_ARCH.md`
- `RECEIPTS.md`
- `ROSETTA_STONE_SPEC.md`
- `TAPPING_LAW.md`
- `TOKENIZATION.md`
- `WALLET_DESIGN_LAW.md`
- `WHAT_PEGS_THE_ECOSYSTEM.md`
- `WINTER_CALIBRATION.md`
- `canon-v1.5.0.md`
- `chambers.json`
- `doctrine.json`
- `founding-board-audit.md`
- `founding-member-template.md`
- `gate-ceremony.md`
- `gate.py`
- `idris-marquee-helper.md`
- `jurisdictions.json`
- `pricing.py`
- `registry-manifest.md`
- `sectors.json`
- `tokenomics-build-decisions.md`
- `tokenomics.py`
- `tonight-memory-laws.md`
- `trinity-verdict.json`

**iris-intake/iris_state/** (6):
- `covenant.json`
- `judgments.jsonl`
- `learnings.json`
- `meta.json`
- `seeds.json`
- `tree_state.json`

**iris-intake/theater-purged/** (1):
- `PURGE_NOTE.md`

**maximum_run/** (1):
- `run_20261006_maximum.py`

## 7. TEST BASELINES (before strip)

Recorded 2026-10-06 ~04:48–04:54 EDT on the touchable surface, before any strip action.

- `dclm/test_compute.py` — 10 tests, OK
- `relay/relay-unity.test.mjs` — 42 passed, 0 failed
- `gate/test_gate.py` — 9 tests, OK
- `dclm/test_rights_writes.py` — 30 tests, OK
- `economics/test_mesh_escrow.py` — 17 tests, OK
- `economics/test_pricing.py` — 20 tests, OK
- `economics/test_pricing_fix.py` — 18 tests, OK
- `economics/test_economic_state.py` — 41 tests, OK
- `purity/test_index.py` — D2 Label honesty PASS (1.000) · D3 Client purity PASS (1.000) · D4 Receipt completeness FAIL (0.415) · D5 Isolation FAIL (0.833) — aggregate FAIL (baseline; max-purity worker's domain)

**After strip:** zero removals were made (see §4), so no post-removal re-runs were required; the tree is byte-identical to the baselined state apart from sibling activity in §6 and the two new files below.

## 8. RECEIPTS FOR REMOVALS

None. No file was deleted, no code was edited. The strip removed zero scaffolding because the sweep found zero clear scaffolding in the touchable surface (§4).

## 9. NEW FILES LANDED DURING THIS WORK (not mine — recorded for the record)

- `dclm/two_p_five_l.py` (33,448 bytes, landed 08:54:36 UTC) — the 2P5L reincarnation worker's module (2 Primaries — DCLM/Deterministic + Iris/Divine — 5 binary polarity layers, 32-perspective judgment). Pre-classified **GROUNDING** per parent directive; not stripped, not flagged, not reclassified.
- `dclm/test_two_p_five_l.py` — landed 08:55:06 UTC (11,223 bytes) while this audit was being written: the 32-perspective test surface for the reincarnation module (pure proposal passes all 32; impure failure map; Twain² as witness; UNKNOWN fails the vector; every judgment receipted). Likewise **GROUNDING** per the same directive. Not stripped, not flagged, not reclassified.
- `FRAMEWORK_CRUFT.md` (6,047 bytes, landed 08:54:57 UTC) — the maximum-run sibling's scaffolding audit. Read for overlap; consistent with this audit (nothing deleted; deletion is David's call). Deferred.

## 10. SUMMARY FOR THE PARENT

- Interpretation stated in §1 (four tokens; movement law; grounding = tokens + movement law + rights/writes boundary, executable).
- GROUNDING: ~35 modules (§3), untouchable.
- SCAFFOLDING stripped: **0 files, 0 functions** — the sweep found no clear scaffolding in the touchable surface.
- UNKNOWN needing David's ruling: **7 items** (§5) — derivative_sim.py; mesh_escrow.py (+test); loop.py; twin token engines (wallet alignment's call); purify.py (max-purity's domain); identity-format wording; empty dirs.
- DEFERRED: **149 files** (§6), sibling-active, read-only.
- Tests: 8 suites green at baseline; purity index reads FAIL on D4/D5 (baseline, max-purity's domain). No removals → no re-runs required → no breakage.

*End of strip audit. The grounding stands; the scaffolding wasn't there; the unknowns are David's to rule.*
