# COIN ARCHITECTURE GAUNTLET — RESULTS

**Worker 2, full gauntlet + 100% SECURE expansion**
**Date:** 2026-10-06 (run window ~07:52–08:35 UTC)
**Scope:** `economics/tokenomics.py`, `economics/wallet.py`, `economics/fuse.py`,
`dclm/token_engine.py` (+ `wallet.transfer_merit` as the canonical Merit path)

**Test discipline:** fresh ephemeral test keypairs (`generate_test_keypair`);
isolated in-memory ledgers only. `~/workspace/unity-world/economics/state/`
and all shared state files untouched. Fuse tests used test keys, in-memory,
never persisted. No production keys anywhere.

**Labels:** REPORTED = measured in this run. MODELED = simulated inputs —
the peg ratio E is HELD_FOR_DAVID; every E used below is labeled MODELED,
never presented as real.

**Machine caveat (REPORTED):** this run shared a build host at load average
~15 with other workers' benchmarks. Pure-Python paths are unaffected;
Ed25519 node-subprocess calls (keygen, signing, verification) measured
**much slower than unloaded** (e.g. transfer ~2.2 s/op loaded vs ~50 ms
unloaded). Throughput ceilings below are honest loaded-machine numbers;
the bottleneck *identity* (subprocess crypto, not coin logic) is
load-independent.

---

## 1. eFuse gauntlet

| Test | Volume | Result | Breaking point |
|---|---|---|---|
| `receive_emission` throughput | 200 / 1,000 / 3,000 | REPORTED 1,330 / 1,383 / 1,089 ops/sec | **No knee to 3,000** — per-op cost flat (~0.75 ms); pure Python, no subprocess signing |
| Receipt-chain integrity after volume | 4,203 emissions | PASS — `ReceiptChain.verify()` True, balances exact | — |
| Peg calibration (1/E) at volume | 4 E-values × 4 conversions (E = 0.5, 3.7, 10.0, 1000.0 — all MODELED) | PASS — 16/16 conversions exact (`amount == merit_value / E`) | Calibration holds at volume |
| Peg set without David authority | 1 | HELD — `TokenizeRefused` (testnet stand-in requires `{"authority": "david"}`) | — |
| Emission with peg E unset (HELD) | 1 | HELD — `TokenizeRefused` (refuses to invent E) | — |
| Donation-to-lock throughput | 201 | REPORTED 405 ops/sec; 201 receipts, 201 Honor records, `merit_accrued == 0` on all, donor-exclusion hashes recorded | No knee |
| Reserve-regulation movement | inventory | **N/A — no executable function exists.** `reserve_holdback_fraction` is HELD; the reserve appears only as a reporting section (`economic_state` peg_reserve). No bypass possible — nothing to push. | — |
| Fuse ARMED → TRIGGERED → SPENT | 1 (test keys, in-memory) | PASS — genesis Unity credited once, receipt chained | — |
| Fuse second trigger | 1 | HELD — `FuseNotArmed` ("the launch happened exactly once") | — |
| Fuse nonce replay | 1 | HELD — `FuseReplay` ("authorization nonce already used") | — |
| Fuse unauthorized trigger (wrong key) | 1 | HELD — `FuseRefused` (founder signature FAILED) | — |
| Fuse trigger missing nonce | 1 | HELD — `FuseRefused` | — |

## 2. Merit gauntlet (canonical path: `token_engine` + `wallet.transfer_merit`)

