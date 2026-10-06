# COIN ARCHITECTURE GAUNTLET — MAX ELEVATION POTENTIAL

**Worker 3 · 2026-10-06 ~04:00–05:00 EDT · TESTNET ONLY**
**Under test:** `~/workspace/unity-world/economics/` (`wallet.py` Ledger/ReceiptChain/Wallet,
`tokenomics.py` Ledger/`emission_calculator`, `fuse.py`) + `~/workspace/unity-world/dclm/token_engine.py` (Tokenizer)

Every number below is a **real measurement** on this machine unless labeled
**MODELED** (extrapolation method shown). All measurements on fresh ephemeral
test keypairs / synthetic test pubkeys and isolated in-memory ledgers —
shared/default state never touched, no real keys, no production paths.

Provenance register: **REPORTED** = measured here · **MODELED** = extrapolated
(method shown) · **DERIVED** = computed from measured figures.

Test box: Linux VM, CPython 3.12, single-threaded benchmark process (except §5).
The box was shared with other agents during the run, so absolute ops/sec
figures carry machine-load noise (two runs are reported where available);
**ratios, scaling shapes, and complexity classes are the stable findings.**

---

## 1. THROUGHPUT CEILING

Three op profiles, each a *complete valid* economic mutation (all gates
enforced, receipt → hash chain → idempotency registry):

- **Op A — `deduct_per_decision`**: single-side receipted mutation (cheapest
  valid op: per-decision metering).
- **Op B — `share()` funds**: both-side receipted mutation with tier lookup,
  tier-limit counters, before/after balances (the representative real tx).
- **Op C — full pipeline `receipt → merit → emission`**: tokenomics
  `Receipt.build` + `accrue_merit` + `emission_calculator` (1 member) +
  wallet `receive_emission` against a gated receipt — the literal
  receipt-to-emission path, end to end.

### Ramp table (REPORTED)

| ops | Op A ops/s (run1 quiet / run2 loaded) | Op A µs/op | Op B ops/s | Op B µs/op | Op C ops/s | Op C µs/op |
|-----|----------------------------------------|-----------|-----------|-----------|-----------|-----------|
| 10 | 16,892 / 1,160 | 59 / 862 | 7,063 | 142 | 8,639 | 116 |
| 100 | 6,023 / 1,912 | 166 / 523 | 4,253 | 235 | 2,464 | 406 |
| 1,000 | 7,934 / 1,997 | 126 / 501 | 1,415¹ | 707¹ | 2,297 | 435 |
| 10,000 | 5,730 / 3,458 | 174 / 289 | 2,294 | 436 | 2,352 | 425 |
| 50,000 | — | — | 2,437 | 410 | — | — |
| 100,000 | 3,551 | 282 | — | — | — | — |

¹ outlier under box load; neighboring points put Op B at ~2.3–4.3K ops/s.

### 1.1 The knee — there isn't an algorithmic one

Per-op cost is **flat vs chain length**: a dedicated GC probe ran 100K
deducts in 10K-op batches with GC on and off — batch means bounced between
~250–590 µs/op with **no monotonic growth** as the chain grew 10K → 100K
(GC-off was *slower* overall: 47.2s vs 29.9s — allocator pressure without
collection). `ReceiptChain.append` is O(1) (`self._entries[-1]` + one hash);
nothing in the hot path scans history.

So: **no knee in the 10 → 100K range.** Throughput sits at roughly
**2K–8K receipted ops/sec single-threaded** (box-load dependent), and the
ceiling beyond 100K is *resource* exhaustion (memory — §2/§7), not an
algorithmic wall. The honest knee is where the operator stops being willing
to pay linear memory + linear verification (§3), not where ops/sec collapses.

### 1.2 Per-op cost breakdown (REPORTED, quiet box, Op A = 67 µs)

