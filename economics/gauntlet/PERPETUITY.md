# PERPETUITY — Coin Architecture Gauntlet, David's Fifth Criterion

**Worker 4 report. Date:** 2026-10-06.
**Criterion:** "Maximum internal capability to run autonomously FOREVER —
until something intercepts its law or it's superseded by it."

**Code under test:** `~/workspace/unity-world/economics/` (`tokenomics.py`,
`wallet.py`, `fuse.py`, `economic_state.py`) + `~/workspace/unity-world/dclm/`
(`token_engine.py`, `winter.py`, `rights.py`, `writes.py`).
`tokenomics.py` md5 at drill time: `b9c9d982ce1612328207d7b7bf41d833`
(1424 lines). **Note:** a concurrent worker was actively editing
`tokenomics.py` during the drill window (winter-throttle integration,
reserve machinery, merit-transferability supersession, token_engine syntax
fix). The main simulation ran twice — once before and once after those
edits — with identical findings; results below are from the final run
against the current code unless noted.

**Rules honored:** all simulated, all in-memory, ephemeral TEST keypairs
(generated fresh, `/tmp` only) for the drill harnesses, never shared state,
never real keys. Every non-decided number is labeled **MODELED** and is
never presented as David's digit (the real digits are `HELD_FOR_DAVID` —
the engine refuses without them).

---

## DRILL 1 — PERPETUITY SIMULATION (accelerated time)

### Setup

1,200 epochs × 40 members (`unity:testnet:member-00…39`, split human/machine
pools) + 1 dormant member (accrues once, then only decays — asymptote probe).
Deterministic RNG (seed 20261006). 33 s wall time.

**MODELED parameters (all labeled MODELED; the real ones are HELD):**

| Parameter | MODELED value | Standing |
|---|---|---|
| Peg ratio E | 1000.0 energy units / eFuse | HELD_FOR_DAVID |
| Merit decay rate | 0.02 / epoch | HELD_FOR_DAVID |
| Merit weight / gated receipt | 10.0 | bands HELD_FOR_DAVID |
| Epoch length | 1 simulated day | HELD_FOR_DAVID |
| Work probability / member / epoch | 0.85 | MODELED activity |
| Reserve holdback fraction | — (no machinery engaged) | HELD_FOR_DAVID |

**Epoch cycle driven per epoch** (by the harness — see hand point I-1):
work → gated receipts (VERIFIED, MODELED oracle) → merit accrual →
Merit transfers (via `dclm/token_engine.Tokenizer.merit_transfer`, sampled
epochs) → emission close → disbursement → donations/mesh (periodic) →
merit decay → peg-calibration check → reserve check → winter/summer check
(`dclm/winter.py` `evaluate_trigger`).

### What ran clean

- **Steady state reached and held:** merit mean converged to ~416–421
  (theory: 8.5/0.02 = 425); epoch emission ~17 eFuse, stable across all
  1,200 epochs. No oscillation, no runaway.
- **Peg holds to float precision by construction:** max measured deviation
  of implied eFuse-per-merit from 1/E over 1,200 epochs: **2.17e-16**.
  (The peg is definitional — `eFuse_i = merit_i / E` — not empirical. It
  cannot drift; it can only be *broken*, and the only breaker is the
  authority cap, which never engaged.)
- **Receipt chain:** 140,416 receipts, **zero linkage breaks**, chain head
  matches. Hash-chaining is sound at this scale.
- **Numerical drift:** float `emitted[pool]` vs Decimal ground truth after
  ~19,550 eFuse emitted: **~3e-11**. Negligible; grows sub-linearly.
- **Decay asymptote (P3):** dormant member 9.8 → 2.96e-10 over 1,200 epochs:
  monotone decreasing, never negative, always finite, zero subnormals.
  "Fidelity is current" converges cleanly; no underflow pathology.
