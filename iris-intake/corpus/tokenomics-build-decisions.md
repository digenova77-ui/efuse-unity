# Tokenomics Engine — build decisions (Trinity lens)

Worker 2 of the unified WORLD build (Tokenomics Core), Oct 6, 2026.
Implements `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md`
(DESIGN, predicted not sealed). Testnet only.

Each build decision was run through the three gates. **DCLM** = logic
(the rule must hold). **Iris** = truth (no fabricated claims).
**Twain²** = pragmatism (the simplest thing that actually works).

## 1. Held parameters refuse instead of placeholder — DCLM/Iris
**Logic:** a held parameter with a guessed default is decree before evidence.
Refusal (`HeldParameterError`) is the only move that keeps the gate honest —
the mechanic cannot run, so it cannot mint on invented digits.
**Iris:** no unsigned claims enter the books; a bare number is treated as
UNKNOWN, and UNKNOWN never pays. **Twain²:** one exception type, one
`require_decided` helper, clear messages. Outcome: **refuse, never invent**.

## 2. Conversion rate = 1/E, merit in energy-equivalent units — DCLM/Iris
**Logic:** the peg says 1 eFuse ≡ E energy units. The unique conversion where
the peg holds *by definition* (emission's energy value = merit's energy value)
is eFuse = merit / E. Any looser rate would need the Reserve to defend the
peg; the definitional rate cannot break it.
**Iris:** the rate IS the peg — posted on every emission receipt, no hidden
multiplier. Honest residual, flagged: human social merit isn't literally
energy; its energy-equivalence lives in the merit *weights* (tier weights are
HELD_FOR_DAVID), so the conversion stays pure while the valuation stays his.
**Twain²:** one division. Outcome: **rate = 1/E**.

## 3. Enforcement by absence of machinery — DCLM
**Logic:** a rule can be waived, reinterpreted, or forgotten; a missing
function cannot be called. Pool-to-pool, mesh minting, merit interest, and
fiat→eFuse are not forbidden — they are *unbuildable* here. The test suite
scans for their names so they cannot creep back quietly.
**Iris:** nothing to hide behind — the absence is inspectable.
**Twain²:** less code than a permission system. Outcome: **absence, not policy**.

## 4. Explicit HonorConversionRefused — Iris/DCLM
**Logic:** donation→merit→eFuse was the obvious gameable design; naming the
refusal (`Honor.redeem_for_emission` raises) kills the temptation where it
would be proposed, instead of relying on nobody noticing the missing path.
**Iris:** the brightest line in the tokenomics is drawn in code, with the
reason attached. **Twain²:** one method. Outcome: **named refusal**.

## 5. Merit accrual needs VERIFIED receipt + explicit weight — DCLM/Iris
**Logic:** "no receipt, no coins" is the gate; REPORTED is a claim, not a
gate-pass, so only VERIFIED receipts accrue. Weight bands are held, so the
caller supplies the weight explicitly *with its provenance* — the engine
never invents one.
**Iris:** the merit event says exactly why it accrued (receipt id + weight
provenance on the credit). **Twain²:** the receipt is the idempotency key too
— same receipt twice is refused by `manifest_hash`. Outcome: **gate in code**.

## 6. Donor exclusion: Lock is one-way per donor — DCLM
**Logic:** the donate→re-earn loop dies by construction: any member with
donated eFuse in the Lock is refused `cause_disburse`. A donor may still earn
by *doing* cause-work — but from pool emission (F1), never from the Lock.
**Iris:** the exclusion is a raised error with the reason, not a silent drop.
**Twain²:** one dict lookup. Outcome: **one-way per donor**.

## 7. Idempotency via manifest_hash + hash-chained receipts — DCLM/Twain²
**Logic:** L5's hunt (phantom receipts, double-apply) becomes a set lookup:
`manifest_hash` over canonical content, applied once. The chain (`prev_hash`)
gives tamper-evidence; epoch summaries are sealed by the orchestrator with
`dclm.compute.sign_state` — not reimplemented here (see 8).
**Iris:** RELAYED ≠ DELIVERED — a receipt that isn't applied isn't a movement.
**Twain²:** a set and a sha256. Outcome: **hash-chain + idempotency set**.

## 8. No signing reimplementation; no crypto surface — Twain²/DCLM
**Logic:** worker 1 built Ed25519 sealing (`dclm/compute.py::sign_state`,
testnet keys). A second signing implementation is new cryptographic surface
to get wrong. The ledger exposes `state_digest()`; the orchestrator seals it.
**Iris:** key material never enters this module. **Twain²:** reuse, don't
rebuild. Outcome: **digest here, seal elsewhere**.