| step | cost | share of op | reducible? |
|------|------|-------------|------------|
| `deepcopy` ×3 (stored receipt, chain entry, returned copy) | ~3 × 16.1 µs ≈ 48 µs | ~70%¹ | yes — §7 |
| canonical JSON serialize ×2 (manifest + chain hash input) | ~2 × 7.6 µs ≈ 15 µs | ~20% | partly — §7 |
| sha256 ×2 (manifest_hash + chain_hash) | ~2 × 11.9 µs ≈ 24 µs | ~25%² | no (structural) |
| `_utc_now()` ×2 | ~2 × 2.05 µs ≈ 4 µs | ~6% | trivially |
| validation (dict lookups, type checks, tier/counter reads) | ~3–5 µs | ~5% | no |
| state mutation (dict writes) | <1 µs | ~1% | no |

¹ components timed separately on slightly different receipt sizes — shares
are approximate and not strictly additive (they sum past 100%). The
**ranking** is the robust finding: deepcopy ≫ hashing > serialization >
clock > validation. End-to-end measured Op A = 67 µs.
² the two hashes cover *different* bytes (idempotency key vs chain link) —
not redundant work, both structurally required.

**Bottleneck, hashed path:** the receipt tax itself — deepcopy + canonical
JSON + hashing ≈ **90% of every op**. Validation and state mutation are
negligible (~0.1 µs dict lookups). The architecture's cost center is exactly
what the design says it is: *every mutation pays the receipt/hash tax.*

**Bottleneck, full pipeline:** Op C at ~425 µs/op is ~6× Op A — the extra
~360 µs is the tokenomics leg (`Receipt.build` + `accrue_merit` +
`emission_calculator` + second `_apply`). Still hash-bound, still flat.

**Bottleneck, crypto path:** any op touching Ed25519 leaves the hashed
universe entirely — see §7. One `make_tier_grant` + `apply_tier_grant` ≈
**1.0 s clean** (2 node subprocess spawns @ ~410 ms sign / ~590 ms verify on
this box; crypto itself is sub-millisecond — the cost is process spawn).
That is **~15,000×** the cost of a hashed op.

### 1.3 Emission at pool scale — one `emission_calculator` call, N members (REPORTED)

| members | ms/call | µs/member |
|---------|---------|-----------|
| 100 | 2.6 | 26 |
| 1,000 | 15.5 | 15.5 |
| 10,000 | 181 | 18.1 |
| 50,000 | 639 | 12.8 |

Roughly linear (~13–18 µs/member); the constant is
`EpochEmission.__post_init__` canonical-hashing the entire per-member dict.
A 1M-member epoch close would take **~13–18 s single-threaded** (MODELED,
linear) — acceptable as a batch job, not as an interactive op.

---

## 2. SCALE CEILING — UNITY IDs

10,000 distinct Unity IDs opened on one ledger (REPORTED):

| probe | 100 | 1,000 | 10,000 | shape |
|-------|-----|-------|--------|-------|
| `new_wallet` µs/ID (per 1K tranche) | — | 61–238 (noise, no trend across 10 tranches) | flat | **O(1)** |
| `ledger.wallet(id)` lookup | 0.6 µs | 0.6 µs | 0.6 µs | **O(1)** dict |
| `_pubkey_of(id)` | ~0.8 µs | 0.84 µs | 1.04 µs | **O(1)** dict |
| `tier_of(a,b)` (G grants on file) | 15–54 µs | 152–282 µs | **3.8–8.6 ms** | **O(n)** scan |
| `is_kin(a,b)` (K bonds on file) | 8–259 µs | 331–1,160 µs | **9.1–11.0 ms** | **O(n)** scan |

Identity storage and binding verification stay O(1) — the ID ceiling is
**not** the wallet map. The ceiling is the *relationship* scans:
`ledger.tier_of` iterates the entire `_grants` list and `ledger.is_kin`
iterates the entire `_kin` list **on every share**. At 10K grants a single
`tier_of` costs 3.8–8.6 ms (two runs) — **~60–130× the hashed op it gates** — and it runs
*inside* every `share()`. This is the first thing that breaks under social
scale: a wallet with 10K tier grants pays ~4–9 ms of scan per share.

Memory (REPORTED, tracemalloc): **~1,950 bytes per wallet** (entry + receipt
copies + pubkey b64). 10K IDs ≈ 20 MB; **1M IDs ≈ 2 GB** (MODELED, linear).
No degradation in lookup — pure capacity question.

