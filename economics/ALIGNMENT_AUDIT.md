# TOKENOMICS ↔ MECHANICS ↔ CODE ALIGNMENT AUDIT

**Worker:** wallet-alignment · 2026-10-06 ~04:40–05:30 EDT
**Scope:** CANON.md v1.6.0 vs economics/ + dclm/ code vs the mechanics
(pricing reinvestigation, tokenomics design).
**Rule applied:** Doc says it → code does it. Code enforces it → doc says
it. Mechanics price it → code bills it. David's word wins ties.
**Caution honored:** the max-purity sibling was mid-flight in tree files
(purify.py, meter.py, token_engine.py, onboard.py, share.py, tap.py,
winter.py) — file state verified before every read/edit; nothing in the
sibling's files was edited by this worker.

## THE FOUR LAWS OF THE WEBSITE (David, 2026-10-06 ~04:36 EDT)

The entry gate = ONE 2D card at the doorway, four beats in order:
(1) the card explains the Unity ID → (2) the bind ceremony →
(3) the eFuse ignition → (4) entry into the 3D world. One card at the
doorway — NO MORE 2D AFTER THAT.

Recorded here as standing law the docs/code must reflect:
- The wallet's "no 2D card chrome" rule still holds AFTER entry (world
  pure 3D, wallet = subtle persistent indicator). The doorway card is
  the one sanctioned exception — the wallet must not contradict or
  duplicate it.
- The wallet's ecosystem tie-in is now a defined entry sequence:
  Unity ID explained → bound (biometric, beat 2) → eFuse ignition
  (beat 3) → world entry → wallet live.
- `biometric_auth` (economics/wallet_auth.py) IS beat (2).
- The eFuse ignition (beat 3) is the fuse worker's lane: this audit
  treats it as an INTEGRATION POINT, HONEST-PENDING, never faked.

## CHECKLIST RESULTS