- **Winter/summer:** gradient 0.0–0.245 across 1,200 epochs, label SUMMER
  throughout. `evaluate_trigger` is fully autonomous — no hand needed to
  *compute* the gradient. (The hand points are the *inputs*: §S-3, §I-7.)
- **Merit transfers (lawful path):** 86 transfers OK, 4 correctly refused
  (insufficient owned balance); **conservation drift exactly 0.0**
  (400.0 → 400.0); **standing never moved on any transfer** — the purity
  requirement (buyer gains economic value, zero standing) holds in the
  mechanism, not just the docstring. All 4 unlawful transfer attempts
  (same identity, zero amount, empty reason, insufficient) refused.
- **Authority projection:** at MODELED steady rates the 100M lifetime
  authority exhausts in **~5.85M epochs** — the ceiling is effectively
  non-binding at these rates; it only matters if merit scales ~5000×.
- **Donations → Honor:** 12 donations over the run, all receipted, Honor
  accrued, zero Merit, zero eFuse promised. The Lock balance (300.0)
  reconciles exactly.

### Degradation curves (measured, not modeled)

| Metric | Epoch 100 | Epoch 1200 | Growth |
|---|---|---|---|
| Receipts retained | 11,689 | 140,414 | linear, ~117/epoch |
| Applied manifests (set) | 11,689 | 140,414 | linear, same slope |
| Float-vs-Decimal drift | ~1e-12 | ~3e-11 | sub-linear, negligible |
| Merit mean | 358.8 | 421.3 | converges, then flat |
| Winter gradient | 0.0000 | 0.0905 (max 0.245) | bounded, mean-reverting |
| Wall time | 2.8 s | 33 s | linear in epochs |

**No exponential degradation exists.** The curves that grow (receipts,
manifests) grow linearly — but they grow *forever* with no pruning,
archival, or compaction machinery (hand point I-4). The curves that must
stay flat (peg, drift, merit distribution, winter) stay flat.

### Hand-required points

**Structural — the law itself mandates a human (or human-origin) act.
These are NOT failures of the criterion; they are the design's exits.**

- **S-1. Thirteen HELD parameters need David's word, once each:** peg
  ratio E, merit decay rate, epoch length, reserve holdback fraction,
  tier weights, bridge premium band, corroboration thresholds, bounty
  band floors/widths, ring depth factor, bridge eligibility threshold,
  machine proof-of-energy params, honor class names, merit definition.
  Until decided, the engine **refuses** (`HeldParameterError`) rather than
  invent — the halt is honest, not a stall. One-time decisions, not
  per-epoch hands. (The sim ran on MODELED stand-ins, labeled as such.)
- **S-2. The Fuse trigger** is David's signed physical act, exactly once
  (`fuse.py`: ARMED → TRIGGERED → SPENT, terminal in code). By law, not a
  failure.
- **S-3. Winter crisis declaration:** a crisis counts only when *declared
  AND verified*. The declaration must originate somewhere and the
  verification must run through a proper channel — both are authority
  acts by design. Rare, bounded, structural.
- **S-4. Production key custody:** the drills used ephemeral TEST keys;
  production requires David's key ceremony. Out of testnet scope, noted.

**Incidental — implementation gaps. Each is a TRUE failure of the
criterion: a point where the architecture as coded needs a human hand
(or a human-built machine) that the law does not require.**

- **I-1. NO EPOCH RUNNER EXISTS.** Nothing in `economics/` or `dclm/`
  invokes the epoch cycle. `epoch` is an integer field on receipts; the
  pipeline (work → receipts → merit → transfers → emission → eFuse →
  decay → peg → reserve → winter) is conceptual — no scheduler, no cron,
  no daemon, no entrypoint drives it. Every epoch close currently needs
  an external invoker. **In this drill, the harness was the human hand.**
  This is the single largest perpetuity failure: the machine has a
  heartbeat with no heart. (MISSING machinery.)