**ID knee:** binding/lookup — none found (O(1) to 10K). Relationship scans —
knee at **~1K grants/bonds** (sub-millisecond below, multi-millisecond above).

---

## 3. SCALE CEILING — RECEIPT CHAIN

| chain length | append µs/op | full `verify()` | µs/entry verified |
|--------------|-------------|-----------------|-------------------|
| 1,000 | ~200 (noise) | — | — |
| 10,000 | 277 | **0.49 s** | 45 |
| 100,000 | 175 | **6.21 s** | 61.5 |

- **Append is O(1)** — flat across 1K → 100K (175–277 µs, noise-dominated;
  the number is higher than §1's op cost because the probe receipt carried
  padding; the shape is the finding).
- **Verification is O(n)** — every `verify()` re-hashes every entry from
  GENESIS. No checkpoints, no incremental seals.

MODELED (linear, method: measured µs/entry × N): 1M entries → **~60 s**
per verify; 10M entries → **~10 min**. `Ledger._load` calls `verify()` on
*every* persisted restart — a 1M-receipt ledger would take ~1 minute just to
open.

**Chain knee:** append — none (O(1) forever). Verification — the practical
wall: beyond **~100K receipts, a full verify exceeds 6 s**; beyond ~1M it
exceeds a minute. The chain grows fine; *proving* it doesn't gets expensive.

---

## 4. COMPLEXITY CEILING

Built the most complex **valid** flow the architecture accepts, one coherent
story across 3 Unity IDs (A, B, C), all gates enforced (REPORTED):

| # | step | gate class exercised |
|---|------|----------------------|
| 1–3 | open wallets A, B, C | Unity binding, zero-by-construction |
| 4 | `kin_bind(A,B)` — 2 Ed25519 verifies | mutual-signature kin bond |
| 5 | `make_tier_grant` + `apply_tier_grant` A→B **family** (sign + verify) | cryptographic tier, kin-required tier |
| 6 | `connect(A,C)` | read-only connector, both IDs resolve |
| 7 | `receive_emission(A, 50000)` vs gated receipt | emission receipt validation (10 field checks) |
| 8 | `share(A→B, 1000 eFuse)` under family tier | tier check + limits + both-side receipt |
| 9 | tier grant A→C `good_friend` + `share(A→C, info)` | same rails, info content type |
| 10 | `donate(A, 500 → lock)` | one-way donation, Honor accrual, donor exclusion set |
| 11 | `check_donor_exclusion` (own donation as source) | **refused correctly** — the gate fires |
| 12–13 | tokenomics `accrue_merit` (A, B) from VERIFIED receipts | receipt→merit, Unity binding match |
| 14 | `emission_calculator` (2 members) + `receive_emission(B)` | merit-weighted, peg-calibrated, authority-bounded |
| 15 | engine `tokenize("work")` → merit for A | DCLM commit path, 2 signed commits |
| 16 | `transfer_merit(A→B)` via engine + wallet receipt | sole legal Merit path, origin never moves |
| 17 | `donate(B, 100)` + `check_donor_exclusion` (other source) | exclusion passes for non-own source |

**Result: 16 distinct gate classes passed in one flow, 10.8 s wall**
(node-subprocess crypto ≈ 10 s of it; the hashed machinery ≈ 0.8 s).
Chain verifies clean afterwards.

Then added one more element until it breaks — 7 attempts (REPORTED):

| +1 element | outcome |
|------------|---------|
| share **Unity** tokens A→B | refused: `UnityBindingError` (binding law) |
| family tier C→B **without** kin bond | refused: `TierViolation` (kin is binding) |
| **forged** tier grant signature | refused: `TierViolation` (Ed25519 verify failed) |
| duplicate manifest retry | **no-op** — original receipt returned, no double-spend |
| donate more than balance | refused: `InsufficientFunds` |
| Honor → emission conversion | **no function exists** — absent by construction |
| **atomic multi-step batch** of the whole flow | **no primitive exists** — each op is its own receipt |

