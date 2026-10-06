# TELEMETRY RECORD — Unity World Final Ship

**Assembled:** 2026-10-06 ~08:20 UTC (04:20 EDT)
**Ordered by:** David — "ALL the telemetrics: every measurement, every benchmark, every mesh result, every test outcome."
**Scope:** the full record of what was built and measured. Not "everything is done" — "everything that exists, recorded."
**Network:** TESTNET ONLY. Nothing here touches production keys, mainnet schemas, or live funds.

**Reading convention (per David's law):**
- **REPORTED** = measured by running code against this box (value + method + n).
- **MODELED** = computed from measurements (extrapolation, projection).
- **UNKNOWN** = not measured. Never passed, never filled in.

**Point-in-time warning:** the build is under ACTIVE concurrent construction at write time (files edited mid-measurement — e.g. `dclm/test_chunks.py` edited 08:07 UTC during its own test run, `dclm/chunks.py` edited 08:15 UTC). Every number below is a snapshot, not a seal. Re-run before trusting.

---

## 1. Test summary table

Every suite re-run for this record on 2026-10-06 ~07:58–08:25 UTC unless noted. No number invented — each traces to the run.

### 1a. economics/ (tokenomics engine)

| Suite | Tests | Pass | Fail/Error | Status | Notes |
|---|---|---|---|---|---|
| test_tokenomics.py | 89 | 89 | 0 | OK | Grew from 55 (receipted at 07:05) to 64 to 89 across concurrent edits |
| test_wallet.py | 41 | 41 | 0 | OK | Grew from 33 (receipted 07:12) to 41 |
| test_economic_state.py | 41 | 41 | 0 | OK | Matches receipted 41 |
| test_fuse.py | 19 | 19 | 0 | OK | Matches receipted 19 |
| test_mesh_escrow.py | 17 | 17 | 0 | OK | Unreceipted suite (no receipt row) |
| test_pricing.py | 20 | 20 | 0 | OK | Matches receipted 20 |
| **economics total** | **227** | **227** | **0** | **ALL GREEN** | README.md documents "168/168" — an older count; measured now **227/227** |

### 1b. dclm/ (compute core)

| Suite | Tests | Pass | Fail/Error | Status | Notes |
|---|---|---|---|---|---|
| test_compute.py | 10 | 10 | 0 | OK | Matches receipted 10 |
| test_merit_regen.py | 27 | 27 | 0 | OK | Grew from 23 (receipted 07:40) to 27 |
| test_chunks.py | 25 | 23–24 | 1–2 (flaky) | **NOT GREEN** | 1st run: failures=2; re-run: failures=1 (`test_epoch_build_receipted`, subprocess assertion "28 != 29"). File edited 08:07 UTC mid-run by a concurrent worker — flaky under construction, cannot certify |
| test_data.py | 22 | 19 | 3 errors | **NOT GREEN** | All 3 errors in `TestFeeds`: `purify.py` (landed 07:56) now raises `PurificationRefused` in `ingest_reading()` where tests expect feed-status returns — contract change not yet reconciled |
| test_meter.py | 20 | 16 | 4 errors | **NOT GREEN** | Same root cause: `purify_input()` wired into `meter.py` (lines 358, 445) raises instead of returning signed-refusal envelopes the tests assert |
| test_rights_writes.py | 30 | 29 | 1 failure | **NOT GREEN** | Receipted 30/30 at 07:02; now 1 failure (purify-contract knock-on) |
| test_winter.py | 28 | 27 | 1 error | **NOT GREEN** | Receipted 28/28 at 07:19; now 1 error (purify-contract knock-on) |
| test_tap.py | 24 | 22 | 1 failure + 1 error | **NOT GREEN** | Receipted 24/24 at 07:45; regressed |
| test_share.py | 29 | 27 | 2 errors | **NOT GREEN** | Receipted 29/29 at 07:23; regressed |
| test_tokenize.py | 64 | 62 | 2 failures | **NOT GREEN** | Suite grew 49 (receipted 07:35) → 64 tests across concurrent edits (`token_engine.py` edited 08:25:56 UTC, `test_tokenize.py` 08:22 UTC mid-run). Ran 64 tests in 513.6s, FAILED (failures=2). Failure details not captured — the run chain was terminated during the following suite. Treat as provisional |
| test_onboard.py | 24 | — | 1 error (partial) | **NOT GREEN (partial)** | Timed out at 100s in TestRegression (subprocess re-run of meter suite); 1 ERROR observed before timeout (`test_replay_never_double_counts`). Receipted 24/24 at 07:34 |
| test_seed.py | 16 | 15 | 1 error | **NOT GREEN** | `test_non_testnet_refused`: `seed.issue_seed()` now raises `PurificationRefused` where the test expects a refusal return — same purify-contract root cause. Unreceipted suite |
| test_purify.py | 54 | 54 (re-run) | 4 errors → 0 | **FLAKY** | 1st run: 4 errors; re-run 54/54 OK. Result flips between runs — file under live concurrent edit. Unreceipted suite |

**The dominant dclm finding:** eight suites regressed after `dclm/purify.py` landed (07:56 UTC) and was wired into `data.py`/`meter.py`/`seed.py`. The new contract raises `PurificationRefused` on bad identity where the old contract returned signed refusal envelopes. The purification is arguably stricter/honester — but the test suites were written against the old contract and now fail. This is a merge conflict between two workers, not a logic bug in either.

### 1c. Purity index (the measurer, measured)

| Suite | Tests | Pass | Status | Notes |
|---|---|---|---|---|
| test_index.py | 50 | 50 | OK | Grew 27 → 46 (receipted 07:42) → 50 now; its embedded live-run reports the same D1/D3/D4/D5 FAIL picture as §4 (D4 fell to 0.385 by 08:30 UTC as workers kept editing) |

### 1d. gate/

| Suite | Tests | Pass | Status | Notes |
|---|---|---|---|---|
| test_gate.py | 9 | 9 | OK | Matches receipted 9/9 (6 original + 3 reframe tests) |

### 1e. relay/ (Node)

| Suite | Tests | Pass | Status | Notes |
|---|---|---|---|---|
| relay-unity.test.mjs | 42 | 42 | OK | "42 passed, 0 failed" — matches RECEIPTS.md |

### 1f. client/ (Node)

| Suite | Checks | Pass | Status | Notes |
|---|---|---|---|---|
| validate-client.mjs | 141 | 141 | OK | RECEIPTS.md recorded **63/63** (~03:00 EDT); the validator + client were extended after receipt without new receipt rows. Measured now: **141/141 checks passing** |

### 1g. testnet/

| Suite | Tests | Pass | Status | Notes |
|---|---|---|---|---|
| relay-testnet.test.mjs | 14 | 14 | OK | "14 passed, 0 failed" — matches README |
| unification-proof.mjs | 17 | **0** | **HARNESS BROKEN** | Crashes at step [1]: `TypeError: Cannot read properties of undefined (reading 'manifest_hash')` — `enqueueBind()` returns no `entry`. README claims "17 end-to-end proofs, all passing" — **does NOT reproduce**. 0/17 complete. |

### Totals

- **Green:** economics 227/227 · dclm compute 10/10 · dclm merit_regen 27/27 · dclm purify 54/54 (flaky) · purity index 50/50 · gate 9/9 · relay 42/42 · client 141/141 · testnet relay 14/14 → **574 passing**
- **Red:** dclm chunks 1–2 flaky · data 3 errors · meter 4 errors · rights_writes 1 failure · winter 1 error · tap 1 failure + 1 error · share 2 errors · seed 1 error · onboard 1 error (partial run) · **tokenize 2 failures (64 tests)** → **17–18 failing**
- **Broken harness:** unification proof 0/17 (crash, not a test failure)

---

## 2. Benchmark summary

### 2a. Iris benchmark teams (measured 2026-10-06, `~/workspace/iris-benchmark/`)

**team2-gate — gate throughput + adversarial purity** (REPORTED)
- Iris gate check throughput: **~568K–1.35M checks/sec** (0.7–1.8μs each, n=5000), 0 breaches of the 4.20ms bound on read paths
- MAX CHAOS battery: **399,265 adversarial evaluations** — 182,054 fail-closed (45.6%), 1,000/1,000 correct approvals under contradictory verdicts, **300 fail-open (0.075%)**: an injected chaos ledger returning `{"status": "SUFFICIENT", "keys_available": -50}` was authorized 300/300 (`_normalize_ledger_view` coerces numerics without a `>= 0` invariant). Seam-only (production adapter computes from real balance), recommendation recorded, production untouched
- ≤4.20ms bound: **HOLDS on every read/evaluation path, BREACHES on the paid-intent path and on mutations**
- Concurrency: 4 threads × 200 bind+confirm on one instance → 800 attempted, 800 BOUND, 0 lost updates; `test_gate.py` green during 4-thread hammer

**team3-dclm — DCLM throughput + chaos** (REPORTED)
- DCLM decision throughput: **102,038 decisions/sec/core** (mean 0.0098ms, p99 0.024ms, n=500, `rings.py Parliament.collapse`)
- rights.py: PURE. writes.py: PURE (slow but honest). meter.py: concurrency risk by inspection (no locks), did not manifest in 700 concurrent debits
- **token_engine.py: BROKEN UNDER CHAOS** — duplicate delivery of the same VERIFIED receipt double-applies: merit 100.0 → 200.0, eFuse registry 1 → 2, no refusal raised. `tokenize()` never checks `manifest_hash` against processed receipts — relay idempotency NOT enforced at this layer. 11/11 other fail-closed paths hold. Fix status: UNKNOWN (wallet.py got a caller-supplied-manifest idempotency fix; token_engine's own fix unconfirmed)

**team4-economics — economics pipeline + chaos** (REPORTED)
- Sign: ~1.285/sec (mean 778ms); verify: ~1.52/sec — **node subprocess spawns are the binding constraint** (~0.77 signed+verified states/sec serial; pure-Python compute ~1000× faster)
- Emission: mean 0.2057ms (n=5000); state latency mean 1.37ms (n=200)
- Chaos findings: F1 (self-labeled REPORTED/VERIFIED fallback billing) MEDIUM; F2/F3 (NaN/+inf pass numeric checks) MEDIUM; F6 (None entries → uncaught AttributeError, fail-stop) LOW; 21 clean refusals; **0 token-minting events**

**team5-live — relay throughput + chaos** (REPORTED, shared live testnet)
- Relay single POST: ~4ms mean (2.2–5.8ms, n=5, 127.0.0.1:18081)
- Sustained: **~19.3 rps @ c=2, 19.6 @ c=8, ~10 @ c=32–128**; p50 90ms @ c=2 → 354ms @ c=8 → 5.8s @ c=128 (distress tripwire, conn errors)
- C3 malformed flood: 915/915 rejected, servers healthy. **C5 cross-process race: VIOLATED — silent truncation of the relay outbox 1,735 → 59 bundles** (~1,676 bundles destroyed, zero errors returned; non-atomic read-modify-write with `catch → []` fallback). Fix (atomic rename + fail-loud) recommended, not confirmed built
- Bottom line: relay's *judgment* pure under chaos; relay's *memory* fragile. Throughput ceiling ~19 rps relay / ~43 rps enqueue / ~10 rps deliver, bound by synchronous full-file rewrites

**team7-iq — Iris judgment battery** (REPORTED)
- Iris effective IQ **1.0** (David's operational definition: judgment accuracy × completeness × purity): 41-case battery — 20 executed against real gate/tokenomics/wallet/fuse/rings code, 21 Trinity-judged and Parliament-collapsed under 4 configurations — **104 verdict observations, zero misses**
- 7 of 61 candidate verdicts were perfectly pure and perfectly wrong (purity ≠ intelligence)
- Bounded by David's input: **13 HELD parameters** (E most load-bearing — nothing emits without it), 2 calibrations in flight, 1 law moved under the benchmark (Merit transferable)

**team8-state — max known state** (REPORTED, 2026-10-06 ~03:35 EDT)
- 58 substantive law statements, 25 DERIVED, **17 held parameters system-wide** (4 canon + 13 tokenomics PARAMS.md)
- Honesty flag: canon's §XVI seal record says 46/26/5 but this pass counts 45/25/4 — discrepancy unresolved, flagged not smoothed
- 19 named datasets; 227 countries / 1251 cities (REPORTED, VENDOR-RECOVERY)

**team6-teach-topic — purity transmission under hostility** (REPORTED)
- Battery: does Iris teach TRUE things under worst conditions (hostile learners, max throughput, chaotic domain jumps)? Findings per-case in `REPORT.md`; `rings.collapse()` returns bare Point(x,y,z) — explanation content zero; verdicts carry question+candidates+status+balance+provenance but no "why this candidate won" prose

### 2b. Mesh performance (from SWARM_INSTANT_CALCULATION.md)

- **Calculated (MODELED): 8 warm bots, cache-first → ~25–65ms per full mesh query** vs 1.0s target. Theoretical floor 1–5ms; relay-mediated alternative 30s; cold-spawn 10–60s
- Binding constraint: the ~20 rps testnet relay (throughput wall, not parallelism) + 10–30s subagent cold-spawn
- Preconditions (non-negotiable): warm pool, cache-first reads (relay write-only), sector sharding, DCLM synthesis (6ms measured for 600 verdicts)
- UNKNOWN: relay under a rewritten high-throughput design (not built); multi-machine fan-out; fresh-gather query time

### 2c. Gauntlet (economics throughput probe — STALE, not green)

- `results.json` (07:54): **all 6 sections raised exceptions**; critical: token_engine import failure (since resolved — suites import cleanly now)
- `run.log` (08:01): eFuse section `AssertionError: bal == 4203, expected 4200` (state pollution across re-runs)
- Throughput numbers that did print (REPORTED, from a partial run): eFuse `receive_emission` ~1,089–1,383 ops/sec (flat to 3000 ops, no knee); merit `accrue_merit` ~6,969–7,178 ops/sec; engine tokenize (accrue+mint, 2 signed commits) ~0.1/sec (689ms/op — node-sign bound); wallet.transfer_merit ~0.4/sec (2,390ms/op)
- Verdict: the gauntlet is a benchmark tool with stale/broken artifacts — its numbers are observations, not a pass/fail gate

### 2d. UNKNOWN benchmarks (never measured)

- Relay behavior under a rewritten high-throughput relay (not built)
- Multi-machine fan-out latency (single box measured)
- Fresh web-gather query time (depends on web, unknowable in advance)
- Chunk-serving throughput / progressive-load timings (chunks.js + dclm/chunks.py landed 08:02/08:15, unbenchmarked)
- Live-browser verification of the client (no live browser in this runtime; validator-only)
- Any mainnet measurement (none exist — testnet only, by law)

---

## 3. Mesh results summary

Source: `~/workspace/mesh/MESH_MAP.md` (pilot running 2026-10-06; Wave 4 fan-out COMPLETE ~03:45 EDT).

### 3a. Topology totals (traceable)

| Level | Count | Source |
|---|---|---|
| Jurisdictions (L1) | 24/24 | MESH_MAP.md "24 country jurisdictions" |
| Sector cells (L2) | 99 | water 22 · energy 10 · food 10 · pharma 24 · climate 10 · pandemic 11 (+ 9 pilot cells + 21 chamber audits + 3 pilot jurisdiction meshes) |
| Chamber audits | 21/21 | 10 batch workers + chamber registry |
| Derivative micro-swarms (L3) | **~423** | 43/43 wave-2 (registry) + ~380 executed inline across 10 wave-4 batches |
| Mesh exchanges (L4) | 30 | 6 sector + 24 jurisdiction |
| Relay bundles posted | **485** | 9 (wave-1) + 43 (wave-2) + 6 (wave-3) + 427 (10 wave-4 batches: 44+40+49+40+43+48+49+30+44+40) |
| Batch workers | 10 | BATCH-1 … BATCH-10 |
| Exchange workers | 10 | sector ×6 + jurisdiction ×24 coverage |

### 3b. Headline findings

- **Cross-cutting law 1:** publication posture > infrastructure — binding constraint in ~23/24 jurisdictions
- **Cross-cutting law 2:** measured-vs-modeled fault line — global across food, energy, climate; grades must follow provenance
- **Cross-cutting law 3:** keyless-vs-keyed is the true horizontal axis — not open-vs-closed
- **Cross-cutting law 4:** critical-dimension rule — a sector whose critical dimension is entirely modeled/unknown is GAPPED by definition
- **Cross-cutting law 5:** split-grade principle — grade sub-dimensions, not headlines (NG-pandemic surveillance NEAR / mortality GAPPED generalizes to all 11)
- **Cross-cutting law 6:** sealed dim-7 gates uniform grading — a free key is not openness; Trinity ruling pending
- **Relay hash contract (resolved, canonical):** `manifest_hash` = sha256 over Node-`JSON.stringify` canonical form of `{kind, envelope, endpoint, unityId}` — sort_keys, separators `(",",":")`, **ensure_ascii=False** (raw UTF-8). Python `ensure_ascii=True` produces relay-rejected bundles for non-ASCII envelopes. Recommend Trinity amend the hash spec
- **Registry corrections:** ≥31 explicit (water 15, climate 7, pandemic 9; energy 0 re-grades) + CN-food NEAR→GAPPED, US-climate →NEAR-CONDITIONAL, CA-food re-grade flagged, FR-pandemic freeze date 23 Jun 2023 (not 1 Jul), CCAP DISCONTINUED (CA-food-T1, major correction), 12 honest UNKNOWNs (sandbox WAF-blocks)
- **Blocking (David's hand only):** EIA + NASS free email registrations; 3 Wave-1 bundles still don't reproduce under hash formula (unicode drift — reported to Trinity, undiagnosed); sealed dim-7 vs free-key tension (Trinity ruling gates uniform grading)

### 3c. Chunked serving (progressive loading — the Trinity-verdict implementation)

- `dclm/chunks.py` + `client/chunks.js` implement the readjustment protocol: head document (world_version), version-pinned streams, no-downgrade rule, STALE labeling, tiered freshness, hash-on-read
- Chunk state at write time: **world_epoch 23, 19 chunks, 746,835 bytes, schema v1, 18 datasets** (`chunk_receipts.log`)
- Both files unreceipted (landed 08:02/08:15 UTC); test_chunks.py flaky under concurrent edits (see §1b)

---

## 4. Build receipts (sha256 of major deliverables)

From the six `RECEIPTS.md` ledgers. "Receipted" = ledger's latest row for that file. **Drift flag** = disk hash no longer matches the receipt (concurrent edits after receipt). Receipts are point-in-time; drift is expected mid-build and is itself measured by D4.

### economics/ (ledger: `economics/RECEIPTS.md`)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| tokenomics.py | `b5fba554252ff0f854fbe10565529093785cc25a7df5f0eb9ef646781e06f7eb` | 07:52 (winter-wire + Merit-transferable) | — |
| test_tokenomics.py | `7e40546d408b3449f063df731c617387fb46bd5555cc2747c4134f68048f57ee` | 07:52 | edited after (89 tests now) |
| wallet.py | `b35e606103f59943c5a0180737674718ddcf8db898c13d0734ad2ba5fd72f6b6` | 07:10 | DRIFT — disk `872c77df…` |
| test_wallet.py | `14628cafe921659449a86daf610432c77fba5b46e59f5312540fc15c73f81803` | 07:10 | DRIFT — disk `873a7c0b…` (41 tests now) |
| fuse.py | `33cfaea537e28cc297dfb655cfdafccc7f15d74134c38952cc6c8579a904e75b` | 07:10 | — |
| test_fuse.py | `9e7f2d2002574c1c62f71c4d29c429bd68250854ff0d973dc450b137ebf3ad27` | 07:10 | — |
| economic_state.py | `f017c8518d47fd4c5a309ded059940d8b4ba941130fa31074c821e6d1b546a45` | 07:15 (D4 repair) | — |
| pricing.py | `4baa6fb1914dc4a39e7d2f3b996048a1be2e900208b7bda9c0537965cc528015` | 07:15 (D4 repair) | DRIFT — disk `b4b19180…` |
| test_economic_state.py | `1efee7d9504e459b71ef258afa4d8bc7cf08b5373d2cd9db7f8ce670cc1fe738` | 07:15 (D4 repair) | — |
| test_pricing.py | `60a3ebed3ab968fc5961f2baad8d5e96a560ac6208fc5454636de713ebb06833` | 07:15 (D4 repair) | — |
| NEW_ECONOMIC_MODEL.md | `83c91a72b44b0d25f5599d8293694fc707956056c9d1639eecef21978a6456f2` | 07:15 (D4 repair) | DRIFT — disk `7cf514d8…` |
| PARAMS.md | `b7d6dc3a55dbcf26de33cff33b4bd4aef0de61375e8e2e95c9d648bbf1cad2ce` | 07:06 | DRIFT — disk `1e28f421…` |
| DECISIONS.md | `11d1a6404d3bb4ac58b33a2065bf5c43c49f3e68b60b6039edecb1b6970ae30c` | 07:06 | DRIFT — disk `62f35c9c…` |
| PURITY_AUDIT.md | `fdd966610d473ec22d6a681b288358313fe9b3d69ceba7b4c047a6b9461f099a` | 07:15 (D4 repair) | — |
| PRICES_ADDENDUM.md | `8133bfa3a08fba5e1edea009f64598126390cac1f649db0e37b39ecd7373b2dc` | 07:15 (D4 repair) | — |

### dclm/ (ledger: `dclm/RECEIPTS.md`)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| compute.py | `daa0b73a7d1a549193522b52d074b523b2361a27434e67edc782d3654065fccb` | 06:58 | — |
| test_compute.py | `ea7c2a62520e259cbd75dd832717787847542442f31923f32058573ee0dbec17` | 06:59 | — |
| meter.py | `4c6b134edc3de3fe2a504a3342a13ba7bad5d65b71016dc24e89d9f386f210e4` | 07:40 (merit-regen evolution) | DRIFT — disk `5ccf630f…` (purify wiring) |
| data.py | `5af85e54fb1d5c66bc8e52eb6440901a3b2693352b636cbadb2fccba6ef64cd6` | 07:15 (file-handle fix) | DRIFT — disk `50b3bed0…` (purify wiring) |
| rights.py | `a059e531f542c9fa2ad268be610ca6f4421d8d57e5e59858eb85556a45789bd5` | 07:34 (onboarder) | — |
| writes.py | `7a82f55e20c583f197446d3a0f45a45ec9d631e17c0e964ead9d631e17c0e…` | 07:34 (onboarder) | — |
| tap.py | `ec73b2f0dd3844421f7f9dc053bbd30692291ebebcf2d7fc8a5fc05dc52e9493` | 07:45 | DRIFT — disk `a93af65f…` |
| winter.py | `42ee632e1f316995509f7b4cbee1405d841cb437a2dbaaa44018b00070fcaa98` | 07:19 | DRIFT — disk `f44169be…` |
| share.py | `78a219d230840b0acab64527d843ee48aa99d4cccc50dfba55294bc28a2f1721` | 07:23 | DRIFT — disk `df85202a…` |
| onboard.py | `c0665e0d1c454884abeccf49550d6dbcffb0c47f46ea52bded6c2571456caf10` | 07:34 | DRIFT — disk `64c3a5fd…` |
| token_engine.py | `ca3db2ea6e3e14b42e2af53d9bb37fd81c26353798bf62d177ab0cde7efd7736` | 07:20 | DRIFT — disk `40ef8185…` |
| tokenize.py | `da3a5f4be764d7a6383bb78081faaf7f213ba635836486bc229175e3057f5113` | 07:20 | DRIFT — disk `2e6a3503…` |
| test_tokenize.py | `2087c740387c50104138bbff5e6f5a61ec7c2d86b59dfec06c0d0749ca437e6d` | 07:25 | DRIFT — disk `7cddb4bc…` |
| test_merit_regen.py | `2f5f78eee8b746e3db4d825e6d5a5d450db645f7591690cd2383ad82bdb8fe1b` | 07:40 | DRIFT — disk `e8e97081…` (27 tests now) |
| ed25519.js | `bb0be18c36c3cd9c90237e117301c0272620b2e57945d2fb19b6e32cfbfa397c` | 06:56 | — |

### gate/ (ledger: `gate/RECEIPTS.md`, self-sealed)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| gate.py | `77ad1d1a9d95adf436c228905a75d494cab8eb48150ddda82c58f44cb8cbc3f6` | 07:00 (reframe) | — |
| test_gate.py | `54fc8a91308698370b48bad86546708997a2456826fbf10c3012706d72525656` | 07:00 (reframe) | — |
| CEREMONY.md | `c9c519779b1d25e587cc2d3e977d06e0fd8eca59ade81c31a7db5180a5c35748` | 07:00 (reframe) | — |
| RECEIPTS.md (self-seal) | `b1fb584f74928d9c8994a1ebc3f31323764f6d056026b5ec38492371280e33ff` | 07:00 | — |
| state chain | 2 mutations, hash-chained, tip `7b399fa4df90ae4a76c3fd026f1dd52bd7b4dfc2683a4af9f98b0a1c67c685dc` | 06:54 (seed) | — |

### relay/ (ledger: `relay/RECEIPTS.md`, self-sealed)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| relay-unity.mjs | `26b8612dc46c9662695fc7bfefc43c9d0381b8a24acde4601acda64343ffb4ee` | creation | — |
| relay-unity.test.mjs | `9fbc946271759116a48609afd41c79a7b259f6697066bbf07e615d263de16b5c` | creation | — |
| RECEIPTS.md (self-seal) | `a3577901191742a4d05268b05459dcf74e9e20f4494d7b44f07766872998246f` | 07:15 (D4 repair) | — |
| wrap-chunk.mjs | **UNRECEIPTED** | landed 07:54 | no receipt row exists |

### client/ (ledger: `client/RECEIPTS.md`)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| index.html | `03d5ea8ef0f6d5417bf6a8f0ea0fc30b63c860a8dce649739d0055efc9525f77` | ~03:00 EDT | DRIFT — disk `9a158a4b…` |
| client.js | `2ee9818ce5216142ba6a4aa3fd429e3a3b75ef768499f36a30e600d49c479b4c` | ~03:00 EDT | DRIFT — disk `55232557…` (edited 08:10) |
| validate-client.mjs | `37c31d4f60446283807e22442182b8919ef017067a62e3ed1d9559baf745737a` | ~03:00 EDT | DRIFT — disk `7c92d63e…` (141 checks now) |
| chunks.js | **UNRECEIPTED** | landed 08:02 | no receipt row exists |

### purity/ (ledger: `purity/RECEIPTS.md`, self-sealed)

| File | Receipted sha256 | Time (UTC) | Drift |
|---|---|---|---|
| index.py | `bef5da1cc76167d9f742acc854b94837e22784b6378dc87394cd55fce622372b` | 07:42 (clarity layer) | DRIFT — disk `baf4f46b…` |
| test_index.py | `a1a81b2c2e7c9f3fbbd6895b34c659175e6ef89e8cd5aba387467be5e965c627` | 07:42 | DRIFT — disk `10109cec…` |
| PURITY_INDEX.md | `709840c8443bf810b6759972f5d803d222f4950a16bd87daa235eef8e67e0c57` | 07:42 | — |
| RECEIPTS.md (self-seal) | `774d3cd6a3dd932bbbac85ee1df96037c2340f3573625d01ad8011b83de751db` | 07:42 | — |

### unity-world root (ledger: `unity-world/RECEIPTS.md`)

| File | Receipted sha256 |
|---|---|
| CANON.md | `68cd7c4e1d3a5d5bc58b13f9e1878a224c70c5150e86f0fcf8f7dc05aaebfe57` |
| LOOP.md | `82a3570ba1578d3bf08ba03311b871065a89cfd36a52a2d89760504e97f4e509` |
| loop.py | `2cec80f0350d2edc7eb70ed688a17604d3cbac9155fcdf4f02569ac24b32fb8f` |
| DIAMOND_ARCHITECTURE_FLOOR.md | `749547ca74a70d2f7f11de82b2f97d8995bc081f00a44da4f250fe9a70e398b0` |
| GOVERNANCE_ELEVATION.md | `305446c97fec736c326cd2e42373f87c8a120a8e5a48670ead128bc81ad9b868` |
| PLUS_ONE_INCENTIVE.md | `de8bd268bc58a9e912a0db2ccdd98fd7ee346cad702c733e5f51b12701100ea2` |

### Purity index live measurement (2026-10-06 08:06–08:08 UTC — re-run for this record)

| Dim | Score | Status | Grade | Cause |
|---|---|---|---|---|
| D1 Unity binding | 0.917 | FAIL | SI | 1/12 assertions fail: `purify_input` raises `PurificationRefused` where the scorer expects a signed refusal envelope for mainnet identity (purify-contract change) |
| D2 Label honesty | n/a | **UNKNOWN** | ungraded | Scorer crashes on `ingest_reading()` — same purify change (anonymous-input refusal propagates). UNKNOWN is never PASS |
| D3 Client purity | 0.000 | FAIL | I | **Likely scorer artifact:** the only matches are the words "localStorage / sessionStorage / IndexedDB" in a comment in `chunks.js` stating the prohibition — zero actual storage calls. Pattern-matcher doesn't exclude comments (same class as calibration-log items §3.1–3.3). Needs scorer fix, not client fix |
| D4 Receipt completeness | 0.534–0.552 | FAIL | SI | 22 hash mismatches + 19 unreceipted files (the drift table above) |
| D5 Isolation | 0.833 | FAIL | SI | `dclm/test_seed.py: SCHEMA='unity.seed.v1'` — non-testnet schema in code |
| **Aggregate** | | **FAIL** | ungraded | D1, D3, D4, D5 FAIL; D2 UNKNOWN |

Compare: 07:15 UTC snapshot was aggregate FAIL with only D4 failing (0.816). The 07:42 snapshot: D1/D2/D3/D5 PASS, D4 0.855 FAIL. The build moved fast between 07:42 and 08:08 and the index caught every bit of it — which is its job.

---

## 5. Honest gaps

What is NOT measured, what is still building, what is UNKNOWN. Each item names its evidence.

### 5a. Red tests / broken harnesses (exist, measured, unresolved at write time)

1. **Eight dclm suites red from the purify contract change** (07:56 UTC): meter 4 errors, data 3 errors, winter 1 error, tap 1 failure + 1 error, share 2 errors, rights_writes 1 failure, seed 1 error, onboard 1 error (partial run). Two workers' contracts disagree (raise vs. signed-refusal); the Trinity hasn't reconciled them.
2. **test_chunks.py flaky under concurrent edits** (1–2 failures across runs; file edited mid-run at 08:07 UTC; chunks.py edited 08:15 UTC by another live worker). **test_purify.py flaky** (4 errors → 54/54 OK on re-run).
3. **test_tokenize.py: 64 tests, 2 failures (provisional)** — run completed (513.6s) only after a >20-min stall; `token_engine.py` edited 08:25:56 UTC and `test_tokenize.py` 08:22 UTC by a live concurrent worker during the run. Failure details not captured (chain terminated during the following suite). Last clean receipt: 49/49 at 07:35 UTC.
4. **Unification proof harness broken**: `testnet/proof/unification-proof.mjs` crashes at step [1] (`TypeError`, `enq.entry` undefined) — 0/17 complete. README's "17/17 passing" does not reproduce.
5. **Gauntlet harness stale**: `results.json` all-sections-raised (07:54); `run.log` 08:01 shows eFuse-section assertion failure. Not a gate, not green.
6. **Purity index aggregate FAIL** (08:08 UTC, re-confirmed 08:30 with D4 fallen further to 0.385): D1/D3/D4/D5 FAIL, D2 UNKNOWN (see §4 table). Receipt drift is accelerating — workers keep editing faster than ledgers are appended.

### 5b. Adversarial findings awaiting fixes (measured, fixes unconfirmed)

6. **Relay persistence race** (team5 C5): silent outbox truncation 1,735 → 59 bundles. Fix (atomic rename + fail-loud) recommended, not confirmed built.
7. **token_engine duplicate-delivery double-apply** (team3): merit 100→200, eFuse 1→2 on re-delivery. Idempotency fix confirmed in `wallet.py` only; token_engine's own fix UNKNOWN.
8. **Gate negative-keys seam** (team2): 300/300 fail-open on injected `keys_available: -50` ledger. Recommendation recorded; fix UNKNOWN.
9. **Economics NaN/inf findings** (team4 F2/F3): no finiteness checks. Fix UNKNOWN.
10. **≤4.20ms bound breached** on the paid-intent path and mutations (team2). Redesign UNKNOWN.

### 5c. David's hand only (HELD — not builder gaps)

11. **Peg ratio E** — nothing emits without it (`HeldParameterError`, never a placeholder). 13 HELD tokenomics params + 4 canon = **17 parameters awaiting David's word** (team8).
12. **Genesis Unity amount** — `GENESIS_UNITY_AMOUNT = None`; the fuse cannot trigger without his signed authorization.
13. **Core Cause Lock address** — `{"value": "UNKNOWN"}`; no placeholder ever rendered as live.
14. **Honor class name** — `UNNAMED — HELD for David`.
15. **EIA + NASS free email registrations** — unblocks keyed re-probes (mesh blocking item).
16. **Sealed dim-7 vs free-key tension** — Trinity ruling pending (mesh blocking item).

### 5d. Never-wired / not-yet-built

17. **WebAuthn**: the gate's `confirm_bind` runs on a clearly-labeled TEST STUB; real device ceremony is SPEC/UNKNOWN (gate/CEREMONY.md).
18. **L2 kin authority**: `verify_kin()` returns False — INTEGRATION PENDING, family grants refused `NOT_KIN_VERIFIED` (dclm/SHARED_ACCESS.md).
19. **testnet IPNS**: keys minted, **no testnet pin published yet** (testnet/README.md).
20. **Emission path rewiring**: `emission_eligibility` gate exists and is tested (27/27), but `_mint_efuse` hasn't been rewired through it yet (dclm/RECEIPTS.md, Phase 2 pending on tokenization worker).
21. **Deployment loop**: `deploy/DEPLOYMENT_PLAN.md` exists; the public loop (domain → box, IPNS republish) is not closed. Testnet only.

### 5e. UNKNOWN by nature

22. Deployment topology (Trinity verdict): decides whether relay fan-out is a real bottleneck or a solved CDN problem.
23. Real user bandwidth environments (affects adaptation tuning, not architecture).
24. Whether behavioral prefetch ever becomes accurate enough to matter.
25. Fresh web-gather intelligence time per cell (minutes–hours; no swarm makes it instant).
26. Any mainnet measurement — none exist, by law.

---

## 6. Source index

Every number above traces to one of these. No invented figures anywhere in this record.

| Claim | Source file |
|---|---|
| economics 227/227 | `python3 test_*.py` runs, `~/workspace/unity-world/economics/`, 2026-10-06 ~08:00 UTC |
| dclm suite results | `python3 test_*.py` runs, `~/workspace/unity-world/dclm/`, 2026-10-06 ~08:00–08:25 UTC |
| gate 9/9, relay 42/42, client 141/141, testnet 14/14 | live runs 2026-10-06 ~08:00 UTC |
| unification proof crash | `node ~/workspace/testnet/proof/unification-proof.mjs`, 2026-10-06 ~08:00 UTC |
| purity index 08:08 UTC | `python3 ~/workspace/unity-world/purity/index.py`, 2026-10-06 08:06–08:08 UTC |
| purity index 07:15/07:42 snapshots | `~/workspace/unity-world/purity/PURITY_INDEX.md` §6, `purity/RECEIPTS.md` |
| Trinity verdict PASS-WITH-NOTES | `~/workspace/unity-world/PURITY_VERDICT_PROGRESSIVE_ARCH.md` (2026-10-06 ~03:55 EDT) |
| mesh topology, 485 bundles, ~423 tasks, ≥31 corrections | `~/workspace/mesh/MESH_MAP.md` |
| 8-bot / 25–65ms calculation | `~/workspace/mesh/SWARM_INSTANT_CALCULATION.md` |
| benchmark team results | `~/workspace/iris-benchmark/team{2,3,4,5,6,7,8}-*/` (BENCHMARK.md / REPORT.md / results.json) |
| receipt hashes | `*/RECEIPTS.md` ledgers + `~/workspace/unity-world/RECEIPTS.md` |
| chunk state (epoch 23, 19 chunks, 746,835 bytes) | `~/workspace/unity-world/dclm/chunk_receipts.log` |
| economic parameters (100M cap, 50/50, peg E, 81/19) | `~/workspace/unity-world/economics/NEW_ECONOMIC_MODEL.md`, `PARAMS.md` |
| purity audit verdicts | `~/workspace/unity-world/economics/PURITY_AUDIT.md` |
| gauntlet stale artifacts | `~/workspace/unity-world/economics/gauntlet/{results.json,run.log}` |

---

*Telemetrics complete = complete record of what exists, not a claim that everything is done. The red items above are the work queue. Nothing here is fabricated; where the record conflicts with an older claim (168/168 → 227/227; 63/63 → 141/141; 17/17 → harness crash), the newer measurement wins and the older claim is named.*