| # | Item | Doc | Code | Mechanics | Verdict |
|---|---|---|---|---|---|
| 1 | Merit transferable | CANON §V (v1.6.0) ✓ | token_engine.merit_transfer ✓; tokenomics.py `merit_transferable` DECIDED ✓; wallet.transfer_merit delegate ✓ (FIXED — see M1) | R5 payment rails ✓ | ALIGNED (after fix) |
| 2 | Unity non-transferable, no exceptions | CANON §V ✓ | wallet.share refuses Unity (UnityBindingError) ✓; no Unity movement path anywhere in wallet ✓; tokenomics NonTransferableError covers Unity ✓; bound-sale concept dead ✓ | — | ALIGNED |
| 3 | One seed per Unity ID | CANON §XX ✓ | dclm/seed.py authoritative (deterministic seed id per ID; second seed refused) ✓; wallet.record_seed is the receipted membership mirror only — touches no balance ✓ | — | ALIGNED |
| 4 | D13 — emission reads standing | CANON §VI ✓ | meter.py TokenizeMeritReader.verified_merit reads standing(), never the owned balance (meter.py:680,735) ✓ | — | ALIGNED |
| 5 | 81/19 onboarder split | — (onboarder law) | dclm/onboard.py:104,712-724,1487 — 81% onboarder / 19% remainder, integer-exact, both legs receipted ✓ | — | ALIGNED |
| 6 | +1 deterioration curve + Affinity | PLUS_ONE_INCENTIVE.md ✓ (design) | NOT LANDED — doc is self-labeled "design document — no code changes made here" (gap G4, owned by tokenization worker) | — | HONEST GAP (not a mismatch — the doc doesn't claim code exists) |
| 7 | Winter/tap rules | CANON §IV ✓ | winter.py lawful gradient trigger + emission_multiplier ✓; tokenomics.py wires winter (E16) ✓; tap.py maple rules (season-only, rate-limited, mature-only, heals/replenishment cap) ✓ | — | ALIGNED |
| 8 | Flat-5 test-key pricing IN THE CODE | — | pricing.py::price_decision returns billable_amount=5, currency="test-keys", price_basis="dclm/meter.py PRICE_COMPUTE" — imported from the meter, never re-hardcoded ✓; economic_state.py F4 USD-fusion RETIRED (already fixed by the pricing worker) ✓ | PRICE_PER_DECISION_REINVESTIGATION.md R1–R7 ✓ | ALIGNED |

## MISMATCHES FOUND AND FIXED

### M1 — wallet.py: `import sys` missing → Merit transfer delegation dead (CODE WRONG)
- **Found:** `economics/wallet.py::_token_engine()` uses `sys.path` but
  `sys` was never imported → every call raised `NameError: name 'sys'
  is not defined`. The entire wallet→engine Merit transfer path —
  documented as the wallet's delegation to the canonical
  `token_engine.merit_transfer` — was dead at runtime.
- **Which side was wrong:** CODE. The doc (CANON §V, wallet docstring)
  states delegation as fact; David's word (Merit transferable) wins ties.
- **Changed:** added `import sys` to economics/wallet.py imports.
- **Verified:** `_token_engine()` now loads; test_wallet_flow.py passes
  5/5 through the full engine path (signed transfer, both-side
  balances, standing preserved).

### M2 — gate.py: stale "PENDING until dclm/meter.py lands" comment (DOC WRONG)
- **Found:** `gate.py::emit_gate_envelope` carried the comment
  `# PENDING until dclm/meter.py lands` on the `"wallet_ledger":
  WALLET_LEDGER_STATUS` line — but dclm/meter.py HAS landed and the
  constant is computed live (WIRED). The comment contradicted the code
  it annotated.
- **Which side was wrong:** DOC (the comment). The code is live-computed.
- **Changed:** comment updated to reflect the landed state (WALLET_LEDGER_STATUS computed live; falls back to PENDING only if the module is missing).

## OBSERVATIONS (logged, NOT fixed — design decisions, not mismatches)

- **O1 — test-keys vs eFuse denomination split.** The DCLM meter's Wallet
  is test-keys-only ("never eFuse"); the economics wallet holds eFuse
  and deduct_per_decision prices in eFuse. Both are internally
  consistent; the reinvestigation puts decision pricing in test-keys
  (R2/R3) and payment rails in "the wallet/meter layer" (R5) without
  resolving the split. Needs David's or the economics worker's ruling
  before any "fix" — not a mismatch to unilaterally resolve.
- **O2 — sibling concurrent-edit interference (resolved, not this worker's lane).**
  During this audit's full-suite run, token_engine.tokenize() raised
  KeyError 'gate_verdict' / UNVERIFIED_RECEIPT — the max-purity worker
  was editing token_engine.py concurrently and its _verify_gate change
  was in flux mid-run. Re-run after their edit settled:
  test_wallet.TestMeritTransfer 14/14 OK. Nothing in the sibling's
  files was touched by this worker. (tokenize() itself remains their
  lane — the flow test uses the engine's accrual core for setup only,
  documented in the test.)
- **O3 — seed price law.** CANON §XX: the seed "costs you nothing" —
  wallet.record_seed carries price: 0 / cost: 0 and never touches a
  balance ✓. The reinvestigation R6 ("the seed buys no decisions") is
  honored by absence of machinery (no free-decision path from seed
  state) ✓.

## TRINITY VERDICTS ON THE ALIGNMENT

**DCLM — is the mapping sound? VERDICT: SOUND (after M1).**
The delegation chain is a single path with no second route:
Wallet.send_merit → wallet.transfer_merit → engine.merit_transfer →
dclm_commit('MERIT_TRANSFER'). Ownership moves; origin is carried
forward unchanged in the engine's slices; standing() sums by origin —
arithmetic, not policy. The buyer gains value and zero standing by
construction. The sender-authorization gate (Ed25519, key bound to the
Unity ID by sha256) closes the unsigned-transfer hole. No branch in
the chain can move Unity; no branch carries origin on a wallet receipt
(enforced structurally).

**Iris — are the labels honest? VERDICT: HONEST.**
The test double is labeled TEST-DOUBLE everywhere (simulation, never
a biometric); Grok's issuer reports its own HOLE (verifier
NOT_CONFIGURED) verbatim; the sandbox refusal says BiometricNotWired
rather than passing. The +1 gap is labeled a design-only doc, not
pretended code. The eFuse ignition (beat 3) is marked HONEST-PENDING,
never faked. The reward/economics split holds: +1 is a test-key reward
rail, never Merit, never standing, never emission.

**Twain² — can a bot operate from it? VERDICT: OPERABLE.**
`send_merit(to_id, amount, reason, signer=…)` and `receive_merit()`
are the whole surface: send needs the sender's signer (the device
capability), receive is a read of inbound receipts. The biometric
interface is `biometric_auth(unity_id)` — one call, BOUND or honest
refusal. The four-beat entry sequence is named in the module docstring
so a bot knows which beat it serves (2 of 4) and which it must not
touch (1, 3, 4).