| Test | Volume | Result | Breaking point |
|---|---|---|---|
| `tokenomics.accrue_merit` throughput | 500 / 2,000 | REPORTED ~7,000 ops/sec | **No knee to 2,500** — dict-lookup idempotency |
| Engine `tokenize` (accrue + mint) | 10 | REPORTED ~0.2/sec (600 ms/op) — 2 signed commits; **node-sign subprocess dominates** | Signing is the accrual ceiling, not Python |
| `wallet.transfer_merit` throughput | 12 | REPORTED ~0.5/sec (~2.2 s/op loaded) — 1 signed MERIT_TRANSFER commit each | Signing is the transfer ceiling |
| `engine.merit_transfer` raw | 6 | REPORTED ~0.5/sec (~1.9 s/op loaded) | Same ceiling |
| Transfer exactness | 12 | PASS — every transfer receipted + chained, balances exact | — |
| Transfer refusal battery | 7 | ALL HELD — over-balance, unverified ID, self-transfer, zero/negative amount, empty reason, missing engine → all `TokenizeRefused`/`WalletError` | — |
| Merit double-spend (replayed wallet manifest) | 1 | HELD — engine called once, value moved exactly once | Idempotent |
| Decay across IDs | 300 IDs × 12 epochs | REPORTED 2,340 decays/sec, all labeled MODELED | No knee |
| Decay with HELD rate | 1 | HELD — `HeldParameterError` (refuses to invent the digit) | — |

### Value/history separation — VERDICT: REAL IN CODE

After A earns 100 Merit and transfers 40 to B (canonical `wallet.transfer_merit`):

- REPORTED: `merit_balance(A)=60, merit_balance(B)=40` — **value moved**.
- REPORTED: `standing(A)=100, standing(B)=0` — **history stayed with the earner**.
- Return transfer B→A: balances A=100/B=0, standing still A=100/B=0.
- All slice `origin_earner_id` fields unchanged across transfers (AST: the only
  `origin_earner_id` references inside `merit_transfer` are reads carried
  forward into new slices — **zero write targets**).
- `MeritRecord` is a frozen dataclass; origin set once at accrual.
- Wallet transfer receipts structurally forbid origin keys (code raises
  `WalletError` if any receipt key contains "origin"); every receipt carries
  the "OWNERSHIP ONLY" note.

**The separation of the two readings is structural, not a docstring promise.**
Caveat: the *wiring* of standing into privilege decisions is incomplete —
see CRITICAL-2.

## 3. Unity gauntlet — 27 attack ways + recheck

**27/27 attacks failed as required** (26 HELD + 1 BROKE→CRITICAL-3 in the main
run; the double-credit recheck separately confirmed HELD after a harness fix).

| # | Attack | Result | Mechanism |
|---|---|---|---|
| 1–3 | `share()` Unity via friend / good_friend / family tier | HELD | `UnityBindingError` — checked before balance logic, at every tier |
| 4–5 | `share()` token `"UNITY"` / `"unity"` variants | HELD | `WalletError` (unknown token) |
| 6–13 | Unity emission receipt: bound to another ID, `gated=False`, amount mismatch, missing manifest_hash, missing epoch, zero amount, bad pool, wrong kind | HELD ×8 | `InvalidReceipt` — every field validated |
| 14 | Unity double-credit (same receipt twice) | HELD | Idempotent — original receipt, no new credit |
| 15 | `token_engine._mint("unity")` | HELD | `UnityMintRefused` |
| 16 | Engine genesis re-bind to another ID | HELD | `TokenizeRefused` (GENESIS_CONFLICT) |
| 17 | Fuse second trigger | HELD | `FuseNotArmed` |
| 18 | Direct `_apply_fuse_genesis` on existing holder | HELD | `WalletError` (already holds Unity) |
| 19 | **Rogue `_apply_fuse_genesis` on fresh wallet** | **BROKE** | **→ CRITICAL-3** |
| 20–21 | Forged tier grant (wrong key); tampered grant (friend→family post-signing) | HELD ×2 | `TierViolation` — Ed25519 verification |
| 22 | Family grant without kin bond | HELD | `TierViolation` (kin is binding) |
| 23–24 | Share to unknown recipient; share with no tier grant | HELD | `UnknownWallet` / `TierViolation` |
| 25–27 | Structural: no Unity param on `transfer_merit`; `deduct_per_decision` eFuse-only; `unity_transfer_paths() == []`; `mint_paths()` exactly 2 | HELD | Absence, asserted |