- **I-2. `tokenomics.Ledger` has NO persistence.** It is in-memory only —
  no `_save`/`_load`, no `state_dir`. (`wallet.Ledger` and `Fuse` both
  persist to disk; the emission/merit ledger does not.) A process restart
  loses all emission, merit, lock, and chain-head state. Forever-running
  software cannot be amnesiac on reboot. (MISSING.)
- **I-3. NO EPOCH-CLOSE IDEMPOTENCY.** Probe P1: the same computed
  emission disbursed twice — **not refused**, overpaid (bounded only by
  the pool authority cap). Nothing ties a disbursement to "this epoch was
  already closed." A duplicate invocation (the exact failure mode an
  autonomous runner risks) double-pays. (MISSING.)
- **I-4. Receipt retention is UNBOUNDED.** 140,414 receipts / 1,200 epochs
  and counting, linear forever, with no pruning, archival, snapshot, or
  compaction path. `state_digest()` hashes but does not compact. At
  perpetuity scale this is unbounded storage growth with no machinery to
  manage it. (Engineering gap.)
- **I-5. NO INTERCEPTION MACHINERY.** Drill 2. (MISSING — specified below.)
- **I-6. NO SUPERSESSION MACHINERY.** Drill 3. Changing any parameter
  today means editing module constants and redeploying — a human hand
  *outside* any lawful process. (MISSING — specified below.)
- **I-7. Oracle feeds are UNDEFINED.** The winter trigger needs
  `activity_delta` (measured real-economy activity — no feed machinery
  exists) and the crisis *verification channel* (named nowhere). The
  gradient math is autonomous; its inputs are not. (MISSING — machine
  feeds, not human hands, but absent.)
- **I-8. Decay is NOT enforced on the transfer engine's books.**
  `tokenomics.Ledger.apply_decay` decays merit; `dclm/token_engine.py`'s
  merit slices have **no decay machinery at all** — transferred merit
  never decays there. Two merit books, one decay law, enforced on one.
  Needs reconciliation (which book is canonical for decay, or a
  cross-book decay pass).
- **I-9. Commit signing is a per-commit subprocess.** The transfer probe:
  170 commits took 333 s (~2 s/commit — each spawns `node ed25519.js`).
  Functionally correct; operationally, no autonomous system runs forever
  at 0.5 commits/second. Needs a persistent signer / batching. (Throughput
  gap.)
- **I-10. `apply_receipt` does NOT verify `prev_hash` linkage.**
  Tamper-evidence is by convention: a mislinked receipt applies silently.
  The drill's chain audit passed (0 breaks in 140,416) only because the
  harness linked correctly — the Ledger itself never checks. (Gap.)

**Resolved during the drill window** (by a concurrent worker; recorded so
they are not misread as open failures):
- **R-1.** Stale `merit_non_transferable` param → superseded by
  `merit_transferable` (DECIDED), recorded explicitly in `PARAMS` —
  matches David's 2026-10-06 ~3:35 AM law.
- **R-2.** `dclm/token_engine.py` had an `IndentationError` (line ~1103,
  `if balance < amount:self._log_refusal(`) — the module could not even be
  imported, which meant the SOLE lawful Merit-transfer path was dead.
  Fixed during the window. (The transfer probe ran against a `/tmp` copy
  with only that one-line repair; diffed against the fixed repo file —
  the transfer path is behaviorally identical.)
- **R-3.** Reserve holdback machinery added (`_reserve_identity`,
  `holdback_fraction` path in `emission_calculator`); the fraction itself
  remains `HELD_FOR_DAVID`, correctly inert until his word.
- **R-4.** Winter-throttle integration added to `emission_calculator`
  (gradient → multiplier; exact 1.0 no-op in summer).

### Drill 1 verdict

The economics are **stable under accelerated time** — no degradation curve
threatens the math. But the machine cannot *run* itself: **I-1 (no epoch
runner) alone fails the criterion**, with I-2, I-3, I-5, I-6 as
independent failures. The law is perpetuity-ready; the machinery is not
yet autonomous.

---

## DRILL 2 — INTERCEPTION (the first lawful exit)