## 9. Provenance labels mirrored, not imported — Twain²/DCLM
**Logic:** importing `dclm.compute` would drag the ring/Parliament import
chain into the economic core. The five labels are a stable register; mirroring
them keeps the engine dependency-free, and the test suite asserts the sets
are identical to `compute.PROVENANCE_LABELS` — divergence fails loudly.
**Iris:** the alignment is verified, not assumed. **Twain²:** zero imports.
Outcome: **mirror + assert**.

## 10. Member eFuse balances not tracked here — Iris (honest boundary)
**Logic:** disbursements are recorded as receipts; a wallet/UTXO balance is
the wallet worker's surface (honest WATER §14: the full wallet build is
unbuilt). Tracking half a balance here would be a claim the engine can't
defend.
**Iris:** the boundary is stated in the module docstring and here, not hidden.
**Twain²:** receipts are the ledger; balances derive elsewhere. Outcome:
**receipts here, balances elsewhere**.

## 11. Testnet what-if runs stay labeled MODELED — Iris
**Logic:** refusing *everything* until David decides would make the engine
untestable; inventing digits would be decree. The middle path: explicitly
labeled MODELED inputs run the machinery and produce MODELED outputs —
a model, never presented as decided.
**Iris:** the label travels with the figure; nothing modeled renders as
verified. **Twain²:** the same code path, honest labels. Outcome: **MODELED
in, MODELED out**.

## 12. Unity non-transferable — David's word, 2026-10-06 ~3:05 AM EDT (LAW)

**David decided:** "make the wallet logically pure" — Unity is non-transferable
between wallets, and the law now says so (`WALLET_DESIGN_LAW.md` §7).
**Logic:** Unity IS the member; a membership cannot change hands. This closes
the loop — Merit, Honor, and now Unity are all identity-bound and
non-transferable. Nothing identity-bound ever moves between identities.
**Iris:** the code already enforced it (`wallet.py` — the transfer path does
not exist); the law now matches the code, no gap. **Twain²:** one rule, no
exceptions, not even for David. Outcome: **law changed, code already pure**.

## 13. SUPERSESSION — Merit is TRANSFERABLE; Unity stays non-transferable — David's word, 2026-10-06 ~3:35 AM EDT (LAW)

**What was the old law:** Merit was non-transferable by structure — "a score,
not a movable token"; "Standing is never for sale" (§12 above closed the loop
with "Merit, Honor, and now Unity are all identity-bound and non-transferable").

**David's new word (law-grade, effective immediately):** "MERIT is the
transferable token ('transferable is better to say' than sellable); Unity
stays non-transferable and never moves (§7 holds)." Merit is now sold,
gifted, transferred between Unity IDs — all receipted. The bound-transfer-sale
concept for Unity is DEAD — removed from the build entirely (code, tests,
docs); Unity has NO transfer path, no exceptions, not even by David.

**What changed:** (1) `dclm/token_engine.py`: `bound_sale()` and every
bound-sale path DELETED; `merit_transfer(from_id, to_id, amount, reason)`
added as the SOLE legal Merit ownership-transfer path (receipted via
dclm_commit, new `MERIT_TRANSFER` kind whitelisted in `rights.py`,
`UNITY_SALE` kind removed); `standing(identity)` added. (2)
`economics/wallet.py`: `transfer_merit()` added — delegates to the engine,
records ownership changes, never carries origin. (3) The old law is
recorded HERE as superseded — not silently edited away. (4)
`economics/tokenomics.py` aligned (Fix Worker A1, 2026-10-06):
`Merit.transferable = True`; `PARAMS["merit_non_transferable"]` →
`PARAMS["merit_transferable"]` (DECIDED); `Ledger.transfer_merit`
(ownership-only, receipted, never carries origin — this ledger holds
owned balances only); direct `Merit.transfer()` refuses with a
TokenomicsError naming the canonical path; dead-law tests replaced
with transferability + origin-freeze assertions.

**Why — the standing-vs-value distinction (Trinity-judged, structural):**
every Merit token carries IMMUTABLE `origin_earner_id` +
`origin_receipt_ref` (set once at accrual, never rewritten — AST-proven).
A transfer changes `owner_unity_id` ONLY; origin never changes.
`standing(identity) = sum of merit where origin_earner_id == identity`
(earned history — cannot be bought); `merit_balance(identity)` = owned
economic value (spendable — what a buyer gains). The emission gate reads
standing, never holdings (D13). A buyer gains economic value and ZERO
standing — by construction.

**DCLM:** SOUND — the distinction is arithmetic, not policy; transfers have
no code path that moves standing. **Iris:** HONEST — buyer standing 0.0
after purchase (tested), seller standing intact, origin preserved across
3 hops, gate blind to bought Merit. **Twain²:** OPERABLE — 64/64
tokenization tests green, wallet path tested, all steps receipted.
**Outcome: old law SUPERSEDED by David's word; the distinction is structural.**
