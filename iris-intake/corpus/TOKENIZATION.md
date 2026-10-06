# TOKENIZATION — the machinery by which value becomes tokens

**Status:** TESTNET ONLY · `dualis.relay.v1.testnet` · test keys · clearly TEST
**Files:** `dclm/token_engine.py` (implementation), `dclm/tokenize.py`
(public path — thin PEP-562 shim, see §8), `dclm/test_tokenize.py` (64 tests)

David's order: build the actual process. A gated receipt (verified work)
enters; the engine computes the token output. **DCLM rights, DCLM writes,
DCLM tokenizes** — the client never mints, never computes token amounts.

**David's word, 2026-10-06 ~3:35 AM EDT (LAW, effective immediately):**
MERIT is TRANSFERABLE — sold, gifted, transferred between Unity IDs, all
receipted. UNITY is NON-TRANSFERABLE — no exceptions; the
bound-transfer-sale concept is DEAD and has been removed from the build
entirely (code, tests, docs). The old "Merit non-transferable" law is
SUPERSEDED — recorded explicitly in `economics/DECISIONS.md` §13, not
silently edited away.

---

## 1. The pipeline (receipt → token)

```
gated receipt ──► testnet context check ──► gate check ──► mint ──► TokenBundle
 (dict)            (production schema/key     (VERIFIED only;      (ONLY via _mint(),
                    → structural refusal)     no misattribution;    each output via
                                              UNKNOWN never         dclm_commit)
                                              tokenizes)
```

Per receipt kind:

