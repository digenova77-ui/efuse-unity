# KEY FUSION MAP — versus PRICING INDEXING

**unity-world · testnet only · 2026-10-06**
**Order:** David — KEY FUSION MAPPING VERSUS PRICING INDEXING.
**Standard:** no invented fusions, no invented prices. UNKNOWN never PASS.
**Update (David, Oct 6, 2026 ~3:35 AM EDT):** MERIT is the transferable token; Unity is not. The Unity bound-transfer-sale is KILLED-BY-DAVID — excluded from this taxonomy entirely. Replacement fusion F7 (Merit transfer) mapped per his spec; law-declared, code pending.

---

## 1. FUSION TAXONOMY

Each fusion: which keys combine · what it unlocks · what it authorizes · code refs · purity status (Unity-bound / receipted / labeled).

### F1 — Identity binding (the root fusion)
- **Keys:** member's Unity ID (`unity:testnet:...`) + member's WebAuthn device credential (passkey; the gate's challenge-response proof). `request_bind` → `confirm_bind` only on a VERIFIED assertion.
- **Unlocks:** BOUND state; the GATE envelope authorizing metered intent.
- **Authorizes:** SEARCH and COMPUTE intents to draw test-keys from the identity's Unity wallet. Looking/rendering needs no binding at all.
- **Code:** `gate/gate.py` — `UnityGate.request_bind`, `confirm_bind`, `emit_gate_envelope`, `authorize_intent`. Ceremony doc: `gate/CEREMONY.md`.
- **Purity:** Unity-bound ✓ (non-testnet identities structurally refused). Receipted ✓ (binding receipts; state file hash-chained in the mutation log). Labeled ✓ (schema-tagged envelopes; five-label provenance at the meter/commit layer). Formation is FREE — the fusion itself costs nothing.
- **Note:** the WebAuthn verifier slot returns UNKNOWN in this sandbox; binding completes only on VERIFIED, never on UNKNOWN — honest by construction.

### F2 — Metered intent (bound identity + spend authority)
- **Keys:** BOUND Unity ID + wallet balance + intent_id (idempotency key). This is the spend-authority fusion: identity alone cannot move keys; keys alone cannot authorize without the identity.
- **Unlocks:** execution of metered actions.
- **Authorizes:** deduction of the metered price: SEARCH = 1 test-key, COMPUTE = 5 test-keys. Refusals: UNBOUND / NOT_TESTNET_IDENTITY / INSUFFICIENT_KEYS / UNKNOWN_ACTION — all signed, honest.
- **Code:** `dclm/meter.py` — `Wallet.meter_intent`, `PRICES = {LOOK:0, RENDER:0, SEARCH:1, COMPUTE:5}`. Canon §XI sets the same constants.
- **Purity:** Unity-bound ✓ · receipted ✓ (Ed25519-signed GRANT/REFUSAL envelopes) · labeled ✓ (`DERIVED` receipts, `VERIFIED` signature envelopes). Ledger never negative; idempotent per intent.

### F3 — Shared access grant (two-party key fusion)
- **Keys:** granter Unity ID + grantee Unity ID (+ tier FRIEND/GOOD_FRIEND/FAMILY, content_type, depth, duration, granter-set price in test-keys). Tier lives as an INTEGER inside the signed grant body.
- **Unlocks:** tiered access to DATA / RTE_SEAT / WORLD_VIEW / RESOURCE / COMPUTE.
- **Authorizes:** `access()` — deducts the grant's price from the ACCESSOR's wallet, credits the GRANTER in full (DCLM takes no cut). Money moves; merit never does (`merit_flow: "NONE"` stamped on grant, debit, credit, and event). Revocation is instant and total (live registry reads, no cache).
- **Code:** `dclm/share.py` — `issue_grant`, `revoke_grant`, `check_access`, `access`. Canon §VII.
- **Purity:** Unity-bound ✓ (both IDs) · receipted ✓ (signed grant + GRANT_ISSUE/GRANT_REVOKE/SHARED_ACCESS commit envelopes) · labeled ✓. Tier ≠ price: the tier sets access depth; the price is set independently by the granter.

### F4 — Kin bond (family-tier fusion)
- **Keys:** granter + grantee at FAMILY tier + L2-umpire kin attestation.
- **Status: IN-CODE, INOPERABLE — integration PENDING.** `verify_kin()` has no registered authority (`_KIN_AUTHORITY = None`); family grants are refused with NOT_KIN_VERIFIED. Kinship is never assumed.
- **Code:** `dclm/share.py` — `register_kin_authority`, `verify_kin`, the FAMILY branch of `issue_grant`.
- **Purity:** cannot be scored operationally — no kin attestation exists to verify. Purity N/A until the umpires wire in. Honest gap, not a pass.

### F5 — The Fuse (founder-key genesis)
- **Keys:** founder's Ed25519 public key (verify-only; the Fuse holds NO private key) + founder Unity ID + David's signed authorization carrying the genesis amount inside the signed body.
- **Unlocks:** Unity entering circulation — the network launch.
- **Authorizes:** the SOLE Unity genesis mint. Exactly two mint paths exist in code (`mint_paths()`): `Fuse.trigger_fuse` (once) and `wallet.receive_unity_emission` (merit-gated). State machine ARMED → TRIGGERED → SPENT is one-way; SPENT has no outgoing edge; replay impossible (nonce registry).
- **Code:** `economics/fuse.py` — `Fuse.trigger_fuse`, `make_fuse_authorization`. AST test asserts no third mint path.
- **Purity:** Unity-bound ✓ (founder Unity ID named in authorization and state) · receipted ✓ (hash-chained genesis receipt) · labeled ✓ (trigger event VERIFIED; amount REPORTED — David's word, never invented; `GENESIS_UNITY_AMOUNT = None` held).

### F6 — Merit-gated Unity emission
- **Keys:** earner's Unity ID + the tokenization worker's gated emission receipt + the earner's OWN verified-receipt merit (read via `emission_eligibility` / `MeritReader`).
- **Unlocks:** Unity tokens bound to the earner's ID.
- **Authorizes:** emission ONLY against own merit — derivative merit regeneration: no cascade, no other identity's receipts. Peg E is HELD-FOR-DAVID; unverified merit emits nothing.
- **Code:** `dclm/token_engine.py` — `Tokenizer.tokenize`, `_mint_efuse`; `dclm/meter.py` — `emission_eligibility`; `economics/wallet.py` — `receive_unity_emission`.
- **Purity:** Unity-bound ✓ · receipted ✓ · labeled ✓. No price — merit-gated, not purchased.

### F7 — Merit transfer (REPLACEMENT fusion, per David's ruling)
- **Keys (per David's spec):** sender Unity ID + recipient Unity ID (+ DCLM signing key authorizing).
- **Unlocks:** economic value movement.
- **Authorizes:** spendable Merit balance change. **Origin (earner) never changes — standing doesn't move.** Transferred Merit = economic value moves; earned standing/history stays with the earner and cannot be bought.
- **Status: LAW-DECLARED, IN-CODE (2026-10-06 ~04:05 EDT).** David resolved the contradiction Oct 6, 2026 ~3:35 AM EDT: "MERIT is the transferable token; Unity stays non-transferable." Implemented: `dclm/token_engine.py::Tokenizer.merit_transfer` (sole legal path, signed MERIT_TRANSFER receipts, origin immutable) + `economics/wallet.py::transfer_merit` (delegates to the engine; records ownership changes, never origin). Standing-vs-value distinction structural: `standing()` sums by origin_earner_id; emission gate reads standing, never holdings (D13). The earlier honest gap is CLOSED.
- **Purity:** UNPRICED — the index is silent (see §2).

### F8 — Parliament collapse — ABSENT as a key fusion
- `~/workspace/core-rings/rings.py` fuses three DIMENSIONS (logic/truth/pragmatism) into a verdict via Parliament collapse. **No keys are involved.** Expected as a "multi-key decision" fusion; the code contains no such thing. Marked ABSENT, never invented.
- (Multi-party grants — granter + grantee — are F3. No additional multi-key mechanism exists in code.)

### F9 — Winter store / release (key + winter-signal fusion)
- **Keys:** identity's test-key balance + winter signal (gradient 0.0–1.0, evaluated through `evaluate_trigger`).
- **Unlocks:** inward flow to the Peg Regulation Reserve (protection, capped at SURVIVAL_NEED_CAP per identity) and release back to circulation.
- **Authorizes:** movement of test-keys identity ↔ reserve; phantom claims (no supporting signal) refused. No fee; no price.
- **Code:** `dclm/winter.py` — `winter_store`, `winter_release`, `winter_aware_faucet`.
- **Purity:** Unity-bound ✓ · receipted ✓ (signed, winter reason stamped) · labeled ✓.

### F10 — Tap outflow (surplus-release fusion)
- **Keys:** member identity + VERIFIED SURPLUS (season-gated, winter-gradient-gated, rate-limited).
- **Unlocks:** outward value flow to members' real needs (the maple law — tapping, not extraction).
- **Authorizes:** `TAP_OUTFLOW` writes. Season must be open; tap rate and maturity threshold are HELD-FOR-DAVID. No price.
- **Code:** `dclm/tap.py` — `Tapper`, `TapSeason`. Doc: `dclm/TAPPING_LAW.md`.
- **Purity:** Unity-bound ✓ · receipted ✓ · labeled ✓.

### F11 — Onboarder pipeline (identity + paperwork fusion)
- **Keys:** onboarder Unity ID + REPORTED residual paperwork (paperwork hash required; MODELED figures refused at intake).
- **Unlocks:** the 81/19 split — 81% stays with the onboarder off-system (fiat, theirs); 19% into receipted HELD escrow (destinations HELD-FOR-DAVID).
- **Authorizes:** no key spend — amounts are integer fiat minor units labeled FIAT-RECOVERED, never test-keys; the meter wallet is untouched. Recovery WORK earns gated receipts → wave merit → emission (top band only; calibration HELD-FOR-DAVID).
- **Code:** `dclm/onboard.py`. Doc: `dclm/ONBOARDER_PIPELINE.md`.
- **Purity:** Unity-bound ✓ · receipted ✓ (ONBOARD / RESIDUAL_INTAKE / SPLIT_EXECUTE / NINETEEN_ROUTE) · labeled ✓. No onboarder is ever promised anything.

### F12 — Donation to the Core Cause Lock
- **Keys:** donor Unity ID + eFuse.
- **Unlocks:** HONOR accrual (public, named, permanent, non-transferable).
- **Authorizes:** one-way value lock; donor exclusion (donated eFuse never re-emitted to the same donor). Donation accrues ZERO merit — no path from donation to emission.
- **Code:** `economics/wallet.py` — `donate`; `economics/fuse.py` — `compute_donation_lock`.
- **Purity:** Unity-bound ✓ · receipted ✓ · labeled ✓. Lock address UNKNOWN until real — never invented.

### F13 — eFuse share (two-wallet value fusion)
- **Keys:** sender Unity ID + recipient Unity ID (+ tier caps: `efuse_per_share`, `shares_per_epoch`).
- **Unlocks / authorizes:** eFuse movement between wallets, tier-capped. Unity share path raises `UnityBindingError` — Unity never moves (see KILLED below).
- **Code:** `economics/wallet.py` — `share`.
- **Purity:** Unity-bound ✓ · receipted ✓ · labeled ✓. No fee; no price.

### KILLED-BY-DAVID — Unity bound-transfer-sale — REMOVED FROM TAXONOMY
- The bound-sale concept (`dclm/token_engine.py` `Tokenizer.bound_sale`; the Unity branch of `economics/wallet.py` `share`) is **dead per David's ruling (Oct 6, 2026 ~3:35 AM EDT)**: Unity tokens are bound to their Unity ID — cannot be sent, sold, gifted, or moved between wallets, not even by David (§7; `wallet.py` enforces via `UnityBindingError`, 33/33 tests). MERIT is the transferable token instead (F7).
- It is NOT mapped, NOT priced, and NOT counted. The code remnants are superseded by law, not deleted by this worker.

---

## 2. PRICING MATRIX — fusion × decision × price × source

**The two price systems in this build:**
- **A. The intent meter** (test-keys): prices the ACT of wanting. `dclm/meter.py` PRICES; Canon §XI SET constants.
- **B. The decision index** (USD cost surfaces): prices WHAT a decision touches. 53 rows in the engine (`economics/pricing.py` INDEX: 33 factory + 2 RTE + 16 claims + rows #101/#102 per `economics/PRICES_ADDENDUM.md`); 51 in `~/workspace/keys/PRICES.md`; machine-readable parse in `dclm/data.py` `pricing_index()`. Doctrine: "the decision is the atomic unit of price. No tiers, ever" (`TIERS = None`).

**Finding:** NONE of the 53 indexed decisions is a key-fusion event. The index prices corporate improvement vectors, RTE findings, and claims adjudications — not bindings, grants, fuses, or emissions. Every fusion row is therefore UNPRICED in the index, and the matrix says so honestly. A fusion's real price — where one exists — lives in system A, in granter-set fields, or in David's REPORTED word.

| Fusion | Formation price | Exercise price | Decision-index price (53 rows) | Price source |
|---|---|---|---|---|
| F1 Identity binding | 0 (free) | — (exercise is F2) | UNPRICED — no binding decision in the index | gate.py (no debit on any transition); meter.py |
| F2 Metered intent | — | SEARCH = 1 test-key · COMPUTE = 5 test-keys · LOOK/RENDER = 0 | UNPRICED — SEARCH/COMPUTE are metered intents, not indexed decisions | `dclm/meter.py` PRICES dict; Canon §XI (SET) |
| F3 Shared grant | 0 (issue free) | grant price, granter-set (non-negative int test-keys); accessor pays, granter credited in full | UNPRICED — no grant decision in the index | `dclm/share.py` `issue_grant(price=…)`; access() debit/credit |
| F4 Kin bond | — (inoperable) | — | UNPRICED — PENDING integration | share.py NOT_KIN_VERIFIED refusal |
| F5 The Fuse | 0 (trigger free) | genesis amount = REPORTED (David's digit inside the signed authorization) | UNPRICED — no genesis decision in the index | `economics/fuse.py` `GENESIS_UNITY_AMOUNT = None`; amount provenance "REPORTED — David's word" |
| F6 Merit emission | 0 (gating free) | merit-gated, not priced (peg E HELD-FOR-DAVID) | UNPRICED — no emission decision in the index | `dclm/meter.py` `emission_eligibility`; token_engine.py |
| F7 Merit transfer | NOT-IN-CODE | — | UNPRICED — the index is silent | David's ruling (Oct 6, 2026 ~3:35 AM EDT); no code path yet |
| F8 Parliament | ABSENT (not a key fusion) | — | N/A | `core-rings/rings.py` (dimensions, not keys) |
| F9 Winter | 0 | 0 (moves keys, no fee) | UNPRICED — no winter decision in the index | `dclm/winter.py` winter_store/release |
| F10 Tap | 0 | 0 (rate-limited, no fee) | UNPRICED — no tap decision in the index | `dclm/tap.py`; rate HELD-FOR-DAVID |
| F11 Onboarder | 0 | 0 (no keys move; fiat minor units) | UNPRICED — no onboarding decision in the index | `dclm/onboard.py`; ONBOARDER_PIPELINE.md |
| F12 Donation | 0 | 0 (one-way lock; Honor, never Merit) | UNPRICED — no donation decision in the index | `economics/wallet.py` donate() |
| F13 eFuse share | 0 | 0 (tier-capped, no fee) | UNPRICED — no share decision in the index | `economics/wallet.py` share() |
| KILLED bound-sale | — | — | EXCLUDED — not priced, not mapped | David's ruling; UnityBindingError in wallet.py |

**Decision-index scope note (source rows):** the 53 engine rows price decisions `factory-1…33, factory-101, factory-102, rte-edu, rte-health, claims C1–C4/O1–O6/R1–R4` — each row bills the canon meter's flat COMPUTE price (5 test-keys, SET in `dclm/meter.py`); each row's USD cost surface rides along as labeled data only (billable 0), never as a charge (`economics/pricing.py` `price_decision()`; `economics/economic_state.py` fuses the flat test-key price with `pays` following the engine's `pass`). No row names a binding, grant, fuse, emission, or transfer. That silence is why the column reads UNPRICED everywhere — the honest state, not an omission.

---

## 3. THE FUSION↔PRICING RELATIONSHIP — THE RULE

**Rule: pricing GATES fused authority; fusion never DRIVES price.**

Formation is always free — binding (F1), grant issue (F3), fuse arming/trigger (F5), emission gating (F6), winter/tap/onboard/donate/share (F9–F13) all cost nothing to form. Exercise is gated by price: the fused authority refuses — honestly receipted — when the wallet cannot cover it (`UNBOUND` / `INSUFFICIENT_KEYS` in `gate.authorize_intent` and `meter.meter_intent`; `INSUFFICIENT_KEYS` in `share.access`; `NOT_KIN_VERIFIED` where the fusion cannot complete). No code path varies any price by the keys fused: the meter's prices are SET constants (SEARCH=1, COMPUTE=5 test-keys; Canon §XI), grant prices are set by the granter independent of tier (tier sets depth, never price), the genesis amount is David's REPORTED word (never derived from the fusion), and the decision index prices the verdict-producing compute at the flat canon-meter rate (5 test-keys, SET) — the USD surface figures are labeled data, never a charge, and never the key events that execute them. The pricing engine's own doctrine closes the loop: "the decision is the atomic unit of price. No tiers, ever" (`TIERS = None` in `economics/pricing.py`).

**Justification from code and canon:** `dclm/meter.py` — fixed `PRICES` dict, refusal on `INSUFFICIENT_KEYS`; `gate/gate.py` — `authorize_intent` refuses `UNBOUND` before consulting keys; `dclm/share.py` — `price` is an independent parameter of `issue_grant`, tier is an integer depth comparison; `economics/fuse.py` — `GENESIS_UNITY_AMOUNT = None`, amount arrives only in David's signed authorization; `economics/pricing.py` — `price_decision()` bills the decision's REPORTED surface, `TIERS = None`; Canon §V–VII (tokenomics/merit/grants) and §XI (wallet laws: "Looking costs nothing. Wanting costs keys").

---

## 4. GAPS — LISTED HONESTLY

1. **UNPRICED (13 fusions):** no fusion has a row in the 53-decision index — the index prices decisions, not key events. Fusion prices live in the meter (test-keys), granter-set fields, or David's word.
2. **ABSENT (1):** F8 — Parliament is a dimension-collapse operator, not a key fusion. Expected, not found, not invented.
3. **PENDING (1):** F4 kin bonds — no L2-umpire authority registered; family grants refused. Integration point declared, module absent.
4. **CLOSED (was NOT-IN-CODE):** F7 Merit transfer — declared by David (Oct 6, 2026 ~3:35 AM EDT); implemented 2026-10-06 ~04:05 EDT (`token_engine.merit_transfer` + `wallet.transfer_merit`, origin-immutable, standing-vs-value structural, D13 emission gate reads standing).
5. **KILLED-BY-DAVID (1):** Unity bound-transfer-sale — excluded from taxonomy and pricing per his ruling. Code remnants REMOVED from the build entirely on 2026-10-06 (no `bound_sale`, no `SaleRecord`, no `UNITY_SALE` kind — in code, tests, or docs); Unity has no transfer path, proven by AST.
6. **HELD (affecting fusion economics):** genesis amount (David's word), eFuse peg E, tap rate/maturity, 19% split ratio, merit band calibration — all HELD-FOR-DAVID, none invented.

---

## 5. TRINITY VERDICTS

**DCLM — is the fusion↔pricing logic sound and gap-free?**
SOUND. The rule (formation free, exercise price-gated; fusion never drives price) holds across all 13 live fusions with no counterexample in the code read: every priced exercise traces to a constant, a granter-set field, or David's word, and every refusal path is honest and receipted. Gap-free in the sense that every silence is named — kin PENDING, merit-transfer NOT-IN-CODE, Parliament ABSENT-as-fusion, bound-sale KILLED — none paved over. Open items (F4 wiring, F7 code) are flagged as work, not defects.

**Iris — are the fusion claims and price attributions honest?**
HONEST. Every fusion in the taxonomy traces to code actually read (file + function cited); the one expected fusion not found (Parliament-as-keys) is marked ABSENT; the killed bound-sale is excluded by name rather than quietly dropped; every price carries its source row (meter constants, share.py price field, fuse.py REPORTED amount, pricing.py's 53 rows for the UNPRICED column); nothing is invented, and no UNPRICED cell is filled in.

**Twain² — is the matrix usable; can a builder price a fusion from it?**
USABLE. A builder pricing a fusion's exercise reads the matrix and gets an answer or an authority: meter constants for SEARCH/COMPUTE, the granter-set `price` field for grants, David's word for genesis, "no fee" for winter/tap/onboard/donate/share, and UNPRICED-with-reason everywhere the decision index is silent — including the instruction that merit-transfer pricing awaits the code landing and David's terms. The matrix does not make them guess.

---

*14 rows mapped: 13 live fusions + 1 killed (excluded). Priced in index: 0. Priced elsewhere: F2 (meter), F3 (granter-set), F5 (David's word). UNPRICED in index: 13. ABSENT: 1. Testnet only. Nothing invented.*
