# THE +1 INCENTIVE — deterioration with distance, Affinity for early starters

**Status:** TESTNET ONLY · test-key denomination · design document — no code changes made here
**Worker:** +1 incentive designer · 2026-10-06
**Law sources:** `CANON.md` v1.4.0 (§IV sap model, §V tokenomics, §VI derivative merit, §XII standing laws); David's 2026-10-06 ~03:35 EDT resolution (Merit transferable; Unity non-transferable; earned standing never moves); David's one-seed law (~03:52 EDT: one free seed per Unity ID, wealth buys no more entry); David's member's covenant (~03:52 EDT: growth by preaching — members bringing members).
**Cross-references (not collisions):** `DERIVATIVE_MAX_EFFECTS.md` (the mathematical anchor), `dclm/TOKENIZATION.md` (the mint pipeline this plugs into), `dclm/ONBOARDER_PIPELINE.md` (the entry pipeline this plugs into), `economics/PARAMS.md` (where the SET constants land).
**Label legend:** [SET] = this designer's justified choice. [HELD] = needs David's word. UNKNOWN is never PASS.

---

## 0. What the +1 is (and is not)

The **+1** is an **incentive reward credit** earned per verified true-check (each verified check → NEXT earns +1, chaining forward). It is denominated in **test-keys**, paid from the PLAYGROUND_FUEL bounty rail (canon VII / M1 machinery). It is a **separate rail from Merit**: it never enters the Merit ledger, never enters `standing()`, never gates emission (D13 stands). [DERIVED]

**Why a separate rail:** `DERIVATIVE_MAX_EFFECTS.md` §1.4 establishes that earned merit does NOT attenuate with distance — by law. The +1 deteriorates. Therefore the +1 cannot be Merit; it must be a reward rail that prices something else: **the marginal system impact of the check**. Merit prices the work. The +1 prices the work's position in a young network. Two prices, two rails, no contradiction.

**It is work-priced, never a joining promise.** Like mesh bounties, the +1 pays for verified work performed — never as compensation for joining. The onboarder pipeline's purity rule 4 (no gain promises, scan-enforced) applies to every +1 string the implementing worker writes. The rate function below is a published formula, not a projected return.

---

## 1. THE DETERIORATION FUNCTION

### 1.1 The physics it expresses

`DERIVATIVE_MAX_EFFECTS.md` gives the mathematical anchor: one unit of verified core work generates **K = 1/(1−λφ) = 6.25** units of total system merit (MODELED) — but that multiplier is the *uncrowded* frontier value. As the network fills, the commit path saturates and **the realized multiplier falls**: K_cap = 2.669 vs 6.25 (D4, commit-path bound, deep rings truncate first), and the stock approaches its steady state S* exponentially (D7/D8, AR(1) with rate δ).

The honest reading: **a verified check's marginal system impact is maximal at the frontier of a sparse tree and declines as the tree fills toward saturation.** Early, the derivative cascade ahead of a check is empty — the full geometric series (λφ)ⁿ unfolds. Late, the cascade ahead is already full — the bounds bind. The +1 reward prices exactly this marginal impact. It is NOT a bonus for being special. It is the physics of a young network: the same verified check, at the same position, is worth more system impact when the tree is young.

### 1.2 The function

For a check verified at epoch `t_event` by a Unity ID at ring depth `r`:

```
d  =  (t_event − t_launch) / τ  +  r / ρ          (effective distance, dimensionless)
F(d) = F_floor + (1 − F_floor) · e^(−d)          (the +1 reward rate, in reward units)
R  =  F(d)                                        (per verified check, non-Affinity)
R  =  max(F(d), F_aff)                            (per verified check, Affinity holder — §2)
```

