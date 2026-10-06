# COIN ARCHITECTURE GAUNTLET — COMPLETENESS ASSESSMENT

**Worker 1 — read-only assessment. No files modified. No test suite run**
(Worker 2 owns that). Quick read-only imports only, to verify class/function
existence.

**Assessed:** 2026-10-06 ~03:50 AM EDT · **Scope:** the four coins
(eFuse / Merit / Unity / Honor) across
`~/workspace/unity-world/economics/` (pricing.py, tokenomics.py, wallet.py,
fuse.py, economic_state.py) and the DCLM-side engines they delegate to
(`~/workspace/unity-world/dclm/` — token_engine.py, tokenize.py, meter.py,
winter.py, tap.py, onboard.py).

**Design baseline:** `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md`
(§§0–14 + law index), `~/workspace/dccp-world/WALLET_DESIGN_LAW.md` (§§1–7),
David's laws through 2026-10-06 ~03:44 AM EDT (Merit TRANSFERABLE;
Unity NON-transferable §7; bound-transfer-sales DEAD; transferred Merit =
value moves, earned standing/history NEVER moves).

**Classification rules used:**
- **BUILT** = working code exists AND tests exist for it
  (module + test file + test-method count cited).
- **DESIGNED** = specified in docs/decisions, no working code
  (doc cited).
- **MISSING** = named in the design but never specified, or implied but
  absent (named explicitly).
- **HELD (David)** = blocked on David's word, not a builder gap —
  listed separately, EXCLUDED from the score denominator.

**Headline: the coin architecture is NOT complete.**
Unity 91% · Merit 80% · Honor 80% · eFuse 75%.
No coin reaches 100%. Every DESIGNED/MISSING item below is a BLOCKER
under David's stop criteria (the gauntlet ends only at 100% COMPLETE).

---

## eFuse — the medium · **75%** (12 BUILT / 3 DESIGNED / 1 MISSING)

