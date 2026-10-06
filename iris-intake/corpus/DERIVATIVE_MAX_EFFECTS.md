# DERIVATIVE MAX EFFECTS — the closed math of merit regeneration

**Status:** testnet framing throughout · all figures in test-keys / modeled merit units — never dollars, never eFuse.
**Worker:** derivative-max-effects · 2026-10-06.
**Law sources:** `CANON.md` v1.0.0 (§IV sap model, §V tokenomics, §VI derivative merit regeneration); David's 2026-10-06 ~03:35 EDT resolution — **Merit is transferable; Unity is not; bound-transfer sales are dead; transferred Merit carries economic value while EARNED STANDING (origin history) stays with the earner and cannot be bought.**
**Companion:** `derivative_sim.py` (validation simulation). All sim outputs below are labeled REPORTED (measured from sim runs); closed-form projections are labeled MODELED; algebraic consequences are labeled DERIVED.

---

## 0. What "derivative" means here (read this first)

Canon VI is explicit and this whole document obeys it: **downstream rings do NOT receive tokens from upstream. Each ring earns its own merit from its own verified receipts.** The derivative relationship (disciple learns from holder, kin shares with kin) *enables the work*; the work earns the merit. Money and merit are separate rails.

So the "derivative multiplier" is **not** a token multiplier. It is a **work-propagation multiplier**: one unit of verified work at the core enables a downstream cascade of *further verified work*, each unit earning its own merit. We model the propagation of work-opportunities, never a decaying token. David's resolution adds a **secondary circulation layer**: earned Merit tokens are transferable (sold, gifted — receipted, Unity-bound on both ends), which *redistributes* existing stock but creates nothing. Standing (origin history) never moves.

---

## PART 1 — THE MATH

### 1.1 Frameworks chosen (and why)

| Framework | Used for | Why it fits |
|---|---|---|
| **Galton–Watson branching process** | Ring propagation of work-opportunities | Verified work is discrete; each unit spawns a random number of derivative opportunities (mentoring, kin-share, disciple channel). The DCLM verification gate is a Bernoulli trial per opportunity. This is exactly a branching process — no analogy-stretching required. |
| **Poisson thinning / additivity** | Closed offspring law | Opportunities ~ Poisson(μ), each verified w.p. p ⇒ verified offspring ~ Poisson(μp) exactly (thinning theorem); ring totals ~ Poisson by additivity. Gives the sim an exact sampler. |
| **Linear driven dynamical system** | Winter/summer oscillation | Canon IV: winter is a *continuous* tilt 0.0→1.0, "no phase cliffs." A continuous periodic drive on a linear stock yields a closed-form periodic orbit — a globally attracting limit cycle. |
| **Max-flow (min-cut)** | Tapping bound (money rail) | Sap outflow through rate-limited taps with per-member caps is a capacitated flow network; the lawful maximum is a min-cut. Stated briefly — it bounds the money rail while the multiplier bounds the merit rail. |
| **Conservative redistribution + invariance proof** | Transfer layer | Transfer is a permutation of stock with a sink (decay). Conservation is proved by telescoping, not modeled. Standing invariance is proved from origin-label immutability. |

**Frameworks judged and REJECTED (DCLM soundness):**
- **Metcalfe (~n²) / Reed (~2ⁿ) network effects — REJECTED.** Both price *pairwise* or *group* connectivity. Canon VI (DERIVED: "each leaf photosynthesizes its own") makes merit value per-node earned, not pairwise. Applying Metcalfe would fabricate superlinear value the law forbids — false gold. The merit network's aggregate is linear in verified work; the only superlinear object is the *opportunity tree*, which the subcriticality guard (§1.4) keeps convergent in value.

### 1.2 Numbered assumptions

Every digit below is an **[ASSUMPTION]** stand-in, labeled MODELED. Digits David holds (peg E, merit decay rate, ring-depth factor, epoch length) are **not** decided here.