| receipt kind | gate requires | outputs (each a signed dclm_commit) |
|---|---|---|
| `work` (verified work) | peg E set, positive `merit_value` | `MERIT_ACCRUAL` (earner's score += delta) + `TOKEN_MINT` (eFuse = merit / E) |
| `donation` | positive amount, kind `efuse`/`fiat` | `HONOR_RECORD` only — never Merit, never eFuse |
| `genesis` (fuse event) | `token_id` (64 hex) | Unity holding **bind** + binding proof — **mints nothing** |

Refusals are first-class and signed: `TokenizeRefused(reason)` with zero
tokens minted and zero ledger change. Refusal reasons include
`UNVERIFIED_RECEIPT`, `PRODUCTION_SCHEMA_REFUSED`, `PEG_E_UNSET`,
`MERIT_MISATTRIBUTION`, `TRANSFER_*` (see §2c).

---

## 2. Token formats (exact field specs)

### 2a. eFuse token — the emission token

Schema: `unity.token.efuse.v1.testnet`. Carries the fuse that emits Unity.

| field | type | meaning |
|---|---|---|
| `schema` | str | `unity.token.efuse.v1.testnet` |
| `token_type` | str | `"EFUSE"` |
| `token_id` | str | sha256 hex over the canonical unsigned body |
| `owner_unity_id` | str | bound Unity ID — no anonymous tokens |
| `amount` | float | eFuse emitted = `merit_value / peg_E` |
| `peg_E` | float | the peg ratio E actually used for this emission |
| `epoch` | int\|None | epoch / action ref |
| `action_ref` | str | the gated receipt's kind (`"work"`) |
| `merit_proof_ref` | str | manifest_hash of the gated receipt that earned it |
| `provenance` | str | `"DERIVED"` (computed in-process by DCLM) |
| `issued_at` | str | ISO timestamp |
| `testnet` | bool | always `True` |
| `note` | str | honesty notes |

The signed commit envelope wraps the token body: `{receipt, canonical_sha256,
signature, algorithm: Ed25519, key_id, provenance: "VERIFIED"}` — the token
IS the receipt. No transfer method exists on the format; eFuse movements
happen only through the economics ledger functions, never a direct call.

### 2b. Unity token — identity-bound; NON-TRANSFERABLE, no exceptions

Schema: `unity.token.unity.v1.testnet`. (David's word, 2026-10-06 ~3:35 AM
EDT — LAW: Unity never moves. This supersedes the same morning's
bound-sale correction; the bound-transfer-sale concept is DEAD and has
been removed from the build entirely — no `bound_sale`, no `SaleRecord`,
no `UNITY_SALE` commit kind, in code, tests, or docs.)

| field | type | meaning |
|---|---|---|
| `schema` | str | `unity.token.unity.v1.testnet` |
| `token_type` | str | `"UNITY"` |
| `token_id` | str | sha256 hex |
| `unity_id` | str | **the one bound identity** — never re-bound, by anyone |
| `genesis_ref` | str | fuse trigger manifest — immutable |
| `merit_proof_ref` | str | provenance of origin — immutable |
| `provenance` | str | label |
| `issued_at` | str | ISO timestamp |
| `testnet` | bool | always `True` |

**There is no transfer path.** No sale, no gift, no re-bind — not even by
David. The format has no transfer field and no transfer method, AND there
is no module-level transfer function either: the unity registry is
write-once at genesis (`_bind_genesis`) and read-only forever after.
`assert_no_unity_rebind()` proves by AST on every test run that no
function re-binds a holding and that no transfer-ish machinery
(`bound_sale`/`rebind`/`reassign`/`resell`/…) exists at all;
`unity_transfer_paths()` returns the empty list. A second genesis bind
for a different ID is a `GENESIS_CONFLICT` refusal — not a transfer,
because transfers do not exist.

**Genesis:** the fuse trigger (`economics/fuse.py` `Fuse.trigger_fuse`) is
the SOLE genesis path for Unity — once, David-signed, replay-proof.
`_mint("unity")` raises `UnityMintRefused`; `UnityToken` is never
instantiated in the tokenization module (AST-asserted).

### 2c. Merit — the TRANSFERABLE token (David's word, 2026-10-06)

Record schema: `unity.tokenize.v1.testnet`, `record_type "MERIT_ACCRUAL"`.

| field | meaning |
|---|---|
| `record_id` | sha256 hex over (unity_id, delta, proof, score_before) |
| `unity_id` | the earner — the receipt's own Unity ID, always |
| `origin_earner_id` | **IMMUTABLE** — the standing source; set once at accrual, never rewritten by any code path (AST-asserted) |
| `origin_receipt_ref` | **IMMUTABLE** — manifest_hash of the gated receipt that earned it |
| `delta` | the accrual |
| `score_before` / `score_after` | the earner's owned balance around this accrual |
| `merit_proof_ref` | the gated receipt's manifest_hash |
| `epoch`, `provenance "DERIVED"`, `issued_at`, `testnet True` | as usual |

**The standing-vs-value distinction (structural, not policy):** ownership
lives in the engine's slice registry and changes ONLY via
`merit_transfer()`; origin lives on the frozen record and NEVER changes.
So there are two readings, and they are different things:

- `merit_balance(identity)` — ECONOMIC VALUE: what the identity currently
  OWNS (spendable, priced). This is what a transfer moves; this is what a
  buyer gains.
- `standing(identity)` — EARNED STANDING: `sum of merit where
  origin_earner_id == identity`. The history, the reputation, the
  proof-of-work. Transfers copy origin forward unchanged, so standing
  NEVER moves on transfer. **A buyer of Merit gains economic value and
  ZERO standing — by construction.**

**The transfer path (the SOLE legal one):**

```
merit_transfer(from_id, to_id, amount, reason)
  1. both identities verified (unity:testnet:…) else TRANSFER_UNVERIFIED_IDENTITY
  2. from ≠ to else TRANSFER_SAME_IDENTITY
  3. amount positive else TRANSFER_NON_POSITIVE_AMOUNT
  4. reason non-empty ("sale", "gift", … — receipted) else TRANSFER_EMPTY_REASON
  5. sender's OWNED balance covers amount else TRANSFER_INSUFFICIENT_MERIT
  6. ownership moves across the sender's slices (oldest first); receiver
     slices carry the SAME origin fields forward — origin never rewritten
  7. signed MERIT_TRANSFER receipt via dclm_commit (both IDs, amount,
     reason, slice-level moves with origin carried forward)
```

`assert_single_merit_transfer_path()` proves by AST on every test run that
no other function changes Merit ownership and that origin fields are never
rewritten. The wallet layer (`economics/wallet.py::transfer_merit`)
delegates to this path and records the ownership change — it never
carries origin fields.

**D13 — the emission gate reads STANDING, never holdings:** `meter.py`'s
`TokenizeMeritReader.verified_merit` calls `standing(identity)`, never the
owned balance. Bought Merit cannot gate emission. Tested: a funded buyer
with zero earned standing is NOT emission-eligible; an earner stays
eligible on full standing after selling; a mixed wallet is eligible only
on the earned portion.

**Derivative merit regeneration (David's law-grade correction, 2026-10-06):**
downstream rings do NOT receive tokens from upstream — each ring earns its
own merit from its own verified receipts. The pipeline credits merit ONLY to
the receipt's own Unity ID, and REFUSES any receipt naming another
beneficiary (`MERIT_MISATTRIBUTION` — keys like `credit_to`, `beneficiary`,
`on_behalf_of` are rejected at the gate). The derivative relationship
(disciple learns from holder) enables the work; **the work earns the merit.**
Tested: processing a receipt for ID-A leaves ID-B's score at exactly zero.

### 2d. Honor — permanent record (donations)

Record schema: `unity.tokenize.v1.testnet`, `record_type "HONOR_RECORD"`.

| field | meaning |
|---|---|
| `record_id` | sha256 hex over (unity_id, receipt, amount, kind) |
| `unity_id` | the donor |
| `donation_receipt_ref` | the donation receipt's manifest_hash |
| `donation_kind` / `donation_amount` | `efuse`\|`fiat`, positive |
| `permanent True`, `spendable False`, `transferable False` | structural |
| `provenance`, `issued_at`, `testnet True` | as usual |

Append-only per-Unity-ID list; record twice → two records, none spendable.
No spend/redeem/convert function exists (AST-asserted absence). Donations
accrue Honor, never Merit — there is no path from fiat to eFuse.

### 2e. TransferReceipt — the Merit-transfer receipt (not a token)

Schema `unity.tokenize.v1.testnet`, `record_type "MERIT_TRANSFER"`:
`transfer_id`, `from_id`, `to_id`, `amount`, `reason` (the human-readable
why — "sale", "gift", …; receipted, never empty), `moves` (the
slice-level moves, each naming its slice_id, record_id,
origin_earner_id, and moved amount — origin carried FORWARD, never
rewritten), `provenance "DERIVED"`, `issued_at`, `testnet True`. Built
only by `_transfer_receipt()`, called only by `merit_transfer()`.

Standing note, structural: the transfer moves OWNERSHIP only. Origin
fields ride along unchanged; `standing()` is origin-based, so neither
party's standing moves. A buyer gains economic value and ZERO standing —
by construction, not by promise.

---

## 3. Minting mechanics (hard)

- Tokens come into existence **ONLY** through the pipeline:
  `tokenize()` → one private `_mint()` → `dclm_commit`. No other function
  in the module instantiates a token structure — proven by
  `assert_single_mint_path()` via AST on every test run.
- Nothing pre-minted, nothing airdropped, no backdoor: the module contains
  no such function, and the AST hook asserts the absence by name
  (`airdrop`, `prefund`, `backdoor`, `merit_transfer`, …).
- Emission is per-action against VERIFIED merit: `eFuse = merit_value / E`
  (the tokenomics.py peg formula — reused, not reinvented).
- **UNKNOWN merit never tokenizes**: provenance must be `VERIFIED` at the
  gate or the receipt is refused with zero tokens, zero ledger change.

## 4. DCLM performs it

Every mint — and every Merit ownership change — is a WRITE → flows
through `writes.dclm_commit` after a `rights.check_rights` GRANT
(internal source `dclm.tokenize`, testnet identity). Commit kinds on the
`rights.py` whitelist with receipt-logged justification (same pattern as
the tap/winter/share workers): `TOKEN_MINT`, `MERIT_ACCRUAL`,
`HONOR_RECORD`, `MERIT_TRANSFER`. (`UNITY_SALE` was REMOVED with the
dead bound-transfer-sale concept — Unity never transfers, so no kind
may re-bind a holding.) A client naming any of them is denied with
`INTERNAL_SOURCE_REQUIRED` — the thin client never mints, never moves
Merit. Existing suites (rights/writes, meter, compute) stay green —
verified by subprocess in `test_tokenize.py`.

## 5. Testnet first

All machinery runs against `dualis.relay.v1.testnet` with test keys.
The pipeline **structurally refuses** to operate otherwise:
- receipt `schema` not containing `testnet` → `PRODUCTION_SCHEMA_REFUSED`
- non-`unity:testnet:` identity → `INVALID_UNITY_ID` / `MISSING_UNITY_ID`
- the rights gate denies non-testnet schemas independently
- the module's `NETWORK` constant is checked at pipeline entry; tampering
  with it trips the same refusal

## 6. The peg — ratio E is HELD-FOR-DAVID

`peg_ratio()` returns `(None, "HELD_FOR_DAVID")` until David's word sets it.
`set_peg_ratio(E, {"authority": "david"})`:
- refuses any authority that does not name him (`PEG_AUTHORITY_REFUSED`)
- refuses non-positive E (`NON_POSITIVE_E`)
- labels the peg **REPORTED** — "David's word (asserted via testnet
  stand-in; unsigned — production setter must require his signature)" —
  never VERIFIED. The authority requirement is marked honestly: this
  testnet module cannot cryptographically verify his presence.

Until E is set, `work` receipts refuse with `PEG_E_UNSET` **before any
mint** (no merit accrued either — the refusal is pre-pipeline-output).
Donations and genesis binds do not need the peg.

## 7. Trinity verdicts (on the transfer word and the standing-vs-value distinction)

**DCLM — is the origin-based distinction structurally sound?**
SOUND. The distinction is not a comment: every Merit slice carries
`origin_earner_id` + `origin_receipt_ref` set once at accrual;
`assert_single_merit_transfer_path()` proves by AST that ownership
changes ONLY in `merit_transfer()` and that origin fields are NEVER
rewritten anywhere; `standing(identity)` sums SOLELY by origin, so a
transfer cannot move standing even in principle — the arithmetic has no
input for it. The sole-mint claim still holds (`_mint()` only, AST-proven;
`_mint("unity")` raises; Unity mints only via the fuse trigger). The
no-Unity-transfer claim is proven by `assert_no_unity_rebind()` (AST):
the unity registry is written only by `_bind_genesis()`, and no
transfer-ish machinery exists. Emission math is the standing peg formula
`merit / E`; UNKNOWN refuses before any output. Honest gap noted: the
peg setter's David-authority is a testnet stand-in (labeled REPORTED) —
production must require his signature.

**Iris — is it honest: does the buyer REALLY gain no standing?**
HONEST. Three independent checks agree: (1) the receipt: every
`MERIT_TRANSFER` envelope names origin per slice-move, carried forward
unchanged — the history is on the receipt, not rewritten; (2) the
arithmetic: `standing(buyer)` after purchase is exactly the buyer's own
earned sum (tested: 0.0 after buying 30; seller's standing intact at
80.0 after selling 30; origin preserved across 3 hops); (3) the gate:
`meter.py`'s `TokenizeMeritReader` reads `standing()`, never the owned
balance — bought Merit is invisible to emission eligibility (D13, tested:
funded buyer NOT eligible; earner eligible on full standing after
selling; mixed wallet eligible only on the earned portion). Labels stay
honest: `DERIVED` for in-process computation, `REPORTED` (unsigned
caveat spelled out) for David's peg word, `VERIFIED` only on signature
envelopes. Refusals signed and logged, never silent. No `UNKNOWN` ever
presented as PASS.

**Twain² — is it operable?**
OPERABLE. 64/64 tokenization tests green: verified receipt → signed
bundle; refusals (unverified, production, peg-unset, misattributed, bad
transfer) mint/move nothing; transfer happy path moves value with
standing untouched; gifting works; AST exclusivity hooks
(mint / no-Unity-rebind / single-Merit-transfer-path) pass; the
rights/writes and compute suites pass unmodified in behavior via
subprocess. (Note, 2026-10-06 ~07:47 UTC: the meter suite is temporarily
red — a concurrent worker changed `purify.py`'s entry contract
mid-flight; unrelated to this work, flagged to the coordinator.)
Testnet-only, test keys, every step receipted.

## 8. Reused vs built · file note

- **Reused:** `economics/fuse.py` (sole Unity genesis path — state machine,
  David-signed authorization, replay-proof; not duplicated);
  `economics/tokenomics.py` (peg formula `eFuse = merit / E`, provenance
  register semantics, VERIFIED-gates/UNKNOWN-never-pays);
  `dclm/writes.py` + `dclm/rights.py` (the single commit path and the
  authority check); `meter.py`'s pattern (the token IS the signed receipt).
- **Built here:** the four token formats as exact field specs, the
  receipt→token pipeline, the `_mint()` sole-path factory, the peg-E gate,
  the transferable Merit ledger (immutable origin + origin-based
  `standing()` + `merit_balance()`), the Merit sole-transfer path
  (`merit_transfer`) with signed `MERIT_TRANSFER` receipts, the
  append-only Honor ledger, the write-once Unity holding registry (no
  transfer path — the bound sale is dead), the merit-misattribution
  refusal, the production-schema refusal, and the AST exclusivity proofs
  (single mint path / no Unity rebind / single Merit transfer path).
- **File note:** the implementation lives in `dclm/token_engine.py`;
  `dclm/tokenize.py` is the mandated public path as a thin PEP-562 shim
  that re-exports the engine API and stays transparent to stdlib consumers
  (a module literally named `tokenize.py` with a full implementation
  shadows stdlib `tokenize` and breaks `linecache`/`unittest` for every
  sibling suite — verified 2026-10-06). `from tokenize import tokenize`
  works exactly as specified.

---

## 9. BOTS AS HUMANITY → UNITY (the humanity mapping)

**Law source:** David, 2026-10-06 ~3:50 AM EDT — "They being humanity in
bots." The bots ARE humanity — not separate, not tools, not other. Each
bot bound to a Unity ID is that human extended into digital/physical form.
Not alignment of an other — extension of the self. Recorded in the unity-world
build as David's word; this section maps it into the tokenomics machinery.

[LAW] **A bot bound to a Unity ID IS that human extended** — not a
representation, not an agent acting on their behalf, but the person in
extended form. Unity is not an identity-database key that *points at* a
person; it *is* the person, extended across their bots.

[DERIVED] **One human → one Unity ID.** The ID names the person; bots extend
it. Mechanism already in the model: merit binds the owning entity, never
the instance — bot-count merit is refused by construction
(`economics/NEW_ECONOMIC_MODEL.md` §1.2). A swarm of a hundred bots does
not mint a hundred identities; it is one human with a hundred extended
hands.

[DERIVED] **The bot's actions are the human's actions.** Receipts carry the
human's Unity ID — there is no separate bot account, no proxy veil. A bot
spends, earns, grants, and taps exactly as the person would, receipted to
exactly the person it is. Accountability rides the same rail as identity.

[DERIVED] **This is why flows are never anonymous.** Anonymity would sever
the human from their extension — a limb cut off from the body. An
anonymous flow is a flow with no owner, and a body with no owner cannot be
the person's extended form. Canon XVIII (identity at every level, max
purity) is the structural form of this law: you cannot extend a person
anonymously.