| # | Capability | Verdict | Evidence |
|---|-----------|---------|----------|
| E1 | Emission pipeline F1 — merit-gated, epoch, pool caps | **BUILT** | `economics/tokenomics.py::emission_calculator`, `PoolLedger.disburse` (L716), `EpochEmission`; `test_tokenomics.py` 55 test methods. Gated on E (HELD). |
| E2 | Peg calibration 1/E (rate = merit/E, definitional) | **BUILT** | `tokenomics.py` conversion; `DECISIONS.md` #2; refuses via `HeldParameterError` without E. Covered in the 55. |
| E3 | Donation to Core Cause Lock F4 (one-way, Honor out) | **BUILT** | `economics/wallet.py::donate` (L~975), `economics/fuse.py::compute_donation_lock` (L339); `test_wallet.py` 41 methods, `test_fuse.py` 19 methods. |
| E4 | Fuse — genesis trigger (ARMED→TRIGGERED→SPENT, once) | **BUILT** | `fuse.py::Fuse.trigger_fuse` (L223), signed authorization, nonce replay guard, terminal SPENT; `test_fuse.py` 19 methods. |
| E5 | Fuse emission path post-genesis (merit-gated Unity) | **BUILT** | `wallet.py::receive_unity_emission` (L959); AST test asserts exactly two Unity-creating paths (`fuse.py` docstring L22, test-covered). |
| E6 | Monetary law — never bought/sold, no market | **BUILT** | By absence of machinery; `tokenomics.py` L299–311 (`eFuse.transfer` raises — disbursement only via disburse/donate/cause_disburse). |
| E7 | No fiat→eFuse path | **BUILT** | Absence asserted by test (name-scan for forbidden paths; `DECISIONS.md` #3). |
| E8 | No pre-funding | **BUILT** | Ledgers start at 0; `emission_calculator` returns 0 on no verified merit (`PARAMS.md`). |
| E9 | 100M lifetime cap / 50M+50M pool authority | **BUILT** | `LIFETIME_CAP`, `POOL_CAPS`, `AuthorityExceededError`; `test_tokenomics.py`. |
| E10 | No pool-to-pool flow | **BUILT** | Absence of machinery, test-scanned (`DECISIONS.md` #3, `PURITY_AUDIT.md` S13). |
| E11 | Mesh routes, never mints | **BUILT** | `PoolLedger.mesh_route` (L741), `emission_authority: 0`; no `mesh_mint` exists (tested). |
| E12 | Cause-work disbursement F6 + donor exclusion | **BUILT** | `tokenomics.py::cause_disburse` (L798), `wallet.py::check_donor_exclusion`; `DonorExclusionError`/`DonorExclusionViolation`. |
| E13 | Peg regulation F7 — Reserve absorb/release | **DESIGNED** | `EpochEmission.reserve_held` is a field always = 0: "no holdback machinery is active" (`tokenomics.py` L485–486, L533–536). Specified in design §5.5/§10; fraction HELD. Machinery absent. |
| E14 | Tapping applied to eFuse outflow | **DESIGNED** | `dclm/tap.py::Tapper` is BUILT (24 tests in `test_tap.py`) but **explicitly excludes eFuse**: "Units are test-keys (never dollars, never eFuse)" (`tap.py` L45). The law (README tree, maple rules) implies eFuse outflow; the mapping is unspecified and unbuilt. Needs David's resolution against the three-movements law. |
| E15 | 81/19 onboarder split (residual grounding) | **DESIGNED** | In `README.md` flow diagram only. No split code anywhere in `economics/` or `dclm/onboard.py` (which has `record_residual` but no 81/19 logic). |
| E16 | Winter throttle wired into token emission | **MISSING** | Winter IS built standalone — `dclm/winter.py`: gradient 0–1, `WinterReserve`, `emission_multiplier(gradient)` (L365), `winter_store`/`winter_release`; `test_winter.py` 28 methods. But **zero references to winter in `economics/*.py`, `dclm/token_engine.py`, or `dclm/meter.py`**. The docstring's "emission throttle" claim is a promise with no wire. |

**eFuse biggest gap:** E16 — winter mode is real code with real tests and
*no connection whatsoever* to the emission it claims to throttle. (E13 peg
regulation is the close second: the Reserve is a labeled zero, not a
mechanism.)

---

## Merit — the measure · **80%** (8 BUILT / 2 DESIGNED / 0 MISSING)

| # | Capability | Verdict | Evidence |
|---|-----------|---------|----------|
| M1 | Accrual engine — gated receipts, VERIFIED-only, explicit weight | **BUILT** | `tokenomics.py::PoolLedger.accrue_merit` (L636); `dclm/token_engine.py` accrual with origin; `DECISIONS.md` #5; `test_tokenomics.py` 55 methods. |
| M2 | Transfer mechanics + value/history separation | **BUILT** | Canonical: `dclm/token_engine.py::Tokenizer.merit_transfer` — frozen `MeritRecord` (origin_earner_id + origin_receipt_ref immutable), `standing(identity)` sums origin-based delta, `merit_balance(identity)` sums owned; transfer changes owner only, origin carried forward. `economics/wallet.py::transfer_merit` (L1072) delegates to it, wallet receipts structurally barred from carrying origin keys (L1170–1173). `test_tokenize.py` 64 methods (incl. AST hooks), `test_merit_regen.py` 27 methods, `test_wallet.py` transfer tests (L606–683). **This is code, not promise.** |
| M3 | Emission gate reads STANDING, never holdings | **BUILT** | `dclm/meter.py::emission_eligibility` — "bought Merit never gates emission"; `test_merit_regen.py` (27): funded-buyer-with-zero-standing refused, earner stays eligible after selling. |
| M4 | Decay — mechanics | **BUILT** | `tokenomics.py::PoolLedger.apply_decay` (L677); refuses without an explicit rate (HELD digit). Principle is law in code. |
| M5 | No merit interest (no staking/yield) | **BUILT** | Absence of machinery, test-scanned (`PURITY_AUDIT.md` S9). |
| M6 | Bot-count merit refused | **BUILT** | Merit binds the owning entity's Unity ID, never the instance (`PURITY_AUDIT.md` S10; tokenize slice registry). |
| M7 | Self-attested bonds earn zero | **BUILT** | Tier genuineness L2-verified or zero; payable rule refuses UNKNOWN provenance (`PURITY_AUDIT.md` S11). |
| M8 | No-cascade / derivative regen | **BUILT** | `test_merit_regen.py`: AST + behavioral proof no path credits one identity on another's; downstream rings earn their own merit. |
| M9 | Gating: work access (higher merit → higher bounty bands) | **DESIGNED** | `bounty_band_floors_widths` is a HELD param (`tokenomics.py` L178); **no gating code exists** anywhere. Named in design §6-adjacent mechanics; unbuilt. |
| M10 | Tier/ring amplification of merit | **DESIGNED** | `tier_weights` (friend/good friend/family/kin) and `ring_depth_factor` are HELD (`PARAMS.md`); no merit-weighting code consumes them. Wallet-side tier grants are built for *sharing*, not for merit weighting. |

**⚠ BLOCKER — stale law in code (not counted in score, must-fix):**
`economics/tokenomics.py` still encodes the DEAD law: module docstring
L14–17 "Merit = the measure (non-transferable…)", `PARAMS` entry
"merit_non_transferable" (L155), `Merit.transferable = False` (L323, L336)
→ `NonTransferableError`, and `PARAMS.md`'s "Merit non-transferable"
row. David's 2026-10-06 ~03:35 AM EDT law says Merit IS transferable.
The canonical path (`dclm/token_engine.py`, `wallet.py`) implements the
new law; the economics engine module contradicts it. Two modules, two
laws — this is the single most dangerous item in the whole assessment:
**code that actively contradicts standing law.** (Confirmed by read-only
import: `tokenomics.Merit.transferable = False`.)

**Merit biggest gap:** the stale-law contradiction above. Mechanically,
M9/M10 (work-access gating, tier/ring amplification) are the largest
unbuilt capabilities.

---

## Unity — the member · **91%** (10 BUILT / 1 DESIGNED / 0 MISSING)

| # | Capability | Verdict | Evidence |
|---|-----------|---------|----------|
| U1 | Binding enforcement — attempt-transfer must fail | **BUILT** | No transfer path exists; `test_wallet.py::test_unity_not_transferable` (L337) raises `UnityBindingError`; `token_engine.py` AST asserts no Unity transfer-ish names and zero `UnityToken` instantiations (`test_tokenize.py`). |
| U2 | Identity derivation | **BUILT** | `wallet.py::derive_unity_id` (L236): `unity:testnet:` + sha256(pubkey), one-way. |
| U3 | Fuse emission path (`receive_unity_emission`) | **BUILT** | See E5; gated receipt required; airdrop-style credit refused (`test_wallet.py` L472–477). |
| U4 | Tier grants — signed, crypto-enforced | **BUILT** | `wallet.py::make_tier_grant` / `apply_tier_grant`; forged grants refused; no signature → no tier (`test_wallet.py` L192–208). |
| U5 | Kin bonds — mutual-signature principle | **BUILT (partial)** | `wallet.py::bind_kin` (L645), `is_kin` (L470); kin gates the family tier (`test_kin_binding_gates_family_tier`, L252). |
| U6 | Founder's wallet ordinary post-genesis | **BUILT** | No privileges in code; Fuse holds no private key (`fuse.py` docstring points 1–5). |
| U7 | Shareable identity (click-to-copy / QR digital twin) | **BUILT** | `qr_payload()` — the exact QR payload as sendable text (`wallet.py` docstring §1). |
| U8 | Easiest connectors | **BUILT** | `wallet.py::connect()` trivially links two Unity IDs (docstring §2). |
| U9 | Tiered sharing enforcement | **BUILT** | Friend/good_friend/family limits enforced at share time; `TIER_LIMITS` (MODELED, labeled). |
| U10 | Money + information on the same rails | **BUILT** | `wallet.py::share()` — identical mechanism, content type varies (docstring §4). |
| U11 | Deeper kin mechanism | **DESIGNED** | `KIN_MECHANISM_TBD = True` (`wallet.py` L116) — flagged in `WALLET_DESIGN_LAW.md` §5 ("Recorded as principle; mechanism TBD"). The mutual-signature bond records the principle; what "kin is binding" means beyond two signatures is unspecified. |

**Unity biggest gap:** U11 — the kin mechanism is the one named-but-unspec'd
piece of the wallet law. (Needs David's word on what binding means, then
~50 lines.)

---

## Honor — the donation class · **80%** (4 BUILT / 1 DESIGNED / 0 MISSING)

| # | Capability | Verdict | Evidence |
|---|-----------|---------|----------|
| H1 | Donation flow — donations accrue Honor | **BUILT** | `wallet.py::donate` (Honor receipt: public, permanent, non-transferable); `token_engine.py::HonorRecord` (append-only per-ID list); `fuse.py::compute_donation_lock`. |
| H2 | Non-conversion enforcement — no Honor→eFuse path | **BUILT** | `Honor.redeem_for_emission` → `HonorConversionRefused` (`tokenomics.py`); `test_tokenize.py` L610–617 asserts no spend/redeem/convert function exists (AST + attribute scan); `test_wallet.py` L380–393 asserts no `redeem_honor`. **Absence-of-code IS verified by test.** |
| H3 | Permanence — append-only, never spent | **BUILT** | `HonorRecord`: permanent True, spendable False; wallet ledger has no debit path for Honor; tested (L380–393, L610–617). |
| H4 | Public, named | **BUILT** | Donor Unity ID on every donation receipt; `compute_donation_lock` aggregates per donor. (Class *names* are HELD — see below.) |
| H5 | Fiat donation gateway F5 | **DESIGNED** | `compute_donation_lock` accepts `kind: "fiat"` as a *label* and the design names the gateway (design §9/F5), but **no fiat gateway exists** anywhere — no intake, no conversion guard, no receipt path. The label is ahead of the machinery. |

**Honor biggest gap:** H5 — the fiat side of the donation sink is a label
with no gateway.

---

## Cross-coin pipeline & pricing connection (not per-coin; BLOCKERS)

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| X1 | End-to-end pipeline (work → receipt → merit → emission → eFuse) as one integrated, receipted pass | **MISSING** | No orchestrator exists in `economics/` or `dclm/`. `economic_state.py` *adapts* the modules (and explicitly does NOT re-drive tokenomics receipts — "its receipt chains have exactly one owner"); `worker_modules_present()` reports `tokenomics: False` because the landed API differs from the contract. The modules are loosely coupled by convention, not by a pipeline. |
| X2 | Pricing engine → token pipeline connection | **MISSING** | `pricing.py` (20 tests) prices decisions standalone; nothing feeds its output into merit or emission. The design never specified the link (the README flow starts at "verified work"); economic_state adapts pricing and tokenomics independently. |
| X3 | Umpire watch L1/L2/L4/L5/L7 over the circuit | **DESIGNED** | Named in design §12 with per-level speedometers; "umpire" appears in code only in `dclm/share.py` and `economic_state.py` comments. No umpire module exists. |
| X4 | Bounty escrow F2/F3 (pool → Mesh escrow → fulfiller, both-side receipts) | **BUILT** (Oct 6, 2026 — Fix Worker A5) | `economics/mesh_escrow.py`: `MeshClearing.bounty_post` (F2 — commissioning pool authority reserved, Unity-bound, terms receipted as `bounty_post`) and `MeshClearing.bounty_fulfill` (F3 — both-side receipts required, `work_manifest_hash` idempotency escrow-wide, disbursement draws on commissioning pool authority via `Ledger.disburse`, bridge merit to fulfiller); `expire_bounty` releases the reservation to the commissioning pool's authority receipted as `bounty_return`. New receipt kinds `bounty_post`/`bounty_fulfill`/`bounty_return` added to `tokenomics.py` RECEIPT_KINDS. 17 tests in `economics/test_mesh_escrow.py`, all green. No pool-to-pool machinery exists (verified by scan); escrow holds no emission authority (verified by test). |
| X5 | Physical swarm bind (design §3.4) | **MISSING** | Named, slotted, explicitly unbuilt ("Marked PROJECTED"). Needs hardware — not closable by code workers. |
| X6 | Full wallet build — claim surfaces for every reward path | **MISSING** | Design §14 honest WATER. |
| X7 | Live relay round-trip | **MISSING** | Design §14; `PURITY_AUDIT.md` E3 (PROJECTED). |
| X8 | Incentive docs Q5 (epoch incentives beyond emission) | **MISSING** | Unpulled from David's Drive; design §14 + `NEW_ECONOMIC_MODEL.md` §4 HELD #14. |
| X9 | OS-core binding, perception layer, 3D coating | **MISSING** | Design §14. |
| X10 | eFuse implementation as subject of the MAX FRICTION battery | **MISSING** | Design §14: "No eFuse implementation exists — the MAX FRICTION security battery has no subject." |

## HELD for David (excluded from scores — block the hard gate, not the builders)

E (peg ratio) · merit decay rate · reserve holdback fraction · epoch
length · genesis Unity amount (`GENESIS_UNITY_AMOUNT = None`) · honor
class names (`HONOR_CLASS_UNNAMED`) · Merit's precise definition ·
tier weights · ring-depth factor · bridge premium band + eligibility ·
corroboration thresholds · bounty band floors/widths ·
machine proof-of-energy params · tap rate · winter trigger thresholds
(`WINTER_CALIBRATION.md`: proposed, HELD) · Core Cause Lock address
(`{"value": "UNKNOWN"}`) · Q5 incentive docs. Full table:
`NEW_ECONOMIC_MODEL.md` §4, `PARAMS.md`.

---

## 100% COMPLETE closure plan

Ranked: every DESIGNED/MISSING item blocks the 100% bar. Within blockers,
ordered by closability (code-ready first, needs-David's-word last).
Effort = rough builder estimate for a fix worker.

### Tier A — code it now (no new decisions needed)

| Rank | Item | What closes it | Effort |
|------|------|----------------|--------|
| A1 | **Merit stale-law contradiction** (`economics/tokenomics.py`) | Update `Merit.transferable = True`; replace the `NonTransferableError` transfer refusal with delegation to the engine's sole legal path (or remove `Merit.transfer()` and document `dclm/token_engine.py::merit_transfer` as canonical); update the module docstring, `PARAMS.md` "Merit non-transferable" row, `PARAMS["merit_non_transferable"]`, and the tests that assert the old refusal. Mirror David's 03:35 AM law verbatim in the docstring. | ~40 lines + test updates, ~2h |
| A2 | **Winter throttle integration** (E16) | Wire `dclm/winter.py::emission_multiplier(gradient)` into the emission path: multiply the computed epoch emission in `tokenomics.py::emission_calculator` (and/or gate in `dclm/meter.py`) by the winter gradient; receipt the gradient value on the epoch receipt; add ~6 tests (full-summer = 1.0×, deep-winter floor > 0, UNKNOWN signal → summer default). | ~60 lines + 6 tests, ~3h |
| A3 | **Peg regulation F7 machinery** (E13) | Implement Reserve absorb/release in `tokenomics.py`: on epoch close, hold back `reserve_holdback_fraction` of computed emission into the Reserve (receipted, L5-visible); release path when calibration supports it. Gate the whole thing on the HELD fraction — build the machinery to refuse until decided, like `apply_decay`. | ~80 lines + 8 tests, ~4h |
| A4 | **End-to-end pipeline orchestrator** (X1) | New module (e.g. `economics/pipeline.py`): one function `run_epoch(inputs)` that drives verified-work → receipt → merit accrual → emission → disbursement across `tokenomics.py`/`token_engine.py`/`wallet.py` in a single receipted, idempotent pass, without double-applying receipts (respect the one-owner rule from `economic_state.py`). | ~120 lines + 10 tests, ~5h |
| A5 | **Bounty escrow F2/F3** (X4) — ✅ CLOSED Oct 6, 2026 (Fix Worker A5) | Implemented escrow hold (`bounty_post`: pool → Mesh Clearing escrow, receipted) and release (`bounty_fulfill`: escrow → fulfiller on both-side receipts, `manifest_hash` idempotency, bridge merit to fulfiller). | Delivered: `economics/mesh_escrow.py` + 17 tests in `economics/test_mesh_escrow.py`, all green; receipt kinds added to `tokenomics.py`. |
| A6 | **81/19 onboarder split** (E15) | Specify the split point (at `record_residual` intake in `dclm/onboard.py`), then code it: 81% to onboarder's Unity ID, 19% routed to Lock/fuel/peg per `README.md`; receipted. | Spec ~1h + ~40 lines, ~2h |
| A7 | **Tier/ring merit amplification** (M10) | Build the weighting machinery gated on the HELD digits: merit accrual accepts tier/ring multipliers; refuses (HeldParameterError) until David sets the tables — same pattern as `apply_decay`. | ~70 lines + 6 tests, ~4h |
| A8 | **Work-access gating** (M9) | Build merit→bounty-band gating: band floors/widths HELD; machinery maps standing → eligible bands; refuses until decided. | ~50 lines + 5 tests, ~3h |
| A9 | **Umpire circuit** (X3) | Phase 1: a `dclm/umpires.py` skeleton with L1 (ID derivation check), L4 (pool-boundary check), L5 (receipt-stream idempotency sampler) as callable watchers over the pipeline's receipt trail; L2/L7 as named stubs. Full L7 gameable-pattern recognition is a research track. | ~200 lines, ~8h (phase 1) |

### Tier B — specify first (needs David's word, then code)

| Rank | Item | What closes it | Effort |
|------|------|----------------|--------|
| B1 | **Deeper kin mechanism** (U11) | David defines what "kin is binding" means beyond mutual signatures (L2 verification? lineage depth?); then ~50 lines in `wallet.py` replacing `KIN_MECHANISM_TBD`. | Spec ~1h + code ~2h |
| B2 | **Tapping vs the three-movements law** (E14) | David resolves: is tapping a 4th eFuse movement, a form of peg regulation, or test-keys-only forever? Then either wire `Tapper` to eFuse outflow (maple rules enforced) or strike the implication from the docs. | Decision ~1h + code ~3h if wired |
| B3 | **Fiat donation gateway F5** (H5) | David names the gateway; then build the fiat intake → Honor receipt path (no conversion rate, no eFuse promised — the refusal is the feature). | Decision ~1h + ~50 lines ~3h |
| B4 | **Pricing ↔ token pipeline** (X2) | Decision: are they parallel by design (document it in `NEW_ECONOMIC_MODEL.md` — closes the item as "intentionally unlinked") or is there a specified feed (then build it)? | Decision + doc ~1h |

### Tier C — not closable by code workers (named honestly)

- **X5 physical swarm bind** — needs hardware-programmed bots; slot is clean, build waits on the physical program.
- **X6 full wallet claim surfaces, X7 live relay round-trip, X9 OS-core/perception/3D** — downstream builds, other workers' lanes.
- **X8 Q5 incentive docs** — David pulls from Drive.
- **X10 eFuse subject for the MAX FRICTION battery** — blocked on the hard gate (full repeated evidence).
- **All HELD parameters** — David's digits; the machinery above is built to refuse until they arrive, which is the correct 100%-of-architecture posture: the code is complete, the *launch* waits on him.

### Re-assessment bar

100% COMPLETE = every Tier A item built + tested, every Tier B item
decided (then built), Tier C items tracked as named external
dependencies. The stale-law fix (A1) is the highest-priority single
item: it is the only place where running code contradicts standing law.

---

## Appendix — test inventory (method counts, `def test` grep)

| Module | Tests | Test file | Methods |
|--------|-------|-----------|---------|
| pricing.py | per-decision meter, provenance | `economics/test_pricing.py` | 20 |
| tokenomics.py | gates, pools, emission, refusals | `economics/test_tokenomics.py` | 55 |
| wallet.py | wallet, tiers, kin, donate, transfer_merit | `economics/test_wallet.py` | 41 |
| fuse.py | fuse state machine, donation lock | `economics/test_fuse.py` | 19 |
| economic_state.py | fused state, signing, relay bundle | `economics/test_economic_state.py` | 41 |
| dclm/token_engine.py | tokenization, origin, transfers | `dclm/test_tokenize.py` | 64 |
| dclm/meter.py | emission gate (standing) | `dclm/test_merit_regen.py` | 27 |
| dclm/winter.py | winter gradient, reserve, throttle fn | `dclm/test_winter.py` | 28 |
| dclm/tap.py | tapping law (test-keys) | `dclm/test_tap.py` | 24 |

**Total: 319 test methods across 9 suites.** (Counts are `def test`
occurrences; Worker 2 runs the suites. RECEIPTS.md records 55/33/19/41
passing at build time; `test_wallet.py` has since grown 33 → 41 with the
transfer tests.)

## Appendix — key file map for fix workers

- `~/workspace/unity-world/economics/tokenomics.py` — emission engine (A1, A3)
- `~/workspace/unity-world/economics/wallet.py` — wallet, donate, transfer_merit, kin (A1, B1)
- `~/workspace/unity-world/economics/fuse.py` — fuse, donation lock (H5)
- `~/workspace/unity-world/economics/economic_state.py` — fusion layer (A4, B4)
- `~/workspace/unity-world/dclm/token_engine.py` — canonical Merit transfer + origin (reference for A1)
- `~/workspace/unity-world/dclm/winter.py` — winter mechanism (A2)
- `~/workspace/unity-world/dclm/tap.py` — tapping law (B2)
- `~/workspace/unity-world/dclm/meter.py` — emission gate (A2, A8)
- `~/workspace/unity-world/dclm/onboard.py` — residual intake (A6)
- `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md` — the design baseline
- `~/workspace/dccp-world/WALLET_DESIGN_LAW.md` — wallet law (§5 kin, §7 Unity)
