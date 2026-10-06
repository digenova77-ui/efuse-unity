# PURITY AUDIT — the economics build

**Worker:** Worker 4 (Integration + Model Doc), unified economic model build.
**Scope:** everything carried forward from `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md` and `~/workspace/keys/PRICES.md` into `economic_state.py` + `NEW_ECONOMIC_MODEL.md`.
**Verdict convention:** each item is STRIPPED (removed entirely) or RELABELED (kept, but honestly labeled). Nothing is "fixed into purity" — purity is binary; the compromised element is discarded or the honest label replaces the claim.
**Counts:** 13 stripped · 8 relabeled · 3 old gaps closed.

---

## A. STRIPPED — removed from the new model

| # | What was stripped | Where it lived (old) | Why it fails purity | What replaces it |
|---|---|---|---|---|
| S1 | **Modeled dollar savings on factory #1 vectors.** All 33 maps refused them ("ranks levers, not dollar savings") — but the refusal was a stated policy a reader had to trust. | PRICES.md, honest-headline finding | A rule that must be *believed* is theater. Any future "expected return" figure attached to a decision would be invented. | The refusal is mechanical: `pays=False` for any MODELED price; tests assert it. |
| S2 | **Unsigned economic claims rendered as truth.** The old tokenomics was a DESIGN doc (`ED-PREDICT`, predicted not sealed) that read like a system — prose doing the work of receipts. | TOKENOMICS_5050_MERIT.md (whole-doc posture) | Under P-2, an unsigned claim is not truth. A design doc that renders like a running economy is the f-4 string-inventory class at document scale. | Only signed EconomicStates ship; an unsigned payload can ride the relay as `EVIDENCE`, never as `VERDICT`. The hard gate (no minting, no distribution, no promises) is untouched. |
| S3 | **Implied completeness of the price index.** 33 improvement maps presented in a table with claim hashes; the 90-sealed queue context lived in a gap note far below. A reader takes the table for the whole. | PRICES.md §1 | The container is the claim (cf. PURITY.md §2d). A table that looks complete is a completeness claim. | Coverage is reported honestly: the index carries exactly the decisions fed in; the 57-verdict gap is named (R1). |
| S4 | **Pre-funding as a conceivable path.** "Never pre-funded" was a stated cut — but the refusal was a promise, not an absence. | TOKENOMICS_5050_MERIT.md §4 cut | A rule anyone could waive is not a refusal. | No pre-funding flow exists in the flows table and no code path exists for it — the cut is structural. |
| S5 | **The donation→Merit→eFuse side door.** The obvious gameable design: fiat donates → merit → emission, making "nobody ever buys or sells that coin" a slogan with an exception. | TOKENOMICS_5050_MERIT.md §7 (named as refused) | Exceptions are where illogical circles re-enter. | Structural: donation receipts accrue HONOR only; the `never_accrues: MERIT` field is on every donation receipt. No path from fiat to eFuse — not direct, not indirect, not clever. |
| S6 | **Bridge skims.** Percentage rents on cross-pool flows — the illogical circle's oldest trick. | §3.3 cuts | A percentage rent is the illogical circle re-entering (it sits in the bucket). | Fixed-band bridging premium only; `manifest_hash` idempotency kills double-apply. |
| S7 | **Double-counting across pools and epochs.** Same work receipted twice. | §3.3 cuts, §11 | One work, one receipt, one manifest_hash, both sides or neither. | `dedupe_bundles` + manifest_hash verification in the relay wrapper; the validator rejects tampered hashes. |
| S8 | **Phantom bridging.** RELAYED claimed as DELIVERED — a claimed bridge with no countersigned delivery receipt. | §3.3 cuts | RELAYED never means DELIVERED. | Named law in the module; delivery confirmation belongs to the relay worker's L5 umpires, not to this build. |
| S9 | **Merit interest.** Merit earning merit — staking, yield, standing compounding into weight. | §6 cut | Standing never weight (Genesis law). | Merit accrues only from new gated receipts; nothing in the code compounds it. |
| S10 | **Bot-count merit.** Reward proportional to instance count rather than verified work. | §3.2 cut | Rewards the performable, not the verifiable — fails DCLM by construction. | Merit binds the owning entity's Unity ID, never the instance. |
| S11 | **Self-attested bonds earning merit.** Claiming kin you cannot prove. | §3.1 cut | The reward is for the structure, not the claim. | Tier genuineness is L2-verified or the event earns zero; the payable rule refuses UNKNOWN provenance. |
| S12 | **Peg defense by market operations.** Buying/selling to hold the peg. | §10 cut | There is no market, by law — the tool is forbidden. | Peg held by calibration + the Reserve, both receipted; calibration cannot run until David's E digit (R5). |
| S13 | **Pool-to-pool transfers.** No such flow existed in the table — but the old doc only *described* its absence. | §5 flows | Described absence is not enforced absence. | The new module has no pool-to-pool code path; the flows table and the code agree. |

