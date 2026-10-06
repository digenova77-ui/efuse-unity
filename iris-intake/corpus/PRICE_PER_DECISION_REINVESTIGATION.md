# PRICE-PER-DECISION REINVESTIGATION

**Worker:** pricing reinvestigation · 2026-10-06 ~04:00 EDT
**Order:** David — go back to the price-per-decision model and re-examine it FROM SCRATCH. Don't defend the old model.
**Framing:** testnet only. Every figure below carries its label: REPORTED / MODELED / DERIVED per canon, plus [SET]/[HELD]/[PROPOSED] where I take a position vs. where David must.
**Verdict up front:** the old model was wrong — not slightly. The "price" of each decision was the reported cost surface the decision touches, denominated in USD, billed at company scale. That is a dimensional error: it prices the object being measured, not the act of deciding. It is re-derived below. **Net effect of the re-derivation: decision charges move DOWN — from USD-billion-scale surface figures to a flat 5 test-keys per decision** (the canon meter's COMPUTE price, SET in `dclm/meter.py`).

---

## 1. WHAT WAS WRONG — 11 flaws, each with the assumption that failed

**F1. The price is the cost surface — a dimensional error.** `pricing.py::price_decision` sets `billable_amount_m` = the row's PRIMARY figure (e.g., Amazon's decision "costs" $637,959M = its entire FY net sales; Tyson's "costs" $8,830M = its gross debt). The decision being priced is the verdict — the collapse of possibility into a judgment. The engine bills the object the verdict was *about*. That is like charging the map's reader the GDP of the mapped country.
*Failed assumption:* "the price of each decision is the REPORTED cost surface it touches" (`pricing.py` module docstring).

**F2. Wrong denomination: USD instead of test-keys.** `CURRENCY_DEFAULT = "USD"`. Canon XI: "Test units only — never dollars, never eFuse." The USD figures from SEC filings are fine *as labeled surface figures* (REPORTED). They are not a price currency. The engine collapses "the figure's unit" and "the price's unit" into one field.
*Failed assumption:* "prices live in USD because the figures do."

**F3. Two meters, disagreeing.** `dclm/meter.py` already owns billing: SEARCH = 1, COMPUTE = 5 test-keys (SET, canon XIII). `economics/pricing.py` built a second meter with its own `billable_amount_m` in USD. The canon gives the meter to one owner (`dclm/rights.py`: "the meter owns pricing and balances").
*Failed assumption:* "the economics dir can own its own meter."

**F4. The false price is load-bearing.** `economics/economic_state.py::_meter_price_entry` fuses `billable_amount_m` into the **signed** EconomicState with `pays=true` whenever provenance is REPORTED — which is nearly every factory row. The mislabeled surface figure would actually authorize payment inside signed state. This is not a paperwork problem; it is a live billing bug.
*Failed assumption:* "a REPORTED surface figure is a payable price."

**F5. The billable amount wears a label nobody earned.** `label=REPORTED` on `billable_amount_m` implies someone reported that figure *as a price*. Nobody did — Amazon never said its shipping-density decision costs $637.959B. Custody of the figure was inherited as custody of the price. That is modeled-as-reported false gold (the thing canon XIV.8 exists to kill).
*Failed assumption:* "custody of the figure = custody of the price."

**F6. De-facto tiers by company size.** The engine claims "no tiers, ever." But the same atomic decision (one verdict, one collapse) is billed $637,959M for Amazon and $8,830M for Tyson — a 72× spread driven purely by company size. A price schedule that scales with the target's revenue is a tier table with extra steps.
*Failed assumption:* "no tier table = no tiers." Size-scaled prices ARE tiers by another name.

**F7. Surface double-counting; primary-figure choice is unlabeled analyst discretion.** Rows list overlapping figures (Uber: gross bookings 2024 AND 2025; AbbVie: FY2024 AND FY2025 revenues plus SG&A plus R&D). Which one is "primary" (and therefore billable) is the index compiler's choice — a DERIVED judgment wearing no label. Under the old model this choice *set the price*; under the new model it only orders a label list, which defuses it.
*Failed assumption:* "the primary figure is a property of the sealed paper." It is a property of the index compiler.

**F8. rte-health unit error.** QHC/KHSC cost-per-ED-visit stored as `amount_m: 0.000215` with `unit: "USD"` — the `amount_m` key means millions, the value means dollars. A $0.22-per-visit read is a $0.000215M-per-visit write. Cosmetic, but a price engine cannot have unit confusion.
*Failed assumption:* "the `amount_m` key holds whatever the source's unit was."

**F9. Stale index count.** Footer: "51 decisions indexed" while the index holds 53 rows (33 + 2 RTE + 16 claims + #101 + #102). The addendum grew; the receipt line didn't.
*Failed assumption:* "the footer was re-checked when rows 101/102 were appended."

**F10. Tonight's incentive changes are unaccounted.** The engine predates David's resolutions and says nothing about them: (a) transferable Merit — can a decision price be paid in Merit? (b) +1 deterioration — do early decisions cost less? (c) one seed — does the seed buy free decisions? (d) the D13 guard — does pricing touch emission eligibility? Unanswered = unpriced risk.
*Failed assumption:* "the price model is complete without the incentive layer." It was built before the incentive layer existed.

**F11. The friction mission is unaddressed.** The model *measures* friction (quotes the surface) and calls the quote a price. Nothing in it pushes friction toward zero. A price that only measures friction is an observation, not a weapon — and David's mission needs a weapon.
*Failed assumption:* "pricing the surface targets the friction."

---

## 2. RE-DERIVED PRICING RULES

What a "decision" is, priced from first principles. Canon I: Parliament is the collapse operator — possibility becomes decision. The priced act is the **verdict-producing COMPUTE** (the collapse), not the surface the verdict was about, not the receipt that records it, not the data it read. From that:

- **[DERIVED] R1 — the priced unit is the verdict-producing compute.** One decision = one collapse = one COMPUTE intent. The surface figures (SEC filings, Drive figures) are labeled reference attached to the row; they are never a charge.
- **[DERIVED from canon XI] R2 — denomination is test-keys only.** USD figures remain as REPORTED labels. Nothing in the price book is denominated in dollars — ever.
- **[SET, canon XIII + `dclm/meter.py`] R3 — one flat rate: COMPUTE = 5 test-keys per decision.** No size scaling (kills F6), no distance scaling, no earliness scaling. No tiers, ever — this time for real.
- **[DERIVED] R4 — surface figures are labels, billable 0.** They stay in the index (they are the honest WHERE-the-money-is map from PRICES.md). Their `billable` contribution is 0; their provenance labels are preserved per figure.
- **[DERIVED from tonight's resolutions] R5 — payment rails.** A decision price may be paid in test-keys or in transferable Merit (Merit is economic value on the money rail — lawful per M1/M3a, DERIVATIVE_MAX_EFFECTS.md). Paying never accrues standing (standing = origin-credited earn events only, D11 — payment is not work). Paying never touches emission eligibility (the D13 guard: the emission gate reads standing, never holdings — decision pricing is money-rail, emission is standing-rail, they do not meet).
- **[DERIVED from §XX] R6 — the seed buys no decisions.** "The seed opens the door; nothing more." It grants the Unity-bound wallet (membership), not purchasing power. First decisions are not free by seed right.
- **[DERIVED from PLUS_ONE_INCENTIVE.md §1.4] R7 — price never deteriorates with distance.** The +1 deterioration prices the *reward* for marginal system impact — reward-side physics. The *price* of running the same compute is the same at the frontier and at saturation. Charging latecomers more would tax the future and contradict canon IV Summer (every leaf fed). Physics decays the reward; the price stays flat.
- **[PROPOSED — HELD for David] R8 — the friction-kill price (see §4).** Verified recovery checks earn their reward *and* get their compute rebated from the bounty rail, making the effective price of killing friction ≤ 0. This spends the fuel rail, so it waits on David's word.

---

## 3. THE NEW PRICES

Per decision class (per the brief: "no change" allowed with justification per class — here every class changes except claims' dollar price, which stays N/A).

| Decision class | Old "price" | New price | Reason |
|---|---|---|---|
| Factory verdicts #1–33 | Primary REPORTED surface figure, USD millions (range: $8,830M Tyson → **$637,959M Amazon**) | **5 test-keys flat** (canon meter COMPUTE) | F1/F2/F6: the surface is the object measured, not the act; USD violates canon XI; size-scaling is de-facto tiering |
| Factory #101 (Uber) | $162,773M (REPORTED-via-mirror) | **5 test-keys flat** | Same as above |
| Factory #102 (MassMutual) | $21,288M (REPORTED-via-mirror) | **5 test-keys flat** | Same as above |
| RTE-EDU (Ontario friction) | $1,273.5M recoverable friction as the "price" | **5 test-keys flat**; the $1,273.5M stays as a REPORTED **friction-target ledger** figure (what the recovery decision hunts), billable 0 | F1: billing someone $1.27B to *learn about* friction is absurd; the figure's lawful role is target, not toll |
| RTE-HEALTH (QHC vs KHSC) | $348.5M (QHC revenue) as the "price" | **5 test-keys flat**; figures stay as REPORTED labels; F8 unit error corrected (cost/visit in USD dollars, not amount_m) | F1/F8 |
| Claims C1–R4 (16 adjudications) | $0 / N/A — "the verdict is the price" | **No change on the dollar price: the verdict remains the price, dollar cost N/A.** Metered compute 5 test-keys *only when requested through the wallet surface*; whether internal Trinity governance commits are metered at all is **[HELD]** (canon III: DCLM performs the writes — that cost may be the system's own, not the requester's) | The old model was accidentally right here: a judgment has no dollar cost. Only the metering of the compute around it needed a rule |

**Single biggest pricing error found:** factory-2 (Amazon), outbound-shipping-density decision — billed **$637,959M ($637.959B, REPORTED)**, i.e., Amazon's entire FY net sales, as the price of one verdict about trailer cube utilization. Runner-up: factory-14 (Fannie Mae) at $534,700M. The honest price of both decisions: 5 test-keys.

**Net direction: DOWN.** Every decision class's charge falls from USD-million/billion-scale surface figures to a flat 5 test-keys. (The surface figures themselves are not "prices," so nothing is lost — they remain, labeled, billable 0.)

---

## 4. THE FRICTION TARGET — MEASURE vs KILL

**Verdict on the old model: it only MEASURES.** It quotes the surface where friction lives and calls the quote a price. A meter reading is not a weapon. Nothing in the old model makes friction cheaper to kill than to keep.

**What makes pricing a friction-killing mechanism.** The re-derived model separates the two jobs David's mission needs:

1. **Measuring friction must be nearly free.** LOOK is already free (canon VIII). The COMPUTE that maps a residual surface costs a flat 5 test-keys — deliberately cheap, deliberately identical for a school board and a Fortune 50. *Rule:* the price of finding friction never scales with the friction found (that would price discovery out of reach for the biggest targets — the opposite of the mission).

2. **Killing friction must pay.** The reward side already exists: verified recovery work earns Merit (origin-credited, canon VI) and the +1 reward (deteriorating with distance, reward-side physics). The missing piece is the price-side complement: **[PROPOSED, HELD]** a verified recovery check's 5 test-keys are **rebated from the PLAYGROUND_FUEL bounty rail** — so the effective price of a decision that *eliminates* verified friction is ≤ 0 (you earn for it). Measuring costs 5; killing earns. That asymmetry IS the weapon: the price book leans against friction's existence.
   - *Why the rebate waits on David:* it spends the bounty rail, whose routing is HELD-FOR-DAVID (cf. M4 verdict). I do not invent spending.
   - *Why it doesn't break the D13 guard:* the rebate is test-keys from the fuel rail, not Merit; it cannot become standing (D11) and cannot gate emission (D13).

3. **The end-state the prices point at.** The meter keeps a friction-kill ledger per seat/ID: cumulative verified friction eliminated (REPORTED figures, e.g., the $1,273.5M Ontario surface). David's mission — "stop all global destruction by targeting 100 friction first" — reads as the target: **all friction, first priority**. The price book is complete when the ledger reads zero: at zero friction there is nothing left to measure expensively and nothing left to reward for killing — the flat 5 test-keys becomes the whole book. **Proof the old model was inverted:** under the old model, zero friction would mean zero price — the price of a solved world would be nothing. Under the new model, the price was never *about* the friction; the friction was the target, and the target is being hunted to zero.

**Which prices change, by what rule, toward what end-state — concretely:**
- All 53 rows: surface → labels, billable 0 (done above, §3).
- New meter line per decision: 5 test-keys, flat (SET).
- PROPOSED: `friction_kill_rebate` — verified recovery COMPUTE refunded from PLAYGROUND_FUEL (HELD: needs David's word on the spend).
- New ledger line: per-seat cumulative verified friction eliminated (REPORTED), target = 100% of identified friction.
- End-state: friction ledger → 0; price book = flat 5 test-keys; mission complete on the pricing axis.

---

## 5. TRINITY VERDICTS

**DCLM — is the math sound? VERDICT: the old math is UNSOUND as a billing surface; the re-derivation is SOUND.**
Checked on the old model: F1 is a dimensional error (price in units of the measured object); F2 violates the canon's unit law; F6 reconstructs tiers the engine claims to forbid; F4 propagates the error into signed state via `economic_state.py`. The labeling/custody machinery underneath (the five-label normalization, the UNKNOWN-never-PASS handling) is sound — the error is in what the engine *does* with the labels, not in the labels. The new model introduces no new math: it points at the existing canon meter (SEARCH=1, COMPUTE=5, SET) and retires the duplicate. Caveats: the rebate (R8) is PROPOSED/HELD, not derived; the flat rate inherits the meter's SET constants, which are David-changeable by one constant.

**Iris — are the prices honest? VERDICT: the old price construct was DISHONEST in effect; the custody labeling was HONEST; the new model is HONEST with the rebate correctly marked.**
The custody work in PRICES.md and pricing.py (REAL/REPORTED/REPORTED-via-secondary/MODELED-DERIVED → five DCLM labels, per-figure custody preserved) is genuinely honest — nothing inflated there. The dishonesty was structural: `billable_amount_m` wearing `label=REPORTED` when no one ever reported a price (F5), and the "51 decisions indexed" footer (F9). The new model keeps every REPORTED/MODELED/DERIVED label on the figures and puts the price where a price belongs: the meter, in test-keys, labeled SET. **Flag:** if the rebate is ever built, its funding source must be labeled on every receipt (PLAYGROUND_FUEL, test-keys) — a rebate that silently mints is gain-promise territory (M5's kill reason).

**Twain² — do the prices work for humans? VERDICT: the old model was UNUSABLE; the new model is USABLE.**
No real onboarder would — or could — accept a bill of $637.959B for a verdict, or understand why their decision costs Amazon's net sales. It reads as either a bug or a shakedown; either way they walk. The new model's pitch is one sentence a human can hold: *"Every decision costs 5 test-keys. The big numbers attached are reported facts about the world — where the money is — not your bill."* The flat rate is explainable, the surface figures are legible as context, and the friction-kill asymmetry (measuring is cheap, killing pays) is the kind of deal a real person signs. Known limit: the rebate is PROPOSED — the pitch must not promise it until David rules.

---

## 6. GAPS — open, owned

- **G1 [HELD — David]:** the friction-kill rebate (R8). Approve the PLAYGROUND_FUEL spend, or kill it. Until ruled: measuring = 5 test-keys, killing = reward rail only.
- **G2 [HELD — David]:** are internal Trinity claim-adjudication commits metered at all, or is DCLM's own governance cost the system's (canon III)? Claims rows carry no wallet charge until ruled.
- **G3 (build item):** `pricing.py` still computes USD `billable_amount_m`, and `economic_state.py` still fuses it with `pays=true`. This worker re-derived; it did not rewrite. The implementation — retire the USD billable, point the meter at `dclm/meter.py`, correct the F8 unit error, fix the F9 footer — is owned by the pricing/economics worker. **Until it lands, F4 is live.**
- **G4 (canon evolution, pre-existing):** CANON.md v1.5.0 §V/§VI still say Merit is non-transferable and Unity transfers via bound sale — superseded by David's 03:35 resolution (Merit transferable, Unity non-transferable, bound sales dead). R5 is written against David's LAW, not the stale canon text. The tokenomics worker owns the amendment.
- **G5 (index completeness):** sealed factory verdicts #34–#100 (57 papers on disk per PRICES.md gap 1) are not in the index. Under the new model they enter as labels-only rows (billable 0, price 5 test-keys) — the extension is paperwork, not pricing.
- **G6:** tonight's +1 Affinity interacts with the reward rail only (PLUS_ONE_INCENTIVE.md §2.2) — confirmed no pricing interaction beyond R7. No gap, recorded so nobody re-derives it.

---

*End of reinvestigation. Testnet only. Nothing invented: every figure above is REPORTED, MODELED, or DERIVED from the cited sources; every proposal I could not derive is marked [HELD]/[PROPOSED]. The old model measured; the new model is built to kill.*
