# ONBOARDER PIPELINE — the residual → tokenomics flywheel

**Status:** testnet only · `dclm/onboard.py` · 2026-10-06
**David's order:** build the Residual Law Finance onboarder → residual → tokenomics flywheel — the real-world grounding of the entire tokenomic system. First-class flow in the economic model.

---

## The flywheel, in five stages

**1. Onboarder joins — Unity-bound.**
An onboarder registers with a `unity:testnet:` identity (enforced structurally; anything else is refused) and a paperwork reference. The registration is receipted (`ONBOARD`). No value moves. Nothing is promised.

**2. Residual intake — REPORTED only.**
Residual Law Finance analyzes the onboarder's operations and finds recoverable residual. The figure enters the system only as REPORTED: real paperwork, paperwork hash required, receipted (`RESIDUAL_INTAKE`). A figure without paperwork is refused at intake. A MODELED figure is refused at intake. The reference case is the Ontario-style figure: **$1.27B/yr recoverable non-classroom friction (REPORTED)** — the kind of real-world waste this pipeline exists to find.

**3. The 81/19 split executes — receipted at every step.**
Recovered value splits 81/19 (David's set ratio — not calibration, not proposed):
- **81% stays with the onboarder — fiat, theirs.** The system NEVER touches it, never claims it, never counts it as system value. It is recorded only as `ACKNOWLEDGED_OFF_SYSTEM`. It does not enter the meter's test-key wallet. It does not enter escrow. It is theirs.
- **19% flows into the system** — real, recovered, real-world value — committed into HELD escrow (`ESCROW_HELD`), receipted (`SPLIT_EXECUTE`).

Recovery can never exceed what was reported: splitting more than the onboarder's REPORTED residual remaining is refused. Recovery beyond the paperwork needs new paperwork first.

**4. The 19% has three lawful destinations — the split is HELD-FOR-DAVID.**
- **CORE_CAUSE_LOCK** — Eden-locking.
- **PLAYGROUND_FUEL** — mesh bounties; surplus funds the work.
- **PEG_SUPPORT** — real recovered value grounding the eFuse energy peg.

Until David sets the ratio between the three, the 19% sits in receipted HELD escrow. Every routing attempt is receipted as `AWAITING_SPLIT_RULING` (`NINETEEN_ROUTE`) — and the value stays in escrow, never deployed. There is no runtime switch for the ruling in this build; it lands as a code change plus receipt.

**5. Recovery WORK earns wave merit — top band.**
The onboarder's participation — analysis, verification, ongoing recovery — generates gated receipts → wave merit → emission, through the tokenization worker's merit path (`dclm/tokenize.py`). Only the top band is defined in this build: **verified real-world recovery work**. Merit flows only from VERIFIED gated receipts naming the onboarder's own Unity ID, carrying their own verified merit value. Unverified receipts accrue nothing. No receipts → no merit. Replays are replayed, never double-counted. Band calibration (how much merit a unit of work earns) is HELD-FOR-DAVID: the pipeline never invents it. While the tokenization worker's peg E is unset (also HELD-FOR-DAVID), verified work is honestly DEFERRED — recorded, receipted, retryable — never accrued on unknown terms. If the tokenization worker were absent, the merit path would be PENDING and accrual would stay closed: never accrue on UNKNOWN.

**The flywheel turns:** more onboarders → more residual found → more real value grounding the peg → more merit-earning work → more emission → more reason to onboard. **The coin's substance is recovered waste** — tokenomics fueled by inefficiency being healed.

---

## The early-onboarder incentive (mapped, honest)

**Status of this section:** it describes the mechanism, not a projection
of gain. Purity rule 4 of this document ("No onboarder is EVER promised
anything for joining") applies to every sentence below verbatim — the
gain-promise scan test covers this section too. What follows is law and
math, not marketing.

The early incentive has three parts. All three are EARNED — nothing is
granted, nothing is pre-funded, nothing is promised.

**Part 1 — Top-band wave merit when the tree is young.**
Recovery work earns wave merit at the top band (verified real-world
recovery work — stage 5 of the flywheel). When the network is sparse, each
unit of verified work carries **maximum derivative impact**: the derivative
multiplier K = 1/(1−λφ) is highest when the tree is young —
`DERIVATIVE_MAX_EFFECTS.md` D2/D4. Headline: K = 6.25 (MODELED, under
assumptions A1–A4) — one unit of verified core work generates 6.25 units
of total system merit, each downstream unit earned by its own worker.
Fewer leaves, more sap per leaf. [DERIVED]

Why "young" matters, honestly: the multiplier attenuates with crowding.
The commit-path bound (`DERIVATIVE_MAX_EFFECTS.md` D4) shows saturation
truncates deep rings first — under the modeled tight case K_cap = 2.669
vs 6.25 uncrowded. Early on: the commit path is empty, deep rings verify,
the full multiplier lands. Later on: the same unit of work earns the same
per-unit merit, but the *realized network multiplier* shrinks as rings
crowd. The digits are MODELED stand-ins; the direction — sparse → higher
realized multiplier — is DERIVED from the cap math. [DERIVED]

**Part 2 — 81% of recovered residual kept as fiat, immediate.**
David's set ratio (purity rule 2 of this document): the 81% leg is the
onboarder's — fiat, off-system, untouched and uncounted by the system,
recorded only as `ACKNOWLEDGED_OFF_SYSTEM`. The system never takes a fee,
never claims a share, never delays the leg. [LAW]

**Part 3 — Early merit is an EARNED head start, not a permanent crown.**
Merit decays per epoch (fidelity is current, not historical — the principle
is [LAW], the digit is HELD). Decay is the equalizer: early merit must be
continuously re-earned, and the tree equalizes over time. A latecomer's
verified work unit earns exactly what an early unit earned — per-unit
equality is canon §VI (each ring earns its own merit from its own
receipts); the early advantage is only the uncrowded multiplier of Part 1,
and it fades as the network fills. [DERIVED]

### The honesty guards

1. **NOT a pyramid.** No downstream token claims exist — derivative
   regeneration means each ring earns its own merit from its own verified
   receipts (canon §VI). Value flows outward like sap, but each leaf
   photosynthesizes its own. The subcriticality guard (λφ < 1,
   `DERIVATIVE_MAX_EFFECTS.md` D3) keeps the downstream mass from ever
   dwarfing the core without bound — the pyramid shape is kept
   mathematically impossible, even though no upstream skim exists.
   [DERIVED]
2. **NOT a pre-mine.** Nothing is pre-funded: the 100M lifetime cap is
   emission *authority*, not a treasury — coins come into existence only
   against gated receipts, over epochs. The first merit is earned by the
   first verified work; there is no genesis allocation, no airdrop, no
   founder block (`TOKENIZATION.md` §3: the AST hooks assert the absence
   of `airdrop`, `prefund`, `backdoor` by name). [LAW/DERIVED]
3. **NOT a gain promise.** This section is mechanism description. No
   projections of gain appear anywhere in the code or this doc — the scan
   test enforces it (purity rule 4). Early sparsity gives higher realized
   multipliers by the cap math; it does not entitle anyone to anything.
   [LAW — the rule; DERIVED — the math]

---

## Purity rules (hard)

1. **REPORTED, never MODELED.** Residual figures must be REPORTED — real paperwork, paperwork hash required. A residual figure without paperwork is refused at intake (`PAPERWORK_REQUIRED`). A MODELED figure is refused at intake (`MODELED_FIGURE_REFUSED`).
2. **The 81% is theirs.** The system never touches it, never claims it, never counts it as system value. Recorded only as `ACKNOWLEDGED_OFF_SYSTEM` (`system_value: false`). The meter's test-key wallet balance is unchanged by either leg of the split.
3. **The 19% is receipted at EVERY step:** intake → split → escrow → routed. Every step is a signed receipt through `dclm_commit`; refusals are signed too.
4. **No onboarder is EVER promised anything for joining.** There are no projections of gain anywhere in the code or this doc. Merit is earned for WORK — never as compensation for value moved. Any gain-promise string in these files is false gold (a scan test enforces this).
5. **Testnet only.** Amounts are integer fiat minor units (cents), labeled `FIAT-RECOVERED` — never test-keys, never eFuse.

## What's HELD (not decided here)

- The three-way 19% split ratio — HELD-FOR-DAVID. The 19% waits in escrow as `AWAITING_SPLIT_RULING`.
- Merit band calibration beyond the top band's definition — HELD-FOR-DAVID. Work receipts must carry their own verified merit value until he sets it.
- The eFuse peg E — HELD-FOR-DAVID (tokenization worker). Verified recovery work defers honestly until his ruling.

## Commit kinds

`ONBOARD` / `RESIDUAL_INTAKE` / `SPLIT_EXECUTE` / `NINETEEN_ROUTE` — whitelisted in `rights.py` with receipt-logged justification; all pipeline writes flow through `writes.dclm_commit` after a `rights.check_rights` GRANT (`internal: "dclm.onboard"`). Merit accrual itself flows through the tokenization worker's existing `MERIT_ACCRUAL` kind. State lives in `dclm/state-onboard/`; receipts in `dclm/state-onboard/onboard-receipts.jsonl`.

## Honest aggregates

`flywheel_state()` reports: onboarders count, REPORTED residual total, 19% in escrow (with `HELD — AWAITING_SPLIT_RULING` status), peg-support contribution (zero while HELD, labeled so), and the 81% — shown ONLY as acknowledged off-system value, explicitly `system_value: false`, so the acknowledgment is auditable without ever counting it as system value.