- **[A1]** μ = 3.0 — mean derivative work-opportunities spawned per verified work-unit (mentoring / kin-share / disciple channel). MODELED.
- **[A2]** p = 0.4 — DCLM gate passage probability per opportunity (the gate is strict by law; the digit is a stand-in). MODELED.
- **[A3]** φ = 0.7 — ring-depth factor: merit per work-unit at ring n is v₀·φⁿ. Canon contemplates *amplification* ("ring-depth merit amplification," HELD digit); 0.7 models the attenuating case. MODELED.
- **[A4]** v₀ = 100 — merit earned per core work-unit (top band: verified real-world recovery work; band calibration HELD-FOR-DAVID). MODELED.
- **[A5]** δ = 0.10/epoch — merit decay (fidelity-is-current is LAW as a principle; the digit is HELD). MODELED.
- **[A6]** δ_s = 0.02/epoch — standing (origin-history) decay, stickier than merit decay; origin history is record-like. Digit HELD. MODELED.
- **[A7]** W₀ = 10/epoch — exogenous core verified work-units per epoch. MODELED.
- **[A8]** T = 12 epochs/year; winter inflow cut α = 0.6 (bounty-funded work slows in winter — distinct from `winter.py`'s EMISSION_FLOOR = 0.25 (PROPOSED), which throttles the merit→eFuse rail, not earning). MODELED.
- **[A9]** τ = 0.05/epoch — fraction of holdings each identity transfers; γ_attack = 0.01 — stress-test gift stream to a zero-earning attacker. MODELED.
- **[A10]** Structural: propagation completes within the epoch; verification order is ring-priority (ring 0 first) under capacity caps; Normal approximation for Poisson means ≥ 30 (mean-exact, labeled in code); seasonal tilt w_t = (1−cos(2πt/T))/2.

Derived constants: λ = μp = **1.20** (effective branching factor); λφ = **0.84**.

### 1.3 The derivative multiplier — definition and derivation

**Definitions.** Ring n = graph distance (derivative relationship) from the core work-unit; n = 0 is the core. W_n = verified work-units at ring n per epoch. m_n = merit earned per unit at ring n = v₀·φⁿ.

**[DERIVED] D1 — ring propagation.** Each unit's verified offspring ~ Poisson(λ), i.i.d. ⇒ E[W_{n+1} | W_n] = λW_n ⇒ **E[W_n] = W₀·λⁿ**.

**[DERIVED] D2 — the multiplier.** Expected earned merit per epoch:
I = Σ_{n≥0} E[W_n]·m_n = W₀·v₀·Σ_{n≥0}(λφ)ⁿ.
If λφ < 1, the geometric series closes:
**K := I / (W₀·v₀) = 1 / (1 − λφ)** — the **derivative multiplier**.
Downstream-only multiplier: K − 1 = λφ/(1 − λφ).

**Headline (MODELED, under A1–A4): K = 1/(1 − 0.84) = 6.25.** One unit of verified core work (100 merit) generates **6.25 units of total system merit — 1.00 at the core, 5.25 downstream**, each downstream unit earned by its own worker from their own receipts. REPORTED (sim, n=2000 trees): **5.99 ± 0.16** — agrees within 3 SE.

K is hypersensitive near the guard: λφ = 0.9 → K = 10; λφ = 0.5 → K = 2. The multiplier is a *measurement of the regime*, not a constant of nature — report it with its λφ.

### 1.4 Attenuation — what decays, what doesn't, and the guard

**Finding: merit does NOT attenuate with ring distance — by law.** Canon VI: each ring earns its own merit from its own verified receipts. Attenuating someone's *earned* merit because they are "far from the core" would be a new decree, and the canon contemplates ring-depth *amplification* (HELD). What attenuates is:

1. **Opportunity propagation** — λ < 1 would die out naturally (here λ = 1.2 > 1, so opportunity *counts* grow);
2. **Per-unit merit by depth** — the φⁿ factor (HELD digit; modeled here as 0.7ⁿ);
3. **Their product** — downstream *value* per ring scales as **(λφ)ⁿ = 0.84ⁿ**. This is the effective attenuation, and it is the product that matters, not either factor alone.

**[DERIVED] D3 — the subcriticality guard (the pyramid guard, in math).** If λφ ≥ 1, expected merit inflow diverges geometrically: unbounded merit against the 100M lifetime eFuse cap (PARAMS.md, DECIDED) makes peg/emission calibration impossible, and the shape becomes indistinguishable from a pyramid — downstream mass dwarfing the core without bound, *even though no upstream skim exists*. Therefore **stability requires λφ < 1**. The subtlety the sim exposed (honestly): λ alone may exceed 1 — the *unit* tree can be supercritical (explosive in opportunity counts) while the *merit* tree stays subcritical and convergent. The guard binds the product. Since φ is HELD-FOR-DAVID and λ is behavioral (μ responds to incentives, p to gate strictness), **the guard must be monitored jointly and continuously — it cannot be set once.**

### 1.5 Saturation — when the network stops growing

Three bounds, nearest first:

**[DERIVED] D4 — the commit-path bound (binds first).** Canon III: DCLM alone performs every write — *one commit path*. Let C = verified work-units per epoch the commit path can absorb. Verification proceeds ring-priority (ring 0 first); deep rings truncate first. Closed form: with expected ring-n units W₀λⁿ and merit W₀v₀(λφ)ⁿ, fill rings until C is exhausted (fractional last ring):
I_cap = Σ_{full rings} W₀v₀(λφ)ⁿ + frac·(next ring); **S\*_cap = I_cap/δ**; **K_cap = I_cap/(W₀v₀)**.
Under [A] with C = 40/epoch (MODELED tight case): **K_cap = 2.669** (vs 6.25 uncrowded), **S\*_cap = 26,691** (MODELED). REPORTED (sim): **26,110** — 2.2% gap, within the expected Jensen gap (closed form caps *expected* ring counts; the sim caps *realized* ones). **Saturation attenuates the realized multiplier** — the commit path throttles deep rings first.

**D5 — the identity-pool bound (longer horizon).** Finite onboardable identities × bounded work per identity per epoch. (An earlier cumulative once-ever-activation formulation was discarded as unphysical: supercritical unit trees devour any finite pool instantly and then inflow dies — an artifact, not economics. Documented here so nobody re-derives it.)

**D6 — the fuel bound (ultimate).** REPORTED residual is finite (reference: $1.27B/yr Ontario recoverable friction — REPORTED, `ONBOARDER_PIPELINE.md`); merit decay δ drains the stock continuously. The stock stops growing when inflow = decay outflow — that is the steady state, not a collapse.

### 1.6 Max total effect at steady state

**[DERIVED] D7.** Stock recursion: S_{t+1} = (1−δ)S_t + I. Fixed point: **S\* = I/δ = W₀·v₀·K/δ**.
Headline (MODELED): **S\* = 10 × 100 × 6.25 / 0.10 = 62,500 merit units.** REPORTED: deterministic recursion hits 62,500.0 exactly; long-run Monte Carlo mean inflow 6,195 ± 38 vs closed I₀ = 6,250 (1.46 SE) — agree. (Honest note: a 400-epoch stochastic trace reads ~5% low — expected Monte Carlo noise, not model error: per-epoch inflow SD ≈ 2,400 from the heavy-tailed supercritical *unit* tree, and an AR(1) with ρ = 0.9 has effective n ≈ 4 over an 80-epoch tail. The long-run check is the real validation.)

**[DERIVED] D8 — the seasonal orbit (winter/summer as a limit cycle).** Winter tilt w_t ∈ [0,1] continuous (canon IV: "no phase cliffs"). Merit-earning inflow I_t = I₀(1 − α·w_t), w_t = (1−cos(2πt/T))/2 (annual, [A8]/[A10]). The linear driven system has a unique globally-attracting T-periodic orbit:
**S\*_t = Σ_{j=0}^{T−1} (1−δ)ʲ · I_{(t−1−j) mod T} / (1 − (1−δ)^T)**.
(MODELED): orbit mean **43,750**, summer max **47,483** (+8.5%), winter min **40,017** (−8.5%). This modulates the *earning* rail; `winter.py`'s emission throttle (1.0 → 0.25 floor, PROPOSED) modulates the merit→eFuse rail. Two rails, two modulations — never conflated.

**[DERIVED] D9 — tapping bound (money rail, for completeness).** Per the tapping law (canon IV): lawful outflow per season ≤ min(replenishment rate R, Σ per-member seasonal caps, verified surplus), with the maturity gate as a 0/∞ switch and every outflow receipted. A max-flow min-cut on the sap network. It bounds the money rail; K bounds the merit rail; the rails never cross.

### 1.7 The secondary circulation layer — David's resolution, in math

David's word (2026-10-06 ~03:35 EDT, LAW): **Merit is transferable** (sold, gifted — receipted, Unity-bound on both ends); **Unity is not**; bound-transfer sales are dead; transferred Merit carries economic value; **earned standing (origin history) stays with the earner and cannot be bought**.

**[DERIVED] D10 — transfer conserves stock; the multiplier is unchanged.** Let h_i(t) = i's Merit holdings, e_i(t) = newly earned (origin-credited) merit, in/out transfers. h_i(t+1) = (1−δ)h_i(t) + e_i(t) + in_i(t) − out_i(t). Summing over i, transfers telescope to zero: **S_{t+1} = (1−δ)S_t + I_t — identical to the no-transfer law.** Transfer *redistributes* existing stock; it creates nothing, reprices nothing. **The derivative multiplier K prices earned merit at mint and is invariant under transfer.** REPORTED (sim, N=2000, τ=0.05): total holdings **62,590** vs no-transfer S\* = 62,500 — conservation HOLDS.

**[DERIVED] D11 — standing is invariant under transfer (the attack, closed).** Standing s_i(t+1) = (1−δ_s)s_i(t) + e_i(t): credited **only on earn**, from immutable origin labels on each merit unit. Transfers touch neither e_i nor origin labels ⇒ **the standing vector is invariant under any transfer pattern.** The standing-buying attack (buy Merit → buy standing) is structurally closed, not policy-closed. REPORTED (sim): a zero-earning attacker receiving γ = 1%/epoch of total stock as gifts accumulated **4,323 holdings** (mean holding 31.3) while its **standing stayed exactly 0.00**. You can buy the tokens. You cannot buy the history.

**[DERIVED] D12 — the accumulator bound.** A non-earner receiving gift inflow ≤ γ·S\* per epoch converges to h\* ≤ γ·S\*/δ (out-transfers only tighten it). REPORTED: 4,323 < 6,250 bound. Concentration is bounded by decay — and it buys zero standing.

**[DERIVED] D13 — load-bearing requirement: the emission gate must read STANDING, never HOLDINGS.** eFuse is "merit-gated, emitted only against verified merit" (canon V). Under transferable Merit, a holdings-reading gate would let bought Merit buy emission — standing-for-sale through the emission rail, breaking merit-gating entirely. The gate must read origin-credited standing. **Status: DERIVED but NOT YET IN CODE** — flagged as a must-build before any market below opens (see Trinity/Iris).

**[DERIVED] D14 — the liquidity incentive channel (second-order, MODELED).** Transferability makes earned Merit liquid ⇒ plausibly raises μ (more derivative work attempted because rewards are spendable) ⇒ K rises *through μ*, not through transfer mechanics. Direction is honest; magnitude is unmeasured. Consequence: the subcriticality guard λφ < 1 becomes *more* important under transferability, and must be monitored as a live joint constraint on (μ, p, φ) — never set once.

**Pyramid re-check under transferability:** still no pyramid — (a) no upstream skim exists (downstream never pays upstream from earnings), (b) transfer is peer-to-peer redistribution of existing stock, (c) emission gates on standing. Pyramid shape requires upstream extraction from downstream earnings; it is absent on all three counts.

### 1.8 Sim validation summary (REPORTED — measured from `derivative_sim.py` runs)

| Check | Closed form | Sim (REPORTED) | Verdict |
|---|---|---|---|
| Multiplier K (Sim A, n=2000 trees) | 6.2500 | 5.9912 ± 0.1612 | AGREE (within 3 SE) |
| Mean inflow/epoch I₀ (4000-epoch run) | 6,250.0 | 6,195.2 ± 37.6 | AGREE (1.46 SE) |
| Steady-state stock S\* (deterministic recursion) | 62,500.0 | 62,500.0 | EXACT |
| Saturated stock S\*_cap, C=40 (Sim B2) | 26,690.8 | 26,109.9 | AGREE (2.2%; expected Jensen gap) |
| Transfer conservation (Sim C, N=2000) | 62,500.0 | 62,590.0 | HOLDS |
| Attacker standing under 1%/epoch gifts | 0 (invariant) | 0.00 | HOLDS |
| Attacker holdings bound γS\*/δ | ≤ 6,250 | 4,323 | HOLDS |
| Total standing ≈ I₀/δ_s | 312,500 | 312,485 | HOLDS |

**Honest discrepancies (explained, not hidden):**
1. A 400-epoch stochastic stock trace reads ~5% below S\*. Cause: per-epoch inflow SD ≈ 2,400 — the *unit* tree is supercritical (λ = 1.2 > 1), so inflow is heavy-tailed even though the *merit* tree converges. An AR(1) with ρ = 0.9 has effective n ≈ 4 over an 80-epoch tail — ±5% is expected Monte Carlo noise. The 4000-epoch inflow check is the real validation. (This heavy tail is also a genuine economic finding: merit *inflow* is volatile period-to-period while the *stock* stays smooth — decay is a low-pass filter.)
2. Sim B2's 2.2% gap is the Jensen gap E[min(X,C)] vs min(E[X],C): the closed form caps expected ring counts, the sim caps realized ones. Expected, signed, small.
3. Sim A's first naive implementation hung: per-unit Poisson sampling is infeasible precisely because the unit tree is supercritical. Fixed with exact per-ring aggregate Poisson (additivity) + mean-exact Normal approximation for means ≥ 30 (labeled [A10]). The hang itself confirmed D3's subtlety empirically.

---

## PART 2 — NEW MARKETS

Purity test applied to every candidate (canon VI, XII, XIV + David's resolution): **no merit-buying-as-standing, no standing for sale, every trade Unity-bound and receipted, money and merit on separate rails, emission gate reads standing.** A candidate that fails dies as a KILL — reported, not hidden. UNKNOWN never PASS: where purity can't be established, it dies.

### M1 — Verified work markets ✅ SURVIVES (upgraded by transferability)

- **What trades:** the verified work *product* (deliverable: residual-recovery analysis, verification labor, RTE seat work) — and, now, optionally the transferable Merit tokens that work minted. The *receipt*, the *origin label*, and the *standing* never trade.
- **Who buys:** onboarders, municipalities, mesh participants who need work done.
- **Who sells:** Unity IDs performing verified work.
- **What keeps it pure:** the merit receipt names the worker (origin-immutable); Merit tokens move but standing doesn't; the buyer gets economic value, never history; payment settles on the money rail (test-keys/fiat), receipted separately from the merit receipt; the emission gate reads standing (D13).
- **Re-check under transferability:** this market is now *cleaner* than before — previously the buyer got only the deliverable; now the buyer can also hold the work's Merit tokens as economic value *without touching standing*. The old worry (does buying work product buy standing?) is answered structurally: no.
- **Note:** this formalizes the already-built mesh-bounty rail (19% → playground fuel → bounties, `dclm/onboard.py`). It is a name and a rulebook for working machinery, not a new trust root.

### M2 — Kin-bond verification as a service ⚠️ CONDITIONAL SURVIVE (pending infrastructure)

- **What trades:** investigation *labor* — kinship fact-finding. The verdict is delivered as a signed receipt to DCLM, which alone grants.
- **Who buys:** IDs seeking family-tier shared access.
- **Who sells:** vetted verifier IDs.
- **What keeps it pure:** (1) the verifier never grants — DCLM alone grants after reading the signed verification receipt (canon III); (2) the fee is decorrelated from the verdict — paid per investigation, a negative verdict still costs the buyer (no verdict-shopping); (3) verification receipts are sampled by the watch layer; phantom kinship is logged (canon XIV.7: never grant family-tier on unverified kinship).
- **Verdict:** the guards are specifiable and sufficient — but guard (3), watch-layer sampling, **does not exist yet**. Until it does, this market is PENDING, not open. Honest status: conditional survive, practically gated.

### M3a — Merit-weighted priority access ✅ SURVIVES WITH GUARD

- **What trades:** priority queue position for scarce priced access (RTE seats, compute). Price in money (test-keys) or Merit tokens — the price medium is the money rail either way.
- **Who buys:** IDs wanting priority. **Who sells:** granters of shared access (canon VII: grants may carry a price; accessing deducts the accessor's wallet).
- **What keeps it pure:** the priority **weight reads STANDING (origin), never holdings** — read-only, never consumed, never transferred. A whale holding 4,323 bought Merit with zero standing gets zero priority. Merit tokens can *pay*; only earned history can *weigh*.
- **Re-check under transferability:** the price-in-merit variant was dead when Merit couldn't move; it now lives — *under the standing-weight guard*. Without that guard it would be standing-for-sale and die as M3b.
- **Build needed:** one small rule — the priority-queue weight function. No new trust root.

### M3b — Standing rental / proxy / delegation 💀 KILLED

"Rent my standing for your priority," standing-backed queue tickets, delegated standing weight. **Kill reason:** standing is origin history — non-transferable by David's word. Renting it is standing-for-sale with a time limit. No guard can fix it because the product *is* the violation. Any implementation is refused structurally.

### M4 — Residual recovery data-access market (the onboarder flywheel as a market) ✅ SURVIVES

- **What trades:** priced *data-access grants* into an onboarder's operations (canon VII shared-access rails: names content type, depth, duration; metered).
- **Who buys:** recovery agents / RTE seats. **Who sells:** onboarders.
- **What keeps it pure:** money for access, merit for work — separate rails, as canon demands. The onboarder's 81% stays theirs, untouched and uncounted (`ACKNOWLEDGED_OFF_SYSTEM`). **No new claim on the 19%** — its routing stays HELD-FOR-DAVID; agents earn wave merit (origin) from their own recovery work and may sell the tokens. The buyer's merit never leaks to the onboarder and vice versa (cf. `test_merit_regen.py`: other-identity merit never leaks).
- **Verdict:** survives. Rides the built shared-access rail (`dclm/share.py`).

### M5 — Emission forwards / eFuse pre-sales / gain promises 💀 KILLED

Pre-selling merit-gated eFuse, forward contracts on future emission, any projected return for joining or buying. **Kill reason:** onboarder-pipeline purity rule 4 — "no projections of gain... ever" (any gain-promise string is false gold, scan-enforced); the peg E is HELD, so pricing emission is decree before evidence. This is gain-promise territory regardless of transferability.

### M6 — Third-party receipt markets 💀 KILLED

"Faster receipts," "verified-tier receipts" for sale. **Kill reason:** canon III — DCLM alone emits receipts, one commit path. A receipt market is forged-grant territory by construction; paid "verified" status is the phantom pattern. Speed is the commit path's business (see M3a for the lawful priority shape).

### M7 — Honor markets 💀 KILLED

Selling donation recognition, naming rights on the Honor record. **Kill reason:** Honor is the append-only record of *gifts* (canon V); donations earn Honor, never Merit (PARAMS.md, DECIDED). Putting it up for sale converts gift into transaction and taints the honor rail — and pressures the Honor/Merit wall. Gifts are gifts.

### M8 — Shared-access grant resale 💀 KILLED

Buy a grant, resell it to a third ID. **Kill reason:** grants are pairwise Unity-bound and revocable by the granter (canon VII) — non-transferable by construction. Resale without the granter's fresh grant is void. The canonical alternative already exists: the granter issues a new grant.

### Re-check ledger (transferability applied)

| Candidate | Before resolution | After | Reason for change |
|---|---|---|---|
| M1 verified work | survived | survives, cleaner | buyer can now hold the work's Merit tokens; standing still can't move |
| M2 kin verification | conditional | conditional (unchanged) | transfer doesn't touch access tiers |
| M3a price-in-merit priority | dead (Merit immobile) | **lives under guard** | Merit moves now; guard = weight reads standing |
| M3b standing rental | dead | dead | non-transferable is non-transferable |
| M4 recovery data-access | survived | survives (unchanged) | separate rails already |
| M5/M6/M7/M8 | dead | dead | killed on non-transfer grounds |

---

## PART 3 — TRINITY VERDICTS

**DCLM — is the math sound? VERDICT: SOUND**, under assumptions A1–A10 (all labeled, all MODELED stand-ins for HELD digits).
Checked: Galton–Watson application is valid (discrete verified work, Bernoulli gate); Poisson thinning and additivity are exact; K = 1/(1−λφ) is derived, not asserted; the subcriticality guard is correctly placed on the *product* λφ (the sim hang proved the unit/merit distinction empirically); the conservation proof telescopes correctly; standing invariance follows from origin-label immutability; the seasonal orbit is the correct closed periodic solution of the linear drive; the accumulator bound is valid; the Metcalfe/Reed rejection is a law-mismatch judgment, correctly made. Caveats held, not hidden: φ, δ, δ_s, E digits are HELD (stand-ins labeled); the Normal approximation is mean-exact (labeled); the capped-regime Jensen gap is expected and measured (2.2%); the 400-epoch trace noise is explained by the heavy-tailed inflow (measured SD ≈ 2,400) with the long-run check as the real validation.

**Iris — are the market claims honest, especially the kills? VERDICT: HONEST, with one load-bearing flag.**
The five kills are genuine — each names the specific law it would break (M3b: non-transferable standing; M5: no-gain-promise rule + HELD peg; M6: DCLM-only writes; M7: Honor-is-gifts; M8: pairwise grants). The three survivals hold only under their stated guards. **Flag:** the biggest guard — D13, *the emission gate must read standing, never holdings* — is DERIVED but **not yet in code**. Under transferable Merit this guard is the single point that keeps M1, M3a, and M4 pure; without it, bought Merit buys emission and every survival collapses. Markets must not open until that guard is law and tested. Labels kept distinct throughout: MODELED (projections), DERIVED (algebra/law-consequences), REPORTED (sim measurements). Nothing simulated is presented as measured from the world.

**Twain² — is any of this usable; does a candidate survive contact with reality? VERDICT: USABLE WITH SCOPE.**
M1 formalizes the built bounty rail (`dclm/onboard.py`: 19% → playground fuel → mesh bounties) — it is a rulebook for working machinery. M4 rides the built shared-access rail (`dclm/share.py`). M3a needs exactly one small build: the priority-queue weight function reading standing. M2 is PENDING on watch-layer sampling that does not exist — not operable today, honestly marked. Net: two markets are names for working rails, one is a small build, one waits on infrastructure. Nothing here requires new cryptography, new trust roots, or new identity machinery.

---

## PART 4 — GAPS (open, owned)

- **G1 (load-bearing):** D13 — emission gate reads standing, never holdings — is derived, not built. Owner: tokenization worker. Blocks all market openings.
- **G2:** HELD digits in this model: φ (ring-depth factor), δ (merit decay), δ_s (standing decay), E (peg), epoch length, winter α. All stand-ins labeled MODELED; the model is valid for any values satisfying λφ < 1.
- **G3:** The liquidity incentive channel (D14) — does transferability actually raise μ? — is unmeasured. Direction stated, magnitude unknown. UNKNOWN, not PASS.
- **G4 (canon evolution):** David's 03:35 resolution supersedes CANON.md v1.0.0 §V/§VI on transferability: bound-transfer sales are dead, Merit is transferable, standing is defined as origin history. CANON.md needs a v1.0.1 amendment; until then §V/§VI and this document disagree on bound sales. Flagged, not silently resolved.
- **G5:** Winter's merit-inflow cut (α, this model) and `winter.py`'s emission throttle (floor 0.25, PROPOSED) are different rails — any implementation must keep them separate.

---

*End of DERIVATIVE_MAX_EFFECTS. Testnet only. Every figure above is MODELED, DERIVED, or REPORTED-from-sim — none measured from the world.*