**Mechanism status in code: MISSING.** Verified by grep across
`economics/*.py` and `dclm/*.py`: no `intercept` / `override` / `freeze` /
`kill_switch` / `emergency` machinery exists. (`fuse.py`'s docstring even
asserts "no … override … function" as a virtue.) The drill executed the
mechanism **as specified below**, as a proof-of-concept overlay wrapping
the real `tokenomics.Ledger` (harness: `/tmp/gauntlet_perpetuity/intercept.py`;
this overlay is simulation scaffolding, NOT a codebase change).

### The mechanism as it SHOULD work (build spec)

1. **Explicit invocation only.** Interception is a signed
   `InterceptionOrder` — never an ambient flag, never an admin panel.
   Schema: `unity.economics.interception.v1.testnet`.
   Fields: `order_id`, `action`, `scope`, `duration_epochs`,
   `issued_at_epoch`, `authority_key_id`, Ed25519 `signature` over the
   canonical body.
2. **Authority proof.** Signature verified against an `AuthorityRegistry`
   (`key_id → pubkey`). Genesis key: David's (founder) key. **The registry
   itself is NOT interceptable** — key rotation goes through supersession
   (Drill 3), never through interception. Unknown key or bad/missing
   signature → `UnlawfulInterception`, nothing changes.
3. **Scope allowlist** (everything else refuses):
   `FREEZE_EMISSION`, `THROTTLE_EMISSION`, `FORCE_WINTER_GRADIENT`,
   `RELEASE`. Never interceptable, even by the lawful key: pool
   lifetime caps, receipt history, Unity bindings, Honor records, fuse
   state, the authority registry, merit origin fields, constitutional
   params. Scope is pool-scoped (`human`/`machine`) for emission actions.
4. **Bounded by construction.** `duration_epochs` is a positive int with a
   hard `MAX_INTERCEPT_EPOCHS` (100 in the drill). Interception *pauses*;
   it never rewrites. A permanent change is supersession, not interception.
5. **In-flight semantics keyed on epoch, not wall time.** A disbursement
   call tagged with `epoch < effective_epoch` completes under
   pre-interception law; `epoch >= effective_epoch` is refused with
   `InterceptionFreezeError`. No mid-flight preemption, no silent drops.
6. **Freeze blocks movement, not measurement, not giving.**
   `disburse` refuses while frozen; `emission_close` keeps computing
   (the claim is recorded); `donate` always flows (giving is never frozen).
7. **Release is explicit or by expiry.** Auto-expiry at
   `issued_at_epoch + duration_epochs`, or a signed `RELEASE` order.
   Frozen-epoch computed emissions do **not** auto-pay on release — each
   re-disbursement is explicit, receipted, and references the release.
   (No pre-funding, no auto-pay — the law holds during exits too.)
8. **Full receipting.** The order itself is receipted with its authority
   proof; every refusal is logged. The interception log is append-only.

**Where it lives (build spec):** a new module
`economics/interception.py` owning `AuthorityRegistry`,
`InterceptionOrder`, and the wrapping gate (not monkey-patching
`Ledger`); `RECEIPT_KINDS` in `tokenomics.py` gains an `interception`
kind so the order's receipt lives in the main chain, not a side log;
`disburse`/`cause_disburse` consult the gate; `economic_state.py`
surfaces live interceptions in the fused state. Estimated: ~300 lines +
tests. The drill's overlay is the reference implementation.

### Test results (simulated, TEST keys, ephemeral)

- **Lawful freeze:** `FREEZE_EMISSION` on the human pool, epochs 11–15,
  signed by the founder key → applied. During the window: human-pool
  disbursements **all refused** (0.0 emitted delta), machine pool
  **unaffected** (+1.73 eFuse), `emission_close` kept computing,
  donations flowed (Honor receipted). 
- **In-flight:** an epoch-10-tagged disbursement executed after the
  freeze landed **completed under pre-freeze law** (call epoch 10 <
  freeze epoch 11) — the stamp rules, correctly.