**Complexity max that works:** the 16-gate flow above. **What "breaks":**
nothing *invalid* gets through — every +1 invalid element refuses exactly as
designed. The real ceiling is structural, not adversarial: **there is no
atomic batch primitive**. A 16-step flow that fails at step 14 leaves 13
receipted, chained, idempotent mutations with no rollback. The architecture
is honest about each step and has no story for the *flow*.

---

## 5. CONCURRENCY

Threaded concurrent mutations against one shared in-memory ledger (REPORTED).
**There is no locking anywhere** — no `threading.Lock`, no atomic
compare-and-swap, no writer election in `Ledger`, `ReceiptChain`, or
`_apply`.

| threads | mode | chain verifies? | dup seq? | balances correct? | exceptions? |
|---------|------|----------------|----------|-------------------|-------------|
| 2 | distinct wallets × 50 deducts | **NO** | yes | yes | 0 |
| 4 | distinct wallets × 50 deducts | **NO** | yes | yes | 0 |
| 8 | distinct wallets × 50 deducts | **NO** | yes | yes | 0 |
| 16 | distinct wallets × 50 deducts | **NO** | yes | yes | 0 |
| 32 | distinct wallets × 50 deducts | **NO** | yes | yes | 0 |
| 4 | **same** wallet × 200 deducts | **NO** | yes | yes | 0 |
| 16 | **same** wallet × 200 deducts | **NO** | yes | yes | 0 |

**It breaks at 2 threads.** The race: `append()` reads `prev =
self._entries[-1]["chain_hash"]` and `seq = len(self._entries)`, then two
threads interleave — both entries get the same `prev_chain_hash` and the
same `seq`. The chain forks silently: **zero exceptions raised**, the
idempotency registry counts come out right, balances *happened* to stay
correct (CPython GIL luck on `r["eFuse"] -= price` — **not guaranteed**,
do not rely on it). `verify()` catches the fork after the fact, but nothing
prevents it.

**Verdict: concurrent mutation of one ledger is UNSAFE at any concurrency ≥
2.** Single-writer only, until a lock/WAL/append-serialization lands (§9).

---

## 6. THE ELEVATION CURVE

### What gets BETTER with scale
Almost nothing per-unit — and that is the good news in disguise: **per-op
cost does not degrade.** Append O(1), ID lookup O(1), binding verify O(1)
— the hot path is scale-invariant to at least 100K ops / 10K IDs. The
architecture's core loop is already at its asymptote; there is no
"worse with scale" on the per-transaction axis. Fixed costs (imports,
process start) amortize trivially.

### What gets WORSE with scale
| axis | shape | measured |
|------|-------|----------|
| chain `verify()` | **O(n)** | 0.49 s @10K → 6.21 s @100K → ~60 s @1M (MODELED) |
| `tier_of` / `is_kin` per share | **O(n)** | 3.8–8.6 ms / 9–11 ms @10K entries — 60–130× the op they gate |
| `merit_balance` per call | **O(n)** slices | 19.7 ms @10K slices (~2 µs/slice) |
| memory footprint | **linear** | ~1.6 KB/receipt-op, ~1.9 KB/wallet → 1M ops ≈ 1.6 GB (MODELED) |
| persisted-mode write cost | **O(state)** | 2,751 ms/op @10K chain vs 272 µs in-memory (**~10,000×**) |
| emission epoch close | **O(n)** members | ~13–18 µs/member → ~15 s @1M members (MODELED) |

### The curve's shape
**Flat per-op + linear verification/lookup/memory degradation.** No
superlinear blowup anywhere on the honest paths (the O(n) scans are linear,
not quadratic). The practical operating ceiling is where the *linear*
costs stop being ignorable:

> **Tell David:** one ledger shard holds **≤ ~100K receipts** AND
> **≤ ~10K Unity IDs** AND **≤ ~1K tier grants / kin bonds**, single-writer,
> in-memory (or persisted only if you accept ~0.4 ops/s at 10K receipts).
> **Beyond here, redesign the ledger** — shard it, checkpoint verification,
> index the scans, serialize writes, move crypto in-process (§8).

---

## 7. 100% EFFICIENCY — THE FRONTIER AUDIT

*David's bar: run AT the frontier, not below it. CPU time per op is the
watt-equivalent proxy (energy ∝ CPU-seconds); joules below are MODELED at a
nominal 15 W per busy core — method shown, assumption labeled.*