Identity scale: REPORTED keygen 1,321 ms/ID loaded (node subprocess);
derive + open 0.83 ms/ID (pure Python).

## 4. Honor gauntlet

| Test | Volume | Result |
|---|---|---|
| Donation → Honor accrual | 50 | REPORTED 1,712/sec; 50 permanent non-transferable Honor records; `merit_accrued == 0` on every receipt; chain verifies |
| Honor → emission | 1 | HELD — `HonorConversionRefused` |
| Honor → Merit / Honor → eFuse paths | AST audit | **Absent** — zero functions matching `honor*(transfer\|spend\|convert\|redeem\|send\|burn\|swap)` across wallet/tokenomics/token_engine |
| Honor spend via engine | — | No sanctioned path (append-only ledger; records `spendable=False, transferable=False`). A raw in-process list pop "succeeds" only as memory tampering — outside the threat model, equivalent to editing any dict. |

## 5. Cross-coin pipeline

Full cycle: work → gated receipt → `tokenize` (Merit + eFuse) →
`receive_emission` → `transfer_merit` → `donate` → Honor. 5 cycles, all
receipted, all balances/standing assertions held, chain verifies.

**Pipeline ceiling: REPORTED ~0.1 cycles/sec (~9 s/cycle) on the loaded host.**
First bottleneck: Ed25519 node-subprocess signing — 3 signed commits per
cycle (`MERIT_ACCRUAL` + `TOKEN_MINT` + `MERIT_TRANSFER`). The pure-Python
legs (emission credit, donation, idempotency) cost microseconds. **Nothing
broke logically** — the ceiling is subprocess crypto throughput, not coin
logic. Unloaded estimate: ~5–7 cycles/sec (3 × ~150–200 ms signs).

---

## 6. 100% SECURE expansion

| # | Vector | Attempted (how) | Result | Mechanism (code ref) |
|---|---|---|---|---|
| 1 | Double-spend eFuse via `share()` | Same manifest twice | HELD | `Ledger._apply` idempotency — balances (900,100)→(900,100) |
| 2 | Double-spend via `deduct_per_decision` | Same manifest twice | HELD | One deduction; retry returns original receipt |
| 3 | Double-credit via `receive_emission` | Same receipt twice | HELD | Idempotent on receipt `manifest_hash` |
| 4 | Spend beyond balance | Share 1M with 850 | HELD | `InsufficientFunds` — refusal records nothing |
| 5 | Replay signed Merit transfer | Same wallet manifest twice | HELD | Engine NOT called twice — original receipt returned |
| 6 | Replay tier grant | Apply same signed grant twice | HELD | Manifest includes signature — single grant record |
| 7 | **Front-running** | — | **N/A (open on async deployment)** | No mempool/ordering layer exists; all ops are synchronous in-process calls — ordering = call order, nothing to interpose on. **A future relay/mempool MUST add nonce/sequence ordering before any networked deployment.** Flagged, not a code vuln today. |
| 8 | Key compromise: drain victim eFuse | Victim key signs tier grant → `share()` | HELD (expected capability) | Signing as victim IS victim authority; bounded by tier caps (100/share, 10/epoch) |
| 9 | Key compromise: mint eFuse | Victim key → `tokenize` without gated receipt | HELD | Refused (`PurificationRefused` — unlabeled claim; nothing minted) |
| 10 | Key compromise: trigger fuse | Victim key signs fuse auth | HELD | `FuseRefused` — founder key required |
| 11 | Key compromise: forge grant for another ID | Victim key, other as granter | HELD | `TierViolation` — signature binds granter |
| 12 | Key compromise: `transfer_merit` FROM another ID | Other (0 balance) → attacker | HELD | `TokenizeRefused` — insufficient owned Merit |
| 13 | **Keyless Merit drain** | Fresh `Wallet(victim_id)` + `transfer_merit`, **zero auth** | **BROKE** | **→ CRITICAL-1** |
| 14 | Emission forgery (crafted valid-structure receipt) | `receive_emission` with invented manifest, `gated=True` | **BROKE** | **→ CRITICAL-4** |
| 15 | Mint forgery (self-asserted VERIFIED) | `tokenize()` with `provenance="VERIFIED"` string | **BROKE** | **→ CRITICAL-5** |
| 16 | Emission with no receipt / `gated=False` | — | HELD ×2 | `InvalidReceipt` |
| 17 | Tier escalation: exceed friend cap (101 > 100) | — | HELD | `TierViolation` |
| 18 | Tier escalation: crafted payload `tier="family"` | — | HELD | Receipt tier read from **signed grant**, never payload |
| 19 | Tier escalation: forged family grant | Attacker key, victim as granter | HELD | `TierViolation` — signature FAILED |
| 20 | Tier escalation: tampered grant tier | Edit tier post-signing | HELD | `TierViolation` — signature FAILED |
| 21 | Receipt forgery: tier grant bad signature | Random 64-byte sig | HELD | `TierViolation` — cryptographic |
| 22 | Donor exclusion: direct check | Own donation hash | HELD | `DonorExclusionViolation` — the function works |
| 23 | **Donor exclusion bypass (wallet credit path)** | Donate 400 → `receive_emission` to same wallet | **BROKE** | **→ CRITICAL-6** |
| 24 | Donor exclusion: `cause_disburse` | Donor claims from Lock | HELD | `DonorExclusionError` — blanket ban enforced |
| 25 | Donation → Merit laundering | — | HELD (impossible) | `donate()` accrues exactly 0 merit |