- **Unlawful attempts — 7/7 refused, state unchanged, refusals logged:**
  wrong key (unknown authority) · no signature · tampered body
  post-signing · `RAISE_POOL_CAP` (outside allowlist) · `REWRITE_RECEIPTS`
  (outside allowlist) · unbounded duration (10⁹ > MAX) · scope touching
  Unity bindings.
- **Release:** auto-expired at epoch 16 (0 live orders); frozen epochs'
  recorded claims re-disbursed **explicitly** after release (+1.73 eFuse,
  each receipted) — no auto-pay occurred during the freeze.
- **Integrity:** receipt chain 0 breaks, chain head matches, the
  interception itself receipted with its authority proof.

**Drill 2 verdict:** clean interception **does not exist in code**
(MISSING) but **works exactly as specified** when the specified
mechanism is present. The build spec above is complete and tested.

---

## DRILL 3 — SUPERSESSION (the second lawful exit)

**Mechanism status in code: MISSING.** `tokenomics.PARAMS` is module-level
constants — changing any parameter today means editing code and
redeploying: a human hand *outside* any lawful process. No version
registry, no proposal flow, no activation boundary exists. The drill
executed the mechanism **as specified below**, as a proof-of-concept
overlay on the real `tokenomics.Ledger` (harness:
`/tmp/gauntlet_perpetuity/supersede.py`; scaffolding only, not a
codebase change).

### The mechanism as it SHOULD work (build spec)