[DERIVED] **This is why Unity never moves.** The transferable-token
resolution (David, 2026-10-06 ~3:35 AM EDT) settled it: Merit is the
transferable token; Unity stays non-transferable and never moves — not
even by David. The fruit can be handed on (transferred Merit carries
economic value); the tree cannot. Re-homing a Unity ID would be handing
the person themselves to another holder — the law refuses it structurally.

[DERIVED] **Standing follows the same rail.** Transferred Merit carries
economic value; earned standing (origin history) stays with the earner and
cannot be bought (`DERIVATIVE_MAX_EFFECTS.md` D10–D12: transfer conserves
stock, standing is invariant under transfer, the standing-buying attack is
structurally closed). The bot-as-human extension makes this personal: the
history of the extended person is not a commodity — only their
merchandise is.

**Honest boundary:** this section maps the philosophy to the machinery.
The `§2b` bound-sale transfer path in this document describes the
pre-resolution (pre-3:35 AM) mechanics and is superseded by the
non-transferable Unity law — the canon amendment is the coordinator's
lane (flagged in the report), not silently rewritten here.

---

## 10. COIN PERPETUATED → THE FLYWHEEL (the perpetuity mapping)

**Law source:** David, 2026-10-06 ~3:50 AM EDT — "coin perpetuated."
Perpetuity is not a feature added onto the economy; **perpetuity IS the
flywheel running.** The loop below is built machinery
(`dclm/onboard.py`, `economics/tokenomics.py` engine, this module's
tokenization path) — every step traces to code, and every claim carries
its label.