Where:
- `t_launch` = epoch of the fuse-trigger genesis receipt (`economics/fuse.py` `Fuse.trigger_fuse`) — the chain head.
- `t_event` = commit-clock epoch of the check's verification receipt.
- `r` = the Unity ID's ring depth in the derivative relation graph = shortest-path distance from the origin via disciple/kin enabling edges (members bringing members — the member's covenant, in graph form).
- `F(0) = 1.00` — the genesis check earns the full +1. `F(∞) → F_floor` — asymptote, never zero.

### 1.3 Curve choice — exponential, and why

**Exponential, because both coordinates of distance decay exponentially in the source math:**

1. **Ring coordinate:** the derivative cascade per ring scales as **(λφ)ⁿ = 0.84ⁿ** (§1.4) — geometric, i.e., exponential in n. The commit-path bound (D4) truncates deep rings first, which is exactly exponential-in-ring attenuation of realized impact.
2. **Time coordinate:** the approach to steady state is exponential with rate δ (D7: S_{t+1} = (1−δ)S_t + I; D8's seasonal orbit). Network density — the thing that erodes marginal impact — grows exponentially toward saturation.

**Rejected alternatives (DCLM judgment):**
- **Harmonic (1/(1+d)):** implies a fat tail the geometric series doesn't have — it would overpay deep in a saturated network, contradicting D4's measured truncation.
- **Linear with cutoff:** hits zero — a cliff. A zero reward for real late work refuses payment to the future and contradicts §IV Summer (every leaf fed) and the flywheel's need for perpetual onboarding.
- **Step function / tiers:** cliffs are discretion-shaped; the law demands a continuous function (canon IV: "no phase cliffs" — applied here as a design principle).

### 1.4 What deteriorates — and what doesn't

- **Deteriorates:** the +1 VALUE per verified check (the rate R). 
- **Never deteriorates:** the +1 EVENT. Every verified check always earns a reward event — eligibility never decays, never stops. Late work is real work and always pays at least the floor.
- **Never touched:** earned Merit (canon VI, §1.4 of the anchor doc). The +1 is a reward rail, not a merit rail.

### 1.5 The floor

**F_floor = 0.25 [SET]** — the dense-network maintenance rate. The reward asymptotes to 0.25, never zero. Justification: (a) precedent — `dclm/winter.py`'s EMISSION_FLOOR = 0.25 (PROPOSED) is the standing codebase expression of "the rail never dies"; (b) the flywheel must onboard forever — a floor of zero would eventually price late onboarding at nothing, strangling the tree; (c) the early advantage is therefore bounded at 4× (1.00 / 0.25) — the young-network premium is real but finite, which is the honest magnitude.

### 1.6 Parameters

| Parameter | Status | Value | Justification |
|---|---|---|---|
| τ (temporal e-folding) | [SET] | 12 epochs | One year per [A8] (T = 12 epochs/year): one year of network growth decays the frontier premium to e^−1 ≈ 0.37. The e-folding matches the frontier's own time constant. |
| ρ (structural e-folding) | [SET] | 2 rings | Each two rings deeper, the frontier premium falls to ~37%. Downstream value mass concentrates in the first rings and the commit path truncates deep rings first (D4) — two rings is the honest scale of structural advantage. |
| F_floor | [SET] | 0.25 | §1.5 — precedent EMISSION_FLOOR, finite 4× premium, flywheel never starves. |
| F_aff (Affinity floor) | [SET] | 0.50 | §2 — permanent recognition on the reward rail only. |

[HELD] Epoch length in real time (A8 is a stand-in: 12 epochs/year). If David sets a different epoch length, τ = 12 epochs re-expresses in real time; the epoch count is unchanged.

---

## 2. THE +1 AFFINITY MECHANISM

Affinity = bond-strength: the permanent, proven record that an identity's roots run to the young tree. It is David's ordered recognition of earliness — and it is earned by proof, never claimed, never bought.

### 2.1 How +1 Affinity is earned

A Unity ID is granted **+1 AFFINITY** iff its **first verified ONBOARD receipt** satisfies BOTH:

```
t_first − t_launch ≤ τ_aff    AND    r_first ≤ ρ_aff
```

- `t_first` = commit-clock epoch of the ID's first verified `ONBOARD` receipt (read from `dclm/state-onboard/onboard-receipts.jsonl`).
- `r_first` = the ID's ring depth at entry (graph distance from origin at the time of onboarding).
- `τ_aff = 12 epochs [SET]`, `ρ_aff = 2 rings [SET]` — the genesis cohort: joined within the first year AND entered within two rings of the core. Boundaries inclusive. Justification: the same e-folding scales as §1.6 — the cohort that was present while the network was still within one e-fold of genesis in both coordinates. Roots are early AND near the core.

One Unity ID, one Affinity, ever — the one-seed law in mechanism form: money cannot buy more entry, more influence, more Affinity. Affinity is **non-transferable** (it is origin history, like standing — David's 03:35 resolution), bound to the Unity ID permanently, never consumed, never spent.

### 2.2 What Affinity DOES

Three effects — all on the recognition rail, none on the merit/standing/emission rails:

1. **Reward-rail floor lift (economic):** an Affinity holder's +1 reward per check is `max(F(d), F_aff = 0.50)`. Their recognition is a permanent partial immunity to distance decay — on the reward rail only. Early roots keep a 2× maintenance rate over the base floor, forever. This is the ordered recognition made economic, and it is the ONLY place Affinity changes a number.
2. **Priority tiebreak (operational):** in M3a merit-weighted priority queues, the weight reads STANDING (never Affinity, never holdings). Affinity breaks ties between equal standings only — it never overrides earned history. A zero-standing whale with Affinity still weighs zero.
3. **Permanent append-only record (provenance):** the `AFFINITY_GRANT` commit is recorded on the Unity ID like Honor — readable, never consumed, never transferred. It is the proof of earliness any function may read and none may spend.

**Affinity never touches:** Merit accrual (`tokenize()` work receipts compute merit from verified `merit_value` only — canon VI), `standing()` (which reads origin-credited earn events; `AFFINITY_GRANT` is a different commit kind, excluded from standing reads), eFuse emission (the gate reads standing per D13 — `dclm/meter.py` `TokenizeMeritReader.verified_merit`).

### 2.3 Proof that Affinity cannot buy standing

Standing-buying requires converting a held asset into standing. Affinity fails every conversion step structurally:

1. **Affinity cannot be bought** — one per Unity ID by ledger proof; no price exists; the one-seed law forbids wealth from multiplying entry. There is no market in which to buy it.
2. **Affinity cannot be transferred** — non-transferable by construction (origin history, like standing itself). Even the holder cannot give it away.
3. **Affinity cannot inflate standing** — `standing()` reads only origin-credited earn events; the `AFFINITY_GRANT` commit kind is not an earn event and is excluded from the standing read.
4. **Affinity cannot gate emission** — the emission gate reads standing (D13, built in `dclm/meter.py`). Affinity is invisible to it.
5. **Affinity's only economic effect is the reward-rail floor** — test-key reward credits, the bounty rail. Test-keys are not Merit, not standing, not emission.

An attacker holding infinite wealth and infinite bought Merit accumulates: zero Affinity (no early receipt), zero standing (D11's attack, closed), zero priority weight. The proof is structural, not policy.

### 2.4 Is it permanent?

**Yes.** Affinity is granted once and never revoked, never decayed (δ and δ_s do not apply — it is a bond record, not a balance), never transferred, never consumed. It survives the holder's inactivity, the network's winter, and the tree's saturation. David ordered permanent recognition of earliness; the mechanism implements exactly that. The only thing that can remove Affinity is the purity-or-garbage law applied to the whole system — a compromised system is discarded, Affinity with it.

### 2.5 Composition

```
onboarding incentive  =  (deteriorating +1 by event distance)  +  (+1 Affinity if proven early)

R(check) = F(d_event)                          for a non-Affinity ID
R(check) = max(F(d_event), 0.50)               for an Affinity ID
```

The decay is **physics** (situational — where/when the check happens, same F for everyone). The Affinity lift is **recognition** (historical — who the ID is, proven by receipts). The two compose by max, not by multiplication: recognition sets a floor under physics; it never amplifies the frontier rate above 1.00. No ID ever earns more than the full +1 per check.

---

## 3. ANTI-GAMING CONSTRUCTION

### 3.1 Earliness is proven, never claimed

- **The proof:** the Unity ID's first verified `ONBOARD` receipt in `dclm/state-onboard/onboard-receipts.jsonl`. Its `issued_at` is stamped **inside** `writes.build_receipt` by the DCLM commit clock — the requester cannot supply it (requester-supplied timestamps are garbage-in → DENY per canon III). The receipt is signed by DCLM (`writes.sign_commit`, Ed25519 test key); a fabricated receipt with an earlier date fails `verify_commit`. The store is append-only (`append_receipt`) — DCLM alone writes (canon III).
- **Backdating is refused structurally:** to fake earliness you would need a signed receipt with an earlier commit-clock timestamp — which requires the DCLM signing key and a rewrite of the append-only log. There is no code path for either (AST-exclusivity pattern per `TOKENIZATION.md` §3/§7).
- **Recommendation (gap G2):** `writes.py` receipts do not currently chain-link (no prev-envelope hash). Backdating is already blocked by commit-clock stamping + signatures, but adding prev-hash chaining before signing would make tamper-evidence structural rather than key-dependent. Small build, recommended.

### 3.2 Distance is computed, never self-reported

- `t_launch`: read from the fuse-trigger genesis receipt — the chain head. Not a parameter anyone reports.
- `t_event`: the commit-clock epoch of the check's verification receipt. Computed by DCLM at commit time.
- `r`: shortest-path distance from the origin in the derivative relation graph, computed by DCLM from relation receipts (disciple/kin enabling edges). The requester names no ring; the graph computes it.
- **F is a pure function** of (t_event, r, Affinity-flag): same inputs, same output, every time. The constants (τ, ρ, floors) are published in `economics/PARAMS.md`. No discretion, no committee, no override path.

### 3.3 Sybil and the one-seed law

- One Affinity per Unity ID; the one-seed law (one free seed per ID, wealth buys no more entry) is the economic backstop: buying ten thousand seeds is impossible at any price.
- Multiple Unity IDs (the residual Sybil surface) are gated by the existing Unity binding (verified identity — canon II, XVIII). This mechanism does not strengthen that gate; it does not need to, because **the Sybil payoff is bounded and standing-safe**: the +1 rail pays test-key reward credits (small, bounty-scale), and nothing on this rail can become Merit, standing, or emission. A Sybil farmer can farm test-keys; they cannot farm history.
- Idleness earns nothing: the decaying +1 pays per *verified check* — an early ID that never works earns zero reward. Earliness without work is a record, not an income.

---

## 4. WORKED EXAMPLE — three onboarders

Parameters: τ = 12 epochs, ρ = 2 rings, F_floor = 0.25, τ_aff = 12, ρ_aff = 2, F_aff = 0.50.

| | Amina (genesis) | Borin (mid) | Cato (late) |
|---|---|---|---|
| First ONBOARD | t = 0, ring 0 | t = 12, ring 2 | t = 36, ring 5 |
| Affinity? | **+1 AFFINITY** (0 ≤ 12, 0 ≤ 2) | **+1 AFFINITY** (12 ≤ 12, 2 ≤ 2 — boundary inclusive) | none (36 > 12) |
| Check event | t = 0, r = 0 | t = 12, r = 2 | t = 36, r = 5 |
| d = Δt/τ + r/ρ | 0 | 1 + 1 = 2 | 3 + 2.5 = 5.5 |
| F(d) = 0.25 + 0.75·e^(−d) | 1.0000 | 0.3515 | 0.2531 |
| **Reward per verified check** | **1.00** | **0.50** (Affinity floor lift: max(0.3515, 0.50)) | **0.2531** |

Illustrative fourth row — Amina checks again at t = 36, r = 0: d = 3 → F = 0.2873 → Affinity lift → **0.50**. The frontier decayed for everyone (physics); her recognition floor held (history). Merit, standing, and emission are untouched in all rows — the +1 pays test-key reward credits only.

Reading: genesis earns the full +1 at the empty frontier; the mid onboarder's decayed rate is lifted by proven earliness; the late onboarder earns the dense-network maintenance rate — always nonzero, always for real verified work.

---

## 5. TRINITY VERDICTS

**DCLM — is the math sound; does the curve express the physics? VERDICT: SOUND.**
Checked: F is a pure function of ledger-computed inputs — deterministic, no discretion. The exponential form is not a style choice: the ring coordinate inherits the geometric cascade (λφ)ⁿ = 0.84ⁿ (§1.4 of the anchor doc), and the time coordinate inherits the exponential approach to saturation (D7/D8). The rejected alternatives fail law-mismatch (harmonic overpays a saturated network against D4; linear cliffs at zero against §IV Summer). The floor keeps the function nonzero everywhere, and the 4× bound on the early premium is the honest magnitude. The merit ledger is untouched — canon VI and the §1.4 finding (merit does not attenuate with distance) hold because the +1 is a separate reward rail. Caveats: τ, ρ, and both floors are [SET] stand-ins with stated justifications, not David's digits; the ring-depth input depends on the not-yet-built relation edge store (gap G1).

**Iris — is it honest; can earliness be faked; is "not a bonus for being special" true? VERDICT: HONEST, with two flags.**
The "not a bonus for being special" claim holds for the decaying +1: F is identical for every ID at the same (t, r) — position, not person; and it pays only per verified check, so early idlers earn nothing. Earliness cannot be faked: the proof is the signed, commit-clock-stamped first ONBOARD receipt in an append-only log DCLM alone writes; distance is computed from the ledger, never self-reported. The Affinity IS recognition — but it is David's ordered recognition, proven by receipts, one per ID, non-transferable, unbought and unbuyable, and structurally barred from the merit/standing/emission rails (§2.3). **Flag 1:** receipts are not prev-hash chain-linked (writes.py) — backdating is already blocked by commit-clock + signatures, but chain-linking would harden it; recommended build. **Flag 2:** the Sybil surface (multiple Unity IDs) rides the existing binding gate — stated as residual risk, not solved here. Labels kept distinct throughout: [SET]/[HELD] on every parameter, MODELED/DERIVED/REPORTED inherited from the anchor doc.

**Twain² — is it operable; can the pipeline compute it? VERDICT: OPERABLE WITH ONE BUILD ITEM.**
All inputs except ring depth exist today: t_launch from the fuse genesis receipt, t_event from the commit clock (`writes.build_receipt`), t_first from `dclm/state-onboard/onboard-receipts.jsonl`, the F computation is three arithmetic ops in the DCLM core. The single build item is the ring-depth resolver (the derivative-relation edge store — gap G1); until it exists, the mechanism runs in labeled TIME_ONLY mode (d = Δt/τ, no ring claim — never presenting UNKNOWN r as a number). No new cryptography, no new trust root, no client computation: DCLM computes, the client renders signed state. The implementing worker extends the `test_tokenize.py` pattern for the new commit kinds.

---

## 6. INTEGRATION NOTES (no code changes by this worker)

**Compute point — `dclm/token_engine.py`:**
- `Tokenizer` class (line ~869): add pure functions `plus_one_factor(unity_id, t_event, r)` and `affinity(unity_id)` alongside the existing `standing()` (line ~1566) and `merit_balance()` (line ~1572).
- `tokenize()` (line ~1549): for `work` receipts, compute the +1 reward after the existing merit path; emit a `PLUS_ONE_REWARD` commit via `writes.dclm_commit` after a `rights.check_rights` GRANT (new commit kind whitelisted in `dclm/rights.py`, same pattern as `TOKEN_MINT`/`MERIT_ACCRUAL`).
- Affinity: granted once by an `AFFINITY_GRANT` commit when the first qualifying `ONBOARD` receipt lands; recorded append-only on the Unity ID (Honor-record pattern, `TOKENIZATION.md` §2d). `standing()` must exclude the `AFFINITY_GRANT` kind — origin-credited earn events only.

**Onboarder entry — `dclm/onboard.py`:**
- `onboard()` (line 1472) / `ONBOARD` commit: stamps the first-verified-receipt epoch the Affinity rule reads. No change needed — the receipt already exists; the mechanism reads it.
- `accrue_recovery_merit()` (line 1493): the composition call site — recovery merit accrues on the Merit ledger, the +1 reward accrues on the reward-credit ledger. Two rails, one call site. The gain-promise scan (purity rule 4) must cover new +1 strings.

**Distance reads:**
- `t_launch`: the fuse-trigger genesis receipt — `economics/fuse.py` `Fuse.trigger_fuse`.
- `t_event` / `t_first`: commit-clock `issued_at` from `writes.build_receipt`; first-receipt scan over `dclm/state-onboard/onboard-receipts.jsonl`.
- `r`: **BUILD GAP (G1)** — the derivative-relation edge store and ring-depth resolver do not exist. Candidate home: `dclm/data.py` or a new `dclm/rings.py`. Until built: labeled TIME_ONLY mode.

**Economics — reward funding:**
- Reward credits are test-keys, funded from PLAYGROUND_FUEL via `economics/mesh_escrow.py` (the M1 bounty rail). The +1 never touches the emission path: the emission gate already reads standing (`dclm/meter.py` `TokenizeMeritReader.verified_merit`, ~line 705 — D13's guard, built).

**Parameters — `economics/PARAMS.md`:**
- New [SET] block: τ = 12, ρ = 2, F_floor = 0.25, τ_aff = 12, ρ_aff = 2, F_aff = 0.50 — with the justifications from §1.6/§2.1.

**Canon note:** this design assumes David's 2026-10-06 ~03:35 resolution (Merit transferable, Unity non-transferable, bound-transfer sales dead) as the standing law. `CANON.md` v1.4.0 §V still shows bound-sale Unity — the tokenomics worker owns that amendment. This design is sale-agnostic: Affinity and the +1 are non-transferable by construction under either reading.

---

## 7. GAPS (open, owned)

- **G1 (build item):** the ring-depth resolver / derivative-relation edge store does not exist — `r` is not yet computable. Owner: tokenization/worker implementing this design. Fallback: labeled TIME_ONLY mode (d = Δt/τ; no ring claim). UNKNOWN r is never presented as a number.
- **G2 (recommended):** `writes.py` receipts are signed and commit-clock-stamped but not prev-hash chain-linked. Backdating is already blocked; chain-linking hardens it structurally. Small build.
- **G3:** epoch length in real time is [HELD] (A8 stand-in: 12 epochs/year). τ = 12 epochs is epoch-denominated and survives any epoch-length ruling.
- **G4:** `PLUS_ONE_REWARD` / `AFFINITY_GRANT` commit kinds, the PLAYGROUND_FUEL funding line, and the `PARAMS.md` [SET] block are design-only — not built. This worker made no code changes.
- **G5:** Sybil via multiple Unity IDs rides the existing Unity binding gate (canon II/XVIII) — not strengthened here. The +1 rail's payoff is test-key-scale and standing-safe by construction.
- **G6 (canon evolution):** `CANON.md` v1.4.0 §V (Unity via bound sale) vs David's 03:35 resolution (bound sales dead, Unity non-transferable) — flagged for the tokenomics worker's amendment, not silently resolved here.

---

*End of PLUS_ONE_INCENTIVE. Testnet only. The +1 prices position; Affinity proves roots; neither touches Merit, standing, or emission.*