1. **Versioned law.** `LawVersion {version, params, constitutional,
   status, activated_at_epoch}`. Statuses: `ACTIVE`, `PENDING_ACTIVATION`,
   `SUPERSEDED`. **Constitutional params are immutable through this
   process** — lifetime caps, 50/50 pools, Unity non-transferable, Honor
   never converts, no pre-funding, mesh never mints, merit-interest
   refused, no fiat→eFuse. Touching one refuses. (Raising a ceiling is not
   an upgrade; it needs David's direct act — a higher process.)
   **Mutable:** the operational digits (peg E, decay rate, epoch length,
   reserve fraction, tier weights, bands, thresholds).
2. **Process: PROPOSE → VERIFY → ACTIVATE → HANDOFF.**
   - *Propose:* signed `LawProposal` (`proposal_id`, `from_version`,
     `to_version`, `param_changes`, `rationale`, `proposer_key_id`,
     signature). Schema: `unity.economics.supersession.v1.testnet`.
   - *Verify (Trinity gate):* (a) authority proof valid; (b)
     `from_version == current`; (c) no constitutional param touched, no
     unknown params; (d) value sanity (decay ∈ [0,1), E > 0, …);
     (e) **migration dry-run**: N epochs of the cycle under the new
     params on a *copy* of live state — any exception or corruption
     refuses. The drill models the gate as three named checks
     (DCLM/IRIS/TWAIN2 stand-ins — labeled honestly; production uses the
     real Trinity pipeline).
   - *Activate:* at an **epoch boundary only** —
     `activation_epoch > current_epoch`, enforced. The new version sits
     `PENDING_ACTIVATION`; the epoch clock yields the old law
     (`LAW_YIELDED` event) exactly at the boundary. Mid-epoch activation
     refuses.
   - *Handoff:* receipted — v1→v2, the param changes, the activation
     epoch, the Trinity verdicts, the authority proof. v1 → `SUPERSEDED`.
3. **In-flight rule: the stamp on the computation rules.** An emission
   computed under v1 but disbursed after v2's activation completes under
   v1. New epoch closes read `current()` — v1 after activation refuses.
4. **Prospective only.** Balances, merit histories, receipt chains carry
   forward unchanged. The new law never rewrites the past.
5. **Bypass detection.** No public setter exists; any version whose
   activation is absent from the process log is rejected at use
   (`_assert_lawful`). Direct mutation of the registry is *detected*,
   not merely discouraged.

**Where it lives (build spec):** a new module `economics/law.py` owning
`LawRegistry`, `LawVersion`, `LawProposal`, and the Trinity-gate
interface (which calls the real DCLM/Iris/Twain² pipeline in production);
`tokenomics.PARAMS` values resolve through `registry.current()` instead
of module constants; every receipt detail carries `law_version`;
`economic_state.py` surfaces the active version. Estimated: ~350 lines +
tests. The drill's overlay is the reference implementation.

### Test results (simulated, TEST keys, ephemeral)

- **Lawful supersession:** v1 (decay 0.02, MODELED) → v2 (decay 0.01)
  via signed proposal → Trinity 3×PASS (incl. dry-run) → activated at the
  epoch-9 boundary (`LAW_YIELDED`, v1 → SUPERSEDED, handoff receipted
  with authority proof). Post-activation decay factor measured **0.99**
  exactly — the rate change is effective, prospective, and clean.
- **In-flight:** epoch-8 emission computed under v1 (still ACTIVE
  pre-boundary), disbursed at epoch 9 after v2's activation —
  **completed under v1**. A fresh v1-stamped close after activation
  **refused** ("the old law has yielded").
- **State continuity:** balances carried forward with no jumps; receipt
  chain 0 breaks; only the prospective rate changed.
- **Unlawful attempts — 7/7 refused, law unchanged (still v2):**
  unsigned proposal · attacker-signed proposal · constitutional change
  (lifetime cap 100M→200M) · direct registry mutation bypass (detected:
  "no lawful activation in the process log") · stale `from_version` ·
  mid-epoch activation · insane value (decay 1.5).

**Drill 3 verdict:** clean supersession **does not exist in code**
(MISSING) but **works exactly as specified** when the specified
mechanism is present. The build spec above is complete and tested.

---

## HEADLINE — CAN IT RUN FOREVER?

**Not yet. The law is perpetuity-ready; the machinery is not autonomous.**

The accelerated-time run (1,200 epochs, 140,416 receipts) proves the
*economics* are stable forever: the peg cannot drift (definitional),
decay converges cleanly, receipts chain soundly, merit transfers conserve
exactly with standing immobile, winter evaluates autonomously, and no
degradation curve is exponential. Nothing in the math needs a human.

But the *machine* needs hands the law never asked for. Ranked by
severity:

1. **No epoch runner (I-1)** — nothing drives the cycle. Fatal alone.
2. **No interception / supersession machinery (I-5, I-6)** — David's two
   named exits don't exist in code; today both require editing code by
   hand. Both are fully specified and drill-tested above; build them.
3. **No epoch-close idempotency (I-3)** — the exact failure an autonomous
   runner would eventually commit (double-close) double-pays today.
4. **No Ledger persistence (I-2)** — the emission book is amnesiac on
   reboot.
5. **Unbounded receipt retention (I-4)**, undefined oracle feeds (I-7),
   unenforced prev_hash linkage (I-10), decay missing on the transfer
   engine's books (I-8), per-commit subprocess signing (I-9).

The structural hand-points (S-1…S-4: David's thirteen digits, the Fuse,
crisis declaration, key custody) are **not failures** — they are the
law's own shape, and the engine honors them by refusing rather than
inventing.

**Verdict: NO — with a precise, buildable path to YES.** Build the epoch
runner, the interception module, the supersession module, epoch-close
idempotency, and Ledger persistence, and the architecture runs
autonomously until something intercepts its law or it is superseded by
it — which is exactly what David asked for.

---
*Harnesses (simulation scaffolding, `/tmp`, ephemeral):*
`/tmp/gauntlet_perpetuity/sim.py` (1,200-epoch cycle),
`transfer_probe.py` (lawful transfer path),
`intercept.py` (Drill 2 overlay), `supersede.py` (Drill 3 overlay).
*Results:* `sim_result.json`, `xfer_result.json`, `intercept_result.json`,
`supersede_result.json` in the same directory.