### 7.1 Efficiency per operation (REPORTED cpu, MODELED joules)

| operation | CPU/op (REPORTED) | energy/op (MODELED) | efficiency |
|-----------|-------------------|---------------------|------------|
| `deduct_per_decision` (hashed) | 67 µs | ~1.0 mJ | **~1,000 ops/J** |
| `share()` funds (hashed, tier-checked) | ~150 µs | ~2.3 mJ | **~440 ops/J** |
| full pipeline receipt→merit→emission | ~425 µs | ~6.4 mJ | **~157 ops/J** |
| `emission_calculator`, per member | ~13–18 µs | ~0.2 mJ | **~5,000 members/J** |
| `merit_balance` @10K slices | 19.7 ms | ~0.3 J | 3.4 calls/J |
| `tier_of` @10K grants | 3.8–8.6 ms | ~0.06–0.13 J | 8–18 calls/J |
| tier grant, end to end (sign+verify) | ~1.0 s clean¹ | ~15 J | **0.067 ops/J** |
| engine `tokenize("work")` (2 signed commits) | ~0.9 s clean¹ | ~13.5 J | 0.074 ops/J |
| engine `merit_transfer` (1 signed commit) | ~0.5–1 s clean¹ | ~11 J | ~0.09 ops/J |
| persisted `deduct` @10K chain | 2,751 ms | ~41 J | **0.024 ops/J** |

¹ clean = without the background-load contention seen during measurement
(B1g: sign 410 ms, verify 588 ms — the cost is ~99.9% node process spawn,
~0.1% actual Ed25519).

Two efficiency universes, **~15,000× apart**: the hashed universe runs at
~1,000 ops/J; the signed universe runs at ~0.07 ops/J. The frontier question
is how much of each universe's cost is load-bearing.

### 7.2 Wasted cycles — every one found, with fixability and gain