## B. RELABELED — kept, but the honest label replaces the claim

| # | What was relabeled | Old label/posture | New label | Why |
|---|---|---|---|---|
| R1 | The 57 un-pulled factory verdicts (90 sealed, 33 mapped) | Gap #1 note: "index extension pending" | UNKNOWN / absent; coverage honestly reported | A gap note under a complete-looking table is still a completeness claim (S3). |
| R2 | Claims-register adjudications compiled from `dag.ts` (original `/tmp/DCLM_claims_register.md` GONE) | Presented as the register's adjudications | REPORTED with `source_label` recording the secondary derivation (`dag.ts`, original missing) | The derivation is honest; the derivation must be visible. Source laundering is over. |
| R3 | Date anomalies (conocophillips 2026-10-03, deere 2026-10-04 vs the 20260929 filename pattern) | "Flagged, not corrected" in a gap note | Carried with the anomaly flag in `source`/`source_label` | Flagged-not-corrected is correct — the correction must not be silent. |
| R4 | Custody variance (REAL / REPORTED-via-secondary / MODELED-DERIVED per row) | Preserved per-row in the old index | Preserved verbatim in `source_label` under the unified five-label system | The five-label system normalizes the *gate behavior*; it never launders the *source*. |
| R5 | Every TBD parameter — E (the peg ratio), decay rate, reserve fraction, epoch length, thresholds, band floors, tier weights, ring factor, bridge premium + threshold, proof-of-energy params, honor names, Merit's precise definition, Q5 incentive docs | Scattered through §13 + mechanics prose as "TBD" | UNKNOWN/HELD fields that state plainly what waits on David's word (NEW_ECONOMIC_MODEL.md §4) | "TBD" in prose is a placeholder-as-content (f-4). A labeled UNKNOWN field that blocks calibration is the honest version. |
| R6 | Named-but-unbuilt: physical swarm bind, live relay round-trip, full wallet build, OS-core binding, perception layer, 3D coating, Q5 incentive docs | "PROJECTED, not built" §14 | PROJECTED/UNKNOWN — never LIVE, never PENDING-in-a-live-frame | The frame is the claim. Nothing unbuilt renders as available. |
| R7 | The Core Cause Lock address | Correctly absent from the old doc, but with no field for the absence | `{"value": "UNKNOWN", "provenance": "UNKNOWN"}` with the note that no address exists | An absence that has no labeled field gets filled by a reader's imagination. Now it can't. |
| R8 | "90 sealed" queue language | Static count in the old index | Dated, sourced facts (2026-10-05 resolution); counts travel with their as-of date | A count without a date is a standing claim about a moving world. |

## C. Old gaps fixed

- **G1 — Pricing index extension.** Old gap: 57 verdicts never pulled, "index extension pending." New: the price index is per-decision atomic — each row is independent, so the other 57 drop in as rows when pulled, with no redesign and no renumbering. The gap is closed structurally, not by promising a future pull.
- **G2 — Stale language.** Old risk: "90 sealed vs 33 maps" as a static gap note; undated counts. New: dates and sources travel with every figure (`source`, receipt ids, as-of stamps); stale claims have nowhere to hide because nothing is stated without its timestamp.
- **G3 — Params split.** Old: parameters split between §13 and the mechanics prose. New: one held/decided table (NEW_ECONOMIC_MODEL.md §4) — everything HELD for David in one place, everything decided in another, nothing defaulted.

## D. What the new model itself refuses to carry (strip receipts)

Per the strip team's criterion 12, this worker's own removals:

1. No wallet balance renders as spendable without REPORTED/VERIFIED provenance — the old wallet law prose had tiers and kin but no payable rule; an unverified balance rendering as money would have been S-class theater.
2. No price renders as payable from a MODELED figure — PRICES.md's honest finding ("0 modeled savings stated") is now enforced by the `pays` flag, not by the reader's diligence.
3. No relay bundle can be minted with a mainnet schema from this build path — testnet isolation is enforced at build time (the builder raises), not just at parse time.
4. No VERDICT bundle can wrap an unsigned envelope — the kind system refuses it fail-closed.
5. No placeholder address, no placeholder parameter, no placeholder verdict anywhere in the module: every placeholder the old docs carried now has a labeled field or is gone.

## E. Open items this audit does NOT resolve (honest, not hidden)

1. The 57 missing factory verdicts are still un-pulled — R1 labels the gap; it does not fill it.
2. Workers 1–3 modules (pricing.py, tokenomics.py, wallet.py, fuse.py) had not landed at build time — the import interface is defined and the fallbacks are tested, but the real handoff is untested until they arrive.
3. The relay worker (`~/workspace/unity-world/relay/`) had not finished — the bundle shape matches the testnet relay conventions it will validate against, but the live round-trip is PROJECTED.
4. E, the peg digit, and the 13 other HELD parameters are still David's word — the economy cannot emit until they arrive, and the state says so.