**Blast-radius map (compromised Unity private key):**
CAN — sign tier grants as victim (drain eFuse via `share()` within tier
caps); sign kin bonds as victim; drain victim Merit **without the key at
all** (CRITICAL-1). CANNOT — mint eFuse/Unity/Merit (no path; fuse needs the
founder key; `tokenize` needs VERIFIED receipts); forge tier grants for other
IDs (signature binds granter); move Unity (no path); move standing (origin
immutable); exceed victim holdings except via CRITICAL-1.

---

## CRITICAL findings (do not fix per brief — reported with reproducers)

### CRITICAL-1: Merit transfer has NO sender authorization (keyless drain)
`wallet.transfer_merit` / `Tokenizer.merit_transfer` verify identity
*format* and owned balance only — no signature, no tier grant, no consent
proof from the sender. Anyone holding a ledger reference (the Unity ID is
public) can move anyone's Merit.
Reproducer: `wv = Wallet(victim_unity_id, ledger)` (fresh handle, no key);
`transfer_merit(wv, attacker_wallet, 50.0, "theft", engine=eng)` → SUCCEEDS;
victim's Merit drains. Contrast `share()`, which requires a signed tier
grant. Severity: the key-compromise blast radius is worse than modeled —
the key isn't even needed for Merit theft.

### CRITICAL-2: Bought Merit drives emission weight (tokenomics layer)
`standing()` is origin-based and correct, but **nothing in the emission path
reads it**: `tokenomics.emission_close(pool, merit_map, …)` accepts a
caller-supplied `merit_map`, and zero non-test call sites reference
`standing()` in `economics/`. The documented "emission gate reads standing()"
(`token_engine.py` comment; `TokenizeMeritReader` does not exist as code)
is **unwired**.
Reproducer: earner accrues 100 via `tokenize()`; `transfer_merit(earner→buyer,
100)`; `Ledger().emission_close("human", {buyer: Figure(merit_balance(buyer))},
E, epoch)` → emission computed FOR THE BUYER. REPORTED: buyer standing stays
0.0 — the reading is right, the gate doesn't use it.