| # | waste | measured cost | load-bearing? | fixable? | est. gain |
|---|-------|---------------|---------------|----------|-----------|
| 1 | **deepcopy ×3 per mutation** (stored receipt, chain entry, returned copy — `Ledger._apply` + `ReceiptChain.append`) | ~48 of 67 µs (**~70%** of a hashed op) | partially — aliasing protection is real, but 3 full copies is not the only way | **yes** — freeze receipts (they're already treated as immutable) and share references; or return the stored object | **~30–40%** per hashed op |
| 2 | **canonical JSON serialized twice per op** (once for manifest_hash, once for chain_hash) | ~15 of 67 µs (~20%) | no — same bytes hashed twice is fine, serializing twice is not | **yes** — serialize once, reuse bytes for both hashes | **~8–10%** per hashed op |
| 3 | **node subprocess per Ed25519 sign/verify** (~450–590 ms spawn tax; the crypto is <1 ms) | ~1 s per tier grant; ~0.9 s per tokenize | no — the *signature* is load-bearing, the *process spawn* is pure waste | **yes** — in-process Ed25519 (vendored pure-Python or PyNaCl): **~1,000–5,000×** on the crypto path; cheaper: persistent signer daemon (no cold start): **~30–50×** | **up to 5,000×** |
| 4 | **`tier_of` O(n) grant scan inside every `share()`** | 8.6 ms @10K grants (**130×** the op it gates) | no — "latest wins" needs an index, not a scan | **yes** — `(granter, grantee) → tier` dict index maintained on append | **~1,000×** at 10K grants → O(1) |
| 5 | **`is_kin` O(n) scan** | 11 ms @10K bonds | no | **yes** — pair-set index | **~1,000×** → O(1) |
| 6 | **`merit_balance` O(n) slice scan** (called 2× per transfer + 1× inside) | 19.7 ms @10K slices (~2 µs/slice) | no — a cached per-owner total is exact | **yes** — per-owner balance cache updated on slice mutation | **O(1)** |
| 7 | **`verify()` re-hashes from GENESIS every call** (incl. on every persisted `_load`) | 6.21 s @100K; ~60 s @1M (MODELED) | partially — full re-verification is the strongest claim; checkpoints weaken it slightly | **yes** — epoch seal checkpoints (hash-of-hashes every N entries; verify from last seal + spot-check) | **verify → O(seal interval)** |
| 8 | **`_save()` rewrites the ENTIRE state on every mutation** when `state_dir` set (ledger-state.json + full receipts.jsonl) | **2,751 ms/op @10K chain** (6.5 MB rewritten per mutation) — **10,000×** vs in-memory | no — durability needs a WAL, not a full rewrite | **yes** — append-only WAL + periodic snapshots | **~10,000×** in persisted mode |
| 9 | **`tokenize("work")` = 2 separately-signed commits** (merit + eFuse) | 2 node spawns ≈ 0.9 s | no — one envelope can carry both outputs | **yes** — single commit envelope for the bundle | **~2×** on tokenize |
| 10 | `_utc_now()` twice per op | ~4 µs (~6%) | no | **yes** — one clock read per op | **~5%** |
| 11 | `uuid4()` per op when no caller manifest | ~3 µs | no — callers that retry supply manifests anyway | already avoided on the retry path | — |

**Frontier verdict:** the hashed path runs at ~60–70% of its own frontier —
recoverable to ~35–45 µs/op (about **1.5–2×** headroom) via fixes #1, #2,
#10, all implementation choices. The signed path runs at **~0.02–0.1%** of
its frontier — fix #3 alone moves tier grants from ~1 s to ~1 ms
(**~1,000×**), which is the single largest efficiency win in the system.
The persisted path runs at **~0.01%** of its frontier — fix #8 is the
single largest *correctness-adjacent* win (it is also what makes persisted
mode deployable at all).

### 7.3 What is NOT waste (leave it alone)
- The **two sha256 hashes per mutation** (~24 µs): different bytes,
  different purposes (idempotency key vs chain link). Irreducible without
  weakening the design.
- The **10-field emission receipt validation**: ~microseconds, and it is
  the gate. Cheap insurance, keep.
- **Fail-closed refusals** (HeldParameterError, UnknownFigureError…):
  refusing is the product. Never "optimize" by skipping checks.
- Canonical JSON with sorted keys: determinism is load-bearing for
  hash equality. Keep; just serialize once (#2).

---

## 8. ARCHITECTURAL HEADROOM — FUNDAMENTAL vs IMPLEMENTATION CEILINGS

| ceiling | kind | raisable? | how |
|---------|------|-----------|-----|
| 2× sha256 + canonical JSON per mutation (~35 µs floor) | **fundamental** (hash-chain physics) | only by weakening the chain | it isn't — this is the price of tamper-evidence |
| Ed25519 verify cost (~0.1–0.5 ms in-process) | **fundamental** (signature physics) | no | budget for it; batch verifications where possible |
| chain `verify()` O(n) | **fundamental-ish** | partially — checkpoints trade verification strength for speed | epoch seals; fraud-proof / spot-check model |
| single-threaded hashed throughput (~8K ops/s) | **implementation** | **yes** | sharded ledgers (per-ID partitions) process in parallel; per-shard chains stay O(1) |
| no concurrency control (corrupts at 2 threads) | **implementation** | **yes** | writer lock / single-writer queue / WAL with atomic append |
| node-subprocess crypto (~0.5 s/op) | **implementation** | **yes** — biggest win | in-process Ed25519 (1,000–5,000×) |
| `tier_of` / `is_kin` / `merit_balance` O(n) scans | **implementation** | **yes** | indexes + cached balances (1,000× at scale) |
| in-memory dict storage (2 GB @1M IDs) | **implementation** | **yes** | indexed store (SQLite/RocksDB); hot-set caching |
| full-rewrite persistence (2.7 s/op @10K) | **implementation** | **yes** | WAL + snapshots (10,000×) |
| no atomic multi-step batch | **structural** (design choice, §4) | yes, but it's a *design* decision | saga/choreography pattern or explicit batch receipt kind — needs David's word on the semantics |
| Held parameters refuse (peg E, decay rate, tier limits…) | **by design** | no — and shouldn't be | the refusal IS the purity boundary |

**Reading:** every ceiling that matters before 1M-scale is an
implementation choice. The fundamental ceilings (hash physics, signature
physics) sit 2–3 orders of magnitude above where the implementation
ceilings bite. **The architecture has headroom; the implementation needs
the §7 fixes to reach it.**

---

## 9. REAL-WORLD READINESS CHECKLIST

*Testnet proves the logic. This is the assessment TO the real-world
deployment line — promotion across it needs David's explicit word per the
build checklist. Nothing here blocks the gauntlet loop; it documents what
stands between testnet and production.*

### READY (deployable as-is, by construction)
- [x] **Fail-closed honesty**: UNKNOWN never pays; Held parameters refuse
  instead of inventing digits (peg E, decay rate, tier limits, honor
  classes). The refusal paths are the most production-ready part of the
  system.
- [x] **Idempotency**: caller-supplied manifests are verbatim idempotency
  keys; retries are no-ops; duplicate receipts refuse. Safe under
  at-least-once delivery — the right primitive for real networks.
- [x] **Testnet isolation is structural**: `unity:testnet:` prefix,
  `.testnet` relay schema, `KEY_ID = "unity-world-test"`. Mainnet parsers
  reject testnet artifacts and vice versa.
- [x] **Deterministic hashing**: canonical JSON (sorted keys, compact
  separators) — hash equality holds across machines. Receipts are
  portable.
- [x] **Absence-of-machinery laws**: no pool-to-pool flow, no mesh mint,
  no merit interest, no fiat→eFuse path, no honor→emission path — verified
  by test asserting the functions don't exist. Can't be misconfigured into
  existence.
- [x] **Tamper-evidence**: any mutation of a chained receipt breaks
  `verify()` audibly (proven in §5 — the corruption was *detected*, just
  not *prevented*).

### NEEDS HARDENING (documented, ordered by blast radius)
1. **[ ] Concurrency control — CRITICAL.** No locking; 2 threads corrupt
   the chain silently (§5). Real-world = concurrent writers by definition.
   → writer lock or single-writer queue + WAL before any multi-client
   deployment.
2. **[ ] Persistent storage — CRITICAL.** In-memory is the only viable
   mode; `state_dir` mode does a full 6.5 MB rewrite per mutation
   (2.7 s/op @10K chain). A restart loses everything in-memory; a crash
   mid-`_save()` can leave torn files (no atomic rename, no WAL).
   → WAL + atomic snapshots + replay-on-load.
3. **[ ] Key management.** Single test keypair, `KEY_ID` hardcoded, keys
   staged as tempfiles (0600, unlinked after use — a crash leaks the
   file). The peg setter is an honest testnet stand-in that *cannot verify
   David's signature*. → HSM/KMS, key rotation, multi-key registry;
   production peg setter MUST require his signed authorization (flagged in
   code already).
4. **[ ] Crypto path.** Every sign/verify shells a `node` process
   (~0.5 s/op on the test box; machine-dependent). Real-world latency
   would be dominated by process spawn, not crypto. → in-process Ed25519
   (§7 #3).
5. **[ ] Verification scaling.** `verify()` O(n) from GENESIS on every
   persisted load; 6 s @100K, ~60 s @1M (MODELED). → epoch seal
   checkpoints (§7 #7).
6. **[ ] Scan indexes.** `tier_of` / `is_kin` / `merit_balance` O(n)
   (§7 #4–6). At social scale these become the per-tx bottleneck and a
   cheap DoS surface (force a victim's wallet to hold 10K grants, every
   share costs them 9 ms).
7. **[ ] Clock discipline.** Receipt timestamps come from the wall clock
   (`_utc_now()`); chain *order* is by `seq` (good), but cross-machine
   deployments need NTP discipline + monotonic seq authority, or ts-based
   disputes get murky.
8. **[ ] No atomic batches.** 16-step flows have no rollback (§4). Real
  -world commerce needs either saga semantics or an explicit batch receipt
   kind — a design decision for David, not just engineering.
9. **[ ] Replication / failover.** One process, one Ledger, no replicas.
   → read replicas + leader election (or the sharded design in §8) before
   production.
10. **[ ] Adversarial input at the edges.** Core validation is fail-closed
    (good), but: no rate limiting, no request-size caps on receipts, and
    `_canonical_bytes` will happily serialize a 100 MB payload before
    hashing it. → ingress caps + payload limits.
11. **[ ] Observability.** No metrics, no structured logs, no slow-op
    tracing. You cannot run what you cannot see. → counters per op kind,
    chain-length gauge, verify-duration histogram.

### What would break or degrade moving to real-world conditions
| condition | effect | status |
|-----------|--------|--------|
| real network latency between components | wallet↔engine are in-process imports today; as RPCs, every `transfer_merit` pays 2+ round trips on top of the crypto tax | needs hardening (#4) |
| real adversarial environment | silent chain corruption under concurrency becomes *exploitable* (fork the log, double-claim before verify runs) | **critical** (#1) |
| real key management | test keys + tempfile staging don't survive contact with reality | needs hardening (#3) |
| persistent storage | 10,000× write amplification; torn writes on crash | **critical** (#2) |
| 10× the Unity IDs | lookups fine (O(1)); tier/kin scans become the tx bottleneck | needs hardening (#6) |
| process restart | in-memory: total loss. persisted: ~60 s re-verify @1M receipts | needs hardening (#2, #5) |

---

## 10. HEADLINE NUMBERS & THE SINGLE BINDING CONSTRAINT

### Headlines (REPORTED)
- **Throughput ceiling:** ~2K–8K receipted ops/sec single-threaded, flat
  from 10 → 100K ops. No algorithmic knee — the per-op cost is O(1) vs
  chain length. Cheapest valid op: `deduct_per_decision` @ ~67 µs
  (~1,000 ops/J MODELED).
- **ID ceiling:** binding/lookup O(1) to 10K IDs (0.6 µs/lookup, ~2 KB/ID).
  Relationship scans O(n): `tier_of` 3.8–8.6 ms / `is_kin` 9–11 ms at 10K
  entries — the social-scale wall, ~60–130× the op they gate.
- **Chain ceiling:** append O(1) forever; `verify()` O(n) — 6.2 s @100K,
  ~60 s @1M (MODELED). Verification, not appending, is the wall.
- **Complexity max:** 16 distinct gate classes in one valid flow; every
  invalid +1 element refuses as designed. No atomic batch primitive —
  partial failure leaves partial state.
- **Concurrency:** UNSAFE at ≥2 threads — silent chain fork, zero
  exceptions. Single-writer only.
- **Efficiency frontier:** hashed path at ~60–70% of frontier (1.5–2×
  recoverable); signed path at ~0.1% of frontier (in-process Ed25519 =
  ~1,000× win); persisted path at ~0.01% of frontier (WAL = ~10,000× win).
- **Operating ceiling (the line for David):** one ledger shard ≤ ~100K
  receipts, ≤ ~10K IDs, ≤ ~1K grants/bonds, single-writer, in-memory.
  Beyond → shard + checkpoints + indexes + WAL + locking + in-process
  crypto.

### The single binding constraint
**The ledger is a single-threaded, ever-growing, fully-rehashed,
unlockable log.** Every scaling axis terminates at the same place: an O(n)
verification or scan, unbounded memory growth, or silent corruption under
concurrency. The hash chain itself — O(1) append, ~35 µs of irreducible
hash physics per op — is *not* the constraint; it is the cheapest honest
part of the system. What binds elevation is everything *around* the chain:
no locks, no indexes, no checkpoints, no WAL, and a crypto path that pays
a half-second process-spawn tax per signature. All implementation choices.
All raisable. None fundamental — except the day the chain's own
verification cost exceeds the operator's patience, which checkpoints push
years out.

---

*Harness: `/tmp/gauntlet_bench.py` + `/tmp/gauntlet_eff_lean.py` (ephemeral)
· raw: `/tmp/gauntlet_results.json`, `/tmp/gauntlet_eff_lean.json` (ephemeral)
· Modules under test: `~/workspace/unity-world/economics/wallet.py`,
`tokenomics.py`, `fuse.py`; `~/workspace/unity-world/dclm/token_engine.py`,
`writes.py` · All ledgers isolated in-memory; all keys ephemeral test keys.*
