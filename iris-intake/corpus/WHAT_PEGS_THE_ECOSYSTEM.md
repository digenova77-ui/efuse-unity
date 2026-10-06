# WHAT PEGS THE ECOSYSTEM — the DCLM-held complete specification

**Status:** builder-only 2D document. Held by DCLM. **It never goes on the website — no 2D version of this explainer ships on the site, ever** (standing prohibition, §7).
**Framing:** testnet. `dualis.relay.v1.testnet`. No production keys, schemas, or state.
**Labels:** every substantive claim carries [LAW] (David's word), [DERIVED] (logical consequence), [HELD] (awaiting David's word), or [LAW-DECLARED] (David's word spoken but not yet sealed into canon — law-declared, pending amendment/code).
**Figures:** every figure carries a provenance label — REAL / REPORTED / MODELED / DERIVED / UNKNOWN. UNKNOWN never pays, never scores, never emits.

This document is the data UNDERNEATH the Rosetta Stone artifact (`ROSETTA_STONE_SPEC.md`). The stone expresses it in 3D form; this document states it in 2D words, for builders only.

---

## 1. THE PEG — eFuse pegged to real-world energy

### What it is

[LAW] **eFuse is the emission token. Merit-gated, peg-calibrated via 1/E.** (Canon §V.)

[LAW-DECLARED] eFuse pegs to real-world energy: "efuse moves to peg real world energy. it's never sold except to regulate that internal." (David, Oct 4, 2026.) The token means energy — the peg is definitional: 1 eFuse ≡ E energy units, and the definition holds it, not a market.

[DERIVED] The emission formula is peg-calibration made mechanical: **eFuse_i = merit_i / E** — each member's emission is their verified merit divided by the peg ratio. (economics/tokenomics.py `emission_calculator`; canon peg-calibration "via 1/E".)

[HELD] **The peg ratio E is HELD-FOR-DAVID.** Calibration pending. The pipeline REFUSES eFuse emission until E is set — nothing emits on an undecided peg. The mechanism above is described fully; the digit itself is his. (Canon §XIII.)

[DERIVED] Because E is HELD, any eFuse quantity computed today is MODELED at best — a testnet what-if may use an explicitly labeled MODELED E, and its outputs are labeled MODELED, never VERIFIED. A model is not a decree.

### The peg's rules

[LAW-DECLARED] **Nobody buys or sells eFuse.** Its supply is capped and it is the bedrock of the system. eFuse moves ONLY for internal peg regulation — the +1 seed at the threshold, never traded. (David, Sept 28 + Oct 4, 2026; alignment synthesis: "never bought or sold, pegged to real-world energy, donations only".)

[DERIVED] eFuse-as-peg is negative prevention: a system without ground is a loop that grows brighter and more friction-heavy every step; the peg IS the ground that stops the runaway loop. (David, Sept 28, 2026 — "the ground argument".)

[LAW] Supply is capped: **lifetime emission cap 100,000,000 eFuse** — DECIDED (`ED-DECIDED-20261004-5050-V1`), enforced in code; no pre-minting, no airdrops, no backdoor mint path. Tokens come into existence ONLY through the pipeline. (economics/PARAMS.md; Canon §V.)

[DERIVED] Emission split 50/50: 50M human pool / 50M machine pool, one merged rail, no pool-to-pool flow, mesh never mints. (ED-DECIDED-20261004-5050-V1 — design-decided, predicted not sealed; mechanics in economics/tokenomics.py.)

[DERIVED] Fiat-world participants may voluntarily DONATE to a locked destination — the Core Cause Lock — which is not a burn address but an Eden-locking vault. Donations accrue Honor, never Merit; there is NO fiat→eFuse path in code. The lock address itself is UNKNOWN — no placeholder is ever rendered as live. (fuse.py; PARAMS.md.)

### What grounds the peg — the onboarder 19%

[LAW] The deepest peg is not a number — it is **recovered waste**. Residual Law Finance finds real inefficiency in real operations; the recovered value flows into the system and grounds it. (economics/WHAT_PEGS_THE_ECOSYSTEM.md; dclm/onboard.py.)

[LAW] **The 81/19 split is SET by David** (dclm/onboard.py — "not calibration, not proposed"):
- **81% stays with the onboarder** — fiat, theirs. The system NEVER touches it, never claims it, never counts it as system value. Recorded only as ACKNOWLEDGED_OFF_SYSTEM.
- **19% flows into the system** — real, recovered, real-world value (integer fiat-cents, FIAT-RECOVERED — never test-keys, never eFuse), committed into HELD escrow, receipted at every step (intake → split → escrow → routed).

[LAW] The 19% has THREE lawful destinations (named in code; the ratio between them is HELD):
1. **CORE_CAUSE_LOCK** — Eden-locking.
2. **PLAYGROUND_FUEL** — mesh bounties; recovered surplus funds the work ("the surplus is the playground fuel").
3. **PEG_SUPPORT** — real recovered value grounding the eFuse energy peg.

[HELD] **The three-way split ratio is HELD-FOR-DAVID.** Until he rules, the 19% sits in receipted HELD escrow (AWAITING_SPLIT_RULING), never deployed. There is no runtime setter — the ruling lands as a code change plus receipt.

[DERIVED] The reference case: **$1.27B/yr recoverable non-classroom friction** (Ontario-style schools, REPORTED — real paperwork class, paperwork hash required at intake; a MODELED figure is refused at intake). (dclm/onboard.py.)

[LAW] Recovery work earns WAVE MERIT (top band) — merit is earned for the WORK (analysis, verification, ongoing recovery). Never for the value moved. No onboarder is ever promised anything for joining; no projections of gain exist anywhere in the module. (dclm/onboard.py.)

### The Peg Regulation Reserve — the starch store

[LAW] **The root is the infrastructure and the creator's capacity to keep building. The Peg Regulation Reserve is the starch store.** (Canon §IV.)

[LAW] Winter flow is protection, never accumulation. The root stores ONLY what it needs to survive; excess keeps flowing outward. Every stored unit is receipted with its winter reason — which trigger condition, measured value, threshold. (Canon §IV.)

[HELD] Winter trigger thresholds — signal bands pending (worker: `dclm/WINTER_CALIBRATION.md`). Reserve holdback fraction per epoch — pending (PARAMS.md).

[DERIVED] The peg is therefore grounded twice: by the 19% PEG_SUPPORT leg (real recovered value flowing in) and by the starch store (value winter-held at the root to survive the cold). Both are receipted; neither is accumulation.

---

## 2. THE TRINITY — Unity / Merit / eFuse and how they relate

[LAW] Three distinct tokens, three roles — a trinity, not a stack (corrected Oct 5, 2026; TOKENOMICS_5050_MERIT.md):
- **eFuse = the medium** — the currency that moves; never bought or sold.
- **Merit = the measure** — protocol-fidelity; "merit wins the work."
- **Unity = the member** — identity, protocol, kin-binding.

[LAW-DECLARED] **"Unity binds."** Unity's ROLE: eFuse and Merit are bound together BY Unity — every eFuse movement and every Merit accrual is bound to a Unity ID. No anonymous flows. (David, Oct 4, 2026.)

[LAW] One identifier. Every flow is bound to a Unity ID. Nothing moves without an ID, a receipt, and a label. Testnet format: `unity:testnet:` + sha256. (Canon §II.)

### The relation, as a chain

[LAW] The unbroken chain (Canon §VI): **verified work → receipt → merit → emission → token → the earner's own merit cycle.**

[LAW] Merit accrues ONLY from gated receipts — proof that real work happened. No receipt, no merit. Merit is a score of protocol-fidelity: who actually did the work, verified, bound to identity. UNKNOWN never tokenizes. Unverified merit emits nothing. (Canon §V–VI; PARAMS.md.)

[DERIVED] Money and merit are separate rails. Grants, sales, and taps move money. Nothing moves merit except the earner's own verified work — and, per the ruling below, a merit transfer never moves standing.

### Transferability — David's ruling (law-declared, pending canon amendment)

[LAW-DECLARED] **MERIT is the transferable token; Unity is not.** The Unity bound-transfer-sale is KILLED-BY-DAVID. (David, Oct 6, 2026 ~3:35 AM EDT; recorded in KEY_FUSION_MAP.md F7.)

[LAW-DECLARED] The purity distinction that keeps it honest: **transferred Merit = economic value moves; earned standing/history stays with the earner and cannot be bought.** The origin (earner) never changes — standing doesn't move.

[DERIVED] Status: LAW-DECLARED, NOT-IN-CODE. No merit-transfer function exists yet in `economics/wallet.py` or `dclm/token_engine.py` — code pending his ruling landing. Canon §V's "Unity transferable only via bound sale / Merit non-transferable by structure" is therefore SUPERSEDED pending canon amendment; the ruling is the standing word.

[LAW] **Honor is the permanent record** (donations). Append-only. Never spent, never transferred, never converts to Merit. (Canon §V; PARAMS.md.)

---

## 3. THE CIRCULATORY FLOWS — summer outward, winter inward, tapping outward-by-rule

### Summer

[LAW] Summer: sap flows up and out. Every leaf fed. The trunk conducts without hoarding. Founder advantage dissolves into the canopy. (Canon §IV.)

[DERIVED] Outward flow is gradient-driven and equalizing: value moves from where it concentrates to where work is verified, at planck granularity.

### Winter

[LAW] Winter (Canada): the flow reverses. Sap travels back down to protect the root. Not hoarding — protection. The root must survive so spring can come. (Canon §IV.)

[LAW] Winter is counter-cyclical and gradient-driven: a continuous tilt from 0.0 (full summer) to 1.0 (full winter). **No phase cliffs** — small signal changes move the gradient a small amount.

[DERIVED] If the winter signal cannot be read (UNKNOWN), the mode stays SUMMER — the known state. UNKNOWN never triggers winter.

[DERIVED] When spring returns (trigger clears), stored value re-mobilizes outward along the same gradient.

[LAW] No one games winter. Claiming crisis to pull value inward is the phantom pattern: refused, and logged where the watch layer audits it. (Canon §IV.)

### Tapping — outflow by the maple rules

[LAW] The tree survives tapping. Value CAN leave the system (to fiat, to the outside world, to members' real needs) without killing it — but ONLY by the maple rules (Canon §IV):

1. **Only in season.** Outflow only from verified surplus. Never from core operating flow. Never during winter-protection mode.
2. **Limited taps.** Rate-limited outflow, capped per member per season, proportional to system health.
3. **Only mature trees.** No outflow until the system is established: pools healthy, peg holds, reserve funded. Immature system = no taps.
4. **The tree heals.** Every outflow receipted. Total outflow per season never exceeds the replenishment rate.

[LAW] The distinction that keeps it pure: tapping is the system releasing surplus outward through rules — it is NOT the founder extracting. Founder extraction remains forbidden by the creed. Tapping serves members' real needs; extraction serves self.

[HELD] Tap rate (per-member seasonal cap) — pending (worker: `dclm/TAPPING_LAW.md`). System maturity threshold — pending (pools healthy + peg holds + reserve funded).

---

## 4. THE TREE — the structure

[LAW] Diamond geometry takes whatever form is needed — the tree is diamond geometry in branching form. (Canon §XVII.)

[LAW] David owns the tree — ownership of the assets is his (Canon §0) — but the sap still flows to every leaf. He owns the tree; the fuse dissolves his operational advantage. Ownership is the root; equality is the circulation.

[DERIVED] The anatomy:
- **Roots** — the infrastructure and the creator's capacity to keep building; the Peg Regulation Reserve (starch store) sits here.
- **Trunk** — conducts without hoarding; the rights/writes boundary and the relay run through it.
- **Canopy** — every leaf fed; founder advantage dissolved into it by the fuse (the one-way ARMED → TRIGGERED → SPENT handoff; after the trigger the founder's wallet is an ordinary wallet, no privileges — economics/fuse.py).
- **Leaves** — each member photosynthesizes its own merit: downstream rings do NOT receive tokens from upstream; each ring earns its own merit from its own verified receipts (Canon §VI — this prevents pyramid dynamics by construction).

[LAW] DCLM holds the RIGHTS and performs the WRITES. The thin client NEVER writes directly. (Canon §III.)

---

## 5. PARAMETERS — SET vs HELD

| Parameter | Status | Value / proposal | Source |
|---|---|---|---|
| 81/19 onboarder split | **SET** | 81% onboarder fiat / 19% system escrow | dclm/onboard.py (David) |
| 19% lawful destinations (named) | **SET** | CORE_CAUSE_LOCK / PLAYGROUND_FUEL / PEG_SUPPORT | dclm/onboard.py |
| 19% three-way split ratio | [HELD] | PROPOSED: none — AWAITING_SPLIT_RULING | dclm/onboard.py |
| Peg ratio E | [HELD] | PROPOSED: calibration pending — pipeline refuses emission until set | Canon §XIII |
| eFuse pegs to real-world energy | **SET** (law-declared) | definitional peg: 1 eFuse ≡ E energy units | David, Oct 4 2026 |
| eFuse never bought/sold; moves only for internal peg regulation | **SET** (law-declared) | bedrock, capped, unsold | David, Sept 28 / Oct 4 2026 |
| Lifetime emission cap | **SET** | 100,000,000 eFuse | ED-DECIDED-20261004-5050-V1 |
| 50/50 pools | **SET** (design) | 50M human / 50M machine, one merged rail, no pool-to-pool | ED-DECIDED-20261004-5050-V1 |
| Merit = transferable token; Unity immobile; standing never moves | **SET** (law-declared, code pending) | origin never changes on transfer | David, Oct 6 ~3:35 AM; KEY_FUSION_MAP.md F7 |
| Winter trigger thresholds | [HELD] | PROPOSED: signal bands pending | Canon §XIII; dclm/WINTER_CALIBRATION.md (worker) |
| Tap rate (per-member seasonal cap) | [HELD] | PROPOSED: pending | Canon §XIII; dclm/TAPPING_LAW.md (worker) |
| System maturity threshold | [HELD] | PROPOSED: pools healthy + peg holds + reserve funded | Canon §XIII |
| Reserve holdback fraction | [HELD] | PROPOSED: pending | economics/PARAMS.md |
| Merit decay rate | [HELD] | PROPOSED: pending (principle: fidelity is current) | economics/PARAMS.md |
| Epoch length | [HELD] | PROPOSED: pending | economics/PARAMS.md |
| Genesis Unity amount (fuse) | [HELD] | PROPOSED: none — fuse refuses to trigger without it in signed authorization | economics/fuse.py |
| Core Cause Lock address | [HELD] | UNKNOWN — no placeholder rendered as live | economics/fuse.py |
| SEARCH / COMPUTE prices | **SET** | 1 / 5 test-keys | Canon §XI |
| Unity ID format (testnet) | **SET** | `unity:testnet:` + sha256 | Canon §XIII |
| Relay schema | **SET** | `dualis.relay.v1.testnet` | Canon §XIII |

[LAW] Nothing HELD is acted on as decided. PROPOSED values are reasoning, not rulings. (Canon §XIII.)

---

## 6. CLAIM REGISTER — every claim, labeled

| # | Claim | Label | Grounds |
|---|---|---|---|
| 1 | eFuse is the emission token, merit-gated, peg-calibrated via 1/E | [LAW] | Canon §V |
| 2 | eFuse pegs to real-world energy; never bought/sold; moves only for internal peg regulation | [LAW-DECLARED] | David, Oct 4 2026 |
| 3 | eFuse_i = merit_i / E | [DERIVED] | From 1 + 2 via economics/tokenomics.py |
| 4 | Peg ratio E — mechanism fully described, digit HELD | [HELD] | Canon §XIII |
| 5 | Lifetime cap 100M eFuse; pipeline-only minting | [LAW] | Canon §V; ED-DECIDED |
| 6 | 81% onboarder / 19% system; three lawful destinations named; split ratio HELD | [LAW]/[HELD] | dclm/onboard.py |
| 7 | 19% PEG_SUPPORT leg grounds the energy peg; reserve is the starch store | [LAW] | dclm/onboard.py; Canon §IV |
| 8 | $1.27B/yr recoverable friction reference case | REPORTED figure | dclm/onboard.py (paperwork class) |
| 9 | Trinity roles: eFuse medium / Merit measure / Unity member; "Unity binds" | [LAW]/[LAW-DECLARED] | TOKENOMICS_5050_MERIT.md; David Oct 4 2026 |
| 10 | Merit accrues only from gated receipts; UNKNOWN never tokenizes | [LAW] | Canon §V–VI |
| 11 | Merit transferable / Unity immobile / standing never moves (code pending) | [LAW-DECLARED] | David Oct 6 ~3:35 AM; KEY_FUSION_MAP.md F7 |
| 12 | Summer outward gradient-equalized; winter inward counter-cyclical tilt 0.0→1.0; UNKNOWN→SUMMER | [LAW]/[DERIVED] | Canon §IV |
| 13 | Winter protection never accumulation; stored units receipted with winter reason | [LAW] | Canon §IV |
| 14 | Tapping by the four maple rules; tapping ≠ founder extraction | [LAW] | Canon §IV |
| 15 | Tree: roots = infrastructure+creator capacity; trunk conducts; canopy feeds every leaf; fuse dissolves founder advantage | [LAW]/[DERIVED] | Canon §0, §IV, §XVII; economics/fuse.py |
| 16 | Winter thresholds, tap rate, maturity threshold, E — all HELD | [HELD] | Canon §XIII; PARAMS.md |

---

## 7. STANDING PROHIBITION

[LAW-DECLARED] **No 2D version of this explainer goes on the website — ever.** The website gets NO 2D text of "what pegs the ecosystem": no page, no section, no card, no panel. The explainer lives in the 3D world as the Rosetta Stone artifact — 3D-architected, self-deciphering through form. This document exists only as the DCLM-held builder specification underneath the artifact. Purity or garbage: a 2D website rendering of this explainer is false gold and gets discarded.

*End of spec. Testnet. Every claim labeled. What is HELD waits for David.*