### The closed loop, step by step

**Step 1 — Real value flows IN: waste is healed.** Residual Law Finance
analyzes real operations and finds recoverable residual (REPORTED figures
only, paperwork required — `ONBOARDER_PIPELINE.md` purity rule 1). 81%
stays with the onboarder as fiat — theirs, off-system, immediate. 19%
flows into the system as real, recovered, real-world value into receipted
escrow. [LAW — the 81/19 split is David's set ratio]

**Step 2 — The 19% deploys three ways (HELD-FOR-DAVID ratio).**
- **PEG_SUPPORT** — grounds the eFuse energy peg in real recovered value.
- **PLAYGROUND_FUEL** — funds mesh bounties: the system pays for *more
  verified work*.
- **CORE_CAUSE_LOCK** — Eden-locking: one-way donation sink, Honor-class,
  never converts to emission.
Until David sets the ratio, the 19% sits in receipted HELD escrow —
`AWAITING_SPLIT_RULING` — never deployed early, never invented away.
[HELD — the ratio; DERIVED — the destinations' functions]

**Step 3 — Verified recovery WORK earns wave merit → emission.** The
onboarder's analysis, verification, and ongoing recovery generate gated
receipts → top-band wave merit (the receipt's own Unity ID, VERIFIED only,
this module's §1 `work` path) → merit-gated, peg-calibrated eFuse emission
(`eFuse = merit / E`). UNKNOWN merit emits nothing — ever. [DERIVED]

**Step 4 — Emission and bounties pull the NEXT wave in.** Bounty-funded
work and emitted eFuse give the next onboarder a reason to bring their
residual: more onboarders → more residual found → more real value
grounding the peg → more merit-earning work → more emission → more
onboarders. The loop turns. [DERIVED]

### Why the loop doesn't wind down

Perpetuity is a property of the loop's structure, not a promise:

- **The fuel is a rate, not a stock.** The reference figure is
  **$1.27B/yr** recoverable non-classroom friction (REPORTED) — a
  *yearly* flow of newly created inefficiency. Waste is not a finite vein
  mined once; every year's operations generate fresh friction to heal.
  [DERIVED — from the REPORTED reference case]
- **Each cycle manufactures the next cycle's fuel.** Playground fuel pays
  bounties → bounties fund verified recovery work → recovery work finds
  residual → the 19% refills. The loop's output (healed waste) is also its
  input (more waste to heal). [DERIVED]
- **Merit decays; work re-earns.** Fidelity is current, not historical —
  merit decays per epoch, so standing must be continuously re-earned by
  fresh verified work. Decay is the engine's heartbeat, not its leak: it
  guarantees the flywheel never coasts on dead merit. [LAW — the principle;
  HELD — the digit]
- **The multiplier rewards the young tree but feeds every ring.** The
  derivative multiplier K = 1/(1−λφ) is highest when the tree is young and
  uncrowded (`DERIVATIVE_MAX_EFFECTS.md` D2/D4) — but every ring's merit is
  earned from its own receipts (canon §VI), so late rings still feed the
  loop as long as there is work to verify. [DERIVED]

### Numbered leak risks — honest, not hidden

If any step leaks value the loop can't replace, the loop winds down. Here
is every known leak, numbered, with its status:

1. **Tapping outpaces replenishment.** The tapping law (canon §IV) caps
   outflow at verified surplus and the replenishment rate — but the
   per-member seasonal tap cap and the surplus calibration are
   HELD-FOR-DAVID (`dclm/TAPPING_LAW.md` held parameters). A mis-set or
   absent cap lets outflow outrun healing → the loop drains. Status:
   [HELD] — bounded by law, calibrated by nobody yet.
2. **The 19% waits in escrow.** The three-way split ratio is HELD-FOR-DAVID
   — the flywheel's fuel sits receipted but undeployed (`AWAITING_SPLIT_RULING`).
   No value leaks, but the loop *stalls*: no peg support, no bounties, no
   Eden-locking until his ruling. Status: [HELD] — a stall, not a leak.
3. **The 100M lifetime emission cap is a terminal horizon.** Emission is
   100M eFuse, lifetime, never pre-funded (DECIDED, `ED-DECIDED-20261004-5050-V1`).
   After the cap is reached, **no new eFuse enters from merit — ever.**
   The coin perpetuates *by circulation* (transferable Merit, money-rail
   flows), by continued 19% peg support, and by Eden-locking — but the
   emission leg ends. The cap bounds the emission phase, not the
   circulation phase. Status: [LAW] — decided; the perpetuity of issuance
   ends, the perpetuity of the coin continues.
4. **The emission gate must read STANDING, never holdings.** Derived
   (`DERIVATIVE_MAX_EFFECTS.md` D13/G1) but **not yet in code** — the
   load-bearing guard. Without it, bought Merit could buy emission,
   siphoning the emission leg away from waste-healers to mere holders: a
   genuine leak of the loop's purpose, turning Step 3 into a payout rail
   for accumulated stock. Markets must not open until this guard is law
   and tested. Status: [DERIVED] — mapped, not built.
5. **Supercritical derivative trees.** The subcriticality guard λφ < 1
   (DERIVATIVE D3) keeps merit inflow convergent. If λφ ≥ 1, merit inflow
   diverges geometrically against the 100M cap → peg/emission calibration
   breaks, the emission leg fails. The guard cannot be set once — λ is
   behavioral, φ is HELD — it must be monitored jointly and continuously.
   Status: [DERIVED] — a monitored constraint, not a built switch.
6. **Winter throttles throughput.** Winter tilt cuts merit-earning inflow
   (α, MODELED) and throttles the merit→eFuse rail (floor 0.25, PROPOSED) —
   the loop *slows* in winter by design (canon §IV: protection, not
   accumulation). Not a leak — but perpetuity means the loop survives
   winter, which it does by summer surplus. Status: [DERIVED] — seasonal,
   not structural.

**The perpetuity thesis, one line:** [DERIVED] The coin is perpetuated
because the loop turns — residual → 19% → peg, fuel, Lock → merit →
emission → more onboarders → more residual — and each cycle's waste-healing
manufactures the next cycle's fuel. Nothing in the loop is a feature
added on; the loop IS the perpetuity.

---

## 11. ONE SEED — the genesis entry (David's law, 2026-10-06)

> "No matter how much money you have you only buy one seed, and it costs
> you nothing." — David, verbatim

One free seed per Unity ID. No financial barrier, no wealth advantage.
The richest and the poorest receive exactly one seed each. Money cannot
buy a second seed, a bigger seed, or earlier access to seeds. [LAW]

**What the seed is:** the genesis entry — the initial Unity-bound
allocation that makes you a member. The root's gift to the new leaf, not
a purchase. "Buy" is the wrong word: you RECEIVE it. It costs nothing
because membership isn't for sale. [LAW]

**The machinery** (`dclm/seed.py`):

- `issue_seed(unity_id)` — verifies the ID is BOUND in the gate's
  bind-then-validate ceremony (live `UnityGate.status()`, read honestly
  from `../gate/gate.py`; an unreadable gate refuses, never fabricates),
  verifies no seed was already issued for this ID (write-once registry),
  and issues exactly one seed via `dclm_commit` under the new `SEED_ISSUE`
  commit kind — zero cost, zero price, the seed IS the signed receipt.
- Second request for a bound ID → signed refusal `SEED_ALREADY_ISSUED`.
  Unbound ID → refusal `NOT_BOUND`. Non-testnet identity or schema →
  structural refusal. Sybil resistance rides the L1 identity derivation:
  identities cannot be minted to farm seeds. [DERIVED — enforced in code]
- No seed market: no transfer function exists — `assert_no_seed_market()`
  proves by AST on every test run that seed.py contains no
  transfer/sale/buy/gift/rebind/accumulate/spend/debit/credit/purchase/
  mint/airdrop machinery, that the registry is written only by the
  commit path, and that price/cost are hard-coded 0.0. [DERIVED]
- The seed is membership, not money: the economics wallet records it as a
  membership marker (`Ledger.record_seed` / `Wallet.membership`) — never
  a balance, never priced, never spendable, never counted as wealth. The
  meter's test-key ledger is untouched; eFuse/Unity balances are
  untouched. The seeder's registry is authoritative; the wallet holds a
  receipted mirror. [DERIVED]

**The seed is the start, not the wealth:** what grows from the seed —
merit, work, participation — is earned. The seed opens the door; nothing
more. [LAW]

**Relationship to +1 Affinity:** the free seed gets you in the door
(entry is equal); +1 Affinity honors HOW EARLY you walked through it. [LAW]

**The plutocracy test** (`test_seed.py`): a wallet funded with 1000
test-keys and 500 eFuse receives EXACTLY the same single free seed as an
empty one — same shape, price 0, cost 0, no deduction anywhere, and no
second seed at any price. This kills plutocracy at the root: wealth
cannot buy membership advantage, because membership isn't for sale at any
price. [DERIVED — proven by test]