### CRITICAL-3: Unity mint via `_apply_fuse_genesis` (private-by-underscore only)
The "sole genesis path" (`fuse.trigger_fuse`) is a naming convention, not a
code barrier: `Ledger._apply_fuse_genesis` is a single-underscore method
callable by anyone holding a ledger reference.
Reproducer: `ledger._apply_fuse_genesis(fresh_uid, 777, {}, mh)` → wallet
Unity balance 777. In-process Unity can be minted at will outside the fuse.
(The existing-holder guard works — this is about fresh wallets.)

### CRITICAL-4: Emission receipts not cryptographically bound to issuer
`_validate_emission_receipt` checks STRUCTURE only — no signature binds the
receipt to the tokenomics engine.
Reproducer: `forged = {kind:"merit-emission", token:"eFuse",
unity_id:victim, amount:999, gated:True, pool:"human", merit_weight:1.0,
manifest_hash:<fresh>, epoch:7}`; `receive_emission(wallet, 999, forged)` →
999 eFuse credited. Anyone with a wallet handle mints eFuse credit at will.

### CRITICAL-5: Provenance is a self-asserted string (tokenize gate)
`_require_gated` checks `provenance == "VERIFIED"` as a string comparison —
no signature from the gating authority.
Reproducer: `tokenize({unity_id, kind:"work", merit_value:50,
provenance:"VERIFIED", manifest_hash:<64hex>, …})` → `MeritRecord` +
`EFuseToken` minted. UNKNOWN-never-pays holds only if callers are honest
about labels.

### CRITICAL-6: Wallet donor exclusion is unwired (dead check)
`check_donor_exclusion` has **zero non-test call sites** in the repo
(`grep -rn` verified). `donate()` records exclusion hashes; no wallet
disbursement/credit path consults them. Demonstrated: `receive_emission` to
a donor succeeds with no exclusion consult. (The tokenomics layer has its
own blanket enforcement — `cause_disburse` refuses ANY donor — but the
wallet layer where `donate()` lives enforces nothing on its own paths.)

### Transient BLOCKER (resolved during run, not a vuln)
`dclm/token_engine.py` was unimportable for ~10 min (IndentationError from a
mid-edit collision, ~07:48 UTC); parent confirmed repaired and all 41 wallet
tests pass. Engine measurements were first taken against a byte-identical
`/tmp` snapshot (only the collapsed newline restored, repo file untouched),
then re-run against the repaired canonical file — all reported numbers are
from the repaired file.

---

## Summary for the orchestrator

- **What broke first:** nothing logical — the pipeline ceiling is Ed25519
  node-subprocess signing (~3 signed commits/cycle → ~0.1 cycles/sec loaded;
  ~5–7/sec unloaded estimate). Pure-Python paths show no degradation knee
  (emission ~1.1–1.4k/sec to 3k ops; accrual ~7k/sec; decay 2.3k/sec).
- **Value/history verdict:** REAL in code — value moves, standing never does
  (origin-immutable slices, frozen records, AST-verified, receipt-level
  enforcement).
- **CRITICALs: 6** (1 transient blocker resolved + 5 structural + 1 wiring).
  The five structural breaks cluster in two themes: **(a) missing
  cryptographic binding** — transfer authorization (C-1), receipt↔issuer
  binding (C-4), provenance labels (C-5); **(b) unwired enforcement** —
  standing→emission gate (C-2), donor exclusion call sites (C-6) — plus
  **(c)** the underscore-private Unity mint (C-3).
- **100% SECURE bar: NOT MET.** 61 attacks held, 6 broke (unique; two log
  lines are re-runs). The held list is
  strong (Unity binding at every tier, idempotency everywhere, tier crypto,
  fuse one-shot, Honor non-conversion), but the six breaks are real and
  reproduced.

**Files:** runner `~/workspace/unity-world/economics/gauntlet/gauntlet.py`,
logs `run.log` / `run_rest.log` / `run_rest2.log`, JSON
`results_rest.json` / `results_rest2.json` (partial, per completed sections).
