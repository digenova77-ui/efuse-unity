# Diamond Merit Engineering Gates

**Scope:** engineering acceptance contract for Merit and its boundary with eFuse, Unity, Honor, DCLM, and Iris.
**Classification:** specification and release gates; not a live currency, wallet, financial instrument, or production authorization.
**Authority:** existing `CANON.md`, `economics/PARAMS.md`, `economics/tokenomics.py`, and their tests remain the sources of truth. This document does not supersede them.
**Release posture:** TESTNET ONLY. No live emission, custody, fiat gateway, exchange, or production value promises.

## 1. Non-negotiable invariants

1. **Unity is identity, not a transferable asset.** Every value movement binds the canonical Unity ID. No anonymous account or identity rebinding.
2. **Merit is earned value and transferable ownership.** A transfer changes balance ownership only. It must not change the original earner, origin receipt, earned history, or standing.
3. **Standing is origin-derived, never balance-derived.** Buying or receiving Merit must not buy standing, emission weight, governance power, or privileged access.
4. **eFuse is not bought or sold.** Emission remains blocked until the decided energy peg and every required evidence gate are satisfied. A cap is a ceiling, not a target or entitlement.
5. **Honor is permanent recognition.** It is append-only, not spendable, not transferable, and cannot convert into Merit or eFuse.
6. **No proof, no movement.** Every state-changing operation is authorized by DCLM's canonical write path and produces a verifiable receipt.
7. **Fail closed.** Missing identity, unverified evidence, unknown figures, held parameters, invalid signatures, stale laws, or unavailable verification deny the operation.
8. **No silent historical rewrite.** Law changes are prospective and receipted; in-flight work retains the law version under which it began.
9. **No production promotion from a testnet result.** A passing unit test, simulation, or green build proves only its stated scope.

## 2. Required receipt contract

Every economic mutation must produce a canonical receipt binding, at minimum:

- schema and protocol version;
- unique operation/receipt identifier and idempotency key;
- operation kind and exact canonical target;
- sender and recipient Unity IDs where applicable;
- amount as a canonical decimal/integer representation, never ambiguous floating-point serialization;
- origin earner and immutable origin receipt reference for Merit;
- evidence reference, evidence grade/provenance, and evidence digest;
- authorization decision, signer identity/key ID, and signature verification result;
- law version, epoch, logical timestamp, and previous-ledger reference;
- result state and deterministic receipt digest.

Secrets, private keys, passkeys, bearer tokens, biometric source data, and provider credentials must never appear in a receipt or public log. A digest does not make unverified source evidence true; provenance and verification status must remain explicit.

## 3. Merit transfer state machine

Allowed transition:

`REQUESTED → AUTHENTICATED → AUTHORIZED → COMMITTED → RECEIPTED`

Any failed check transitions to `REFUSED` without balance mutation.

Before commit:
- verify the sender's registered signing key and the canonical transfer payload;
- verify the sender owns sufficient available balance;
- verify amount is finite, positive, in the supported precision, and within limits;
- verify sender and recipient Unity IDs are valid and distinct;
- verify the nonce/idempotency key has not already been applied;
- bind the authorization to sender, recipient, amount, reason, operation ID, target, and current law version;
- preserve origin metadata and earned standing unchanged.

At commit:
- debit and credit are one atomic ledger transaction;
- exactly one immutable transfer receipt is appended;
- retries with the same idempotency key return the original result and never apply twice;
- an uncertain commit must be reconciled by reading the ledger, not retried as a fresh transfer.

Explicitly reject:
- replayed or mismatched signatures;
- missing or revoked keys;
- overspending and negative amounts;
- same-identity self-transfer unless a future law explicitly allows it;
- floating-point/NaN/infinity values and non-canonical amount encodings;
- duplicate receipt IDs or idempotency keys with a different payload;
- transfers that mutate origin, standing, emission history, or Honor;
- any transfer through a client-side balance setter or alternate write path.

## 4. Invariant and adversarial acceptance matrix

| ID | Invariant | Required test evidence |
|---|---|---|
| M-01 | Transfer conserves total Merit | Sum of all balances before and after equal; sender debit equals recipient credit |
| M-02 | Origin is immutable | Origin earner and accrual receipt byte-for-byte unchanged after one or many transfers |
| M-03 | Standing is not transferable | Sender standing unchanged; recipient standing unchanged by receipt of transferred Merit |
| M-04 | Replay is idempotent | Same signed operation submitted repeatedly yields one ledger mutation and the same receipt |
| M-05 | Payload substitution refused | Alter recipient, amount, reason, epoch, or target after signing; signature/authorization fails |
| M-06 | Unauthorized sender refused | Missing, invalid, revoked, or wrong sender key yields zero state changes |
| M-07 | Overspend refused | Balance remains unchanged when requested amount exceeds available balance |
| M-08 | Precision is deterministic | Boundary values, decimal normalization, NaN, infinity, negative zero, and overflow are covered |
| M-09 | Concurrent transfers safe | Competing spends cannot overspend; exactly one valid commit wins when funds permit only one |
| M-10 | Atomicity | Crash/failure between debit and credit cannot leave a partial state |
| M-11 | Receipt chain detects tamper | Altered, deleted, reordered, or forked receipt is detected by full-chain verification |
| M-12 | Law version pinned | In-flight transaction verifies against its starting law; new law applies prospectively |
| M-13 | Unknown evidence earns zero | UNKNOWN or unsigned figures cannot create Merit or emission weight |
| M-14 | No emission from purchased Merit | Transfer does not change origin-derived standing or emission weights |
| M-15 | eFuse gate remains closed | Missing/held `peg_ratio_E`, absent verified evidence, or cap exhaustion refuses emission |
| M-16 | Honor separation | No Honor transfer, spend, conversion, or emission path |
| M-17 | Unity binding | Missing, malformed, or rebound identity refuses movement |
| M-18 | No alternate writer | Repository audit proves all persistent mutations pass through the canonical DCLM rights/write boundary |
| M-19 | Receipt privacy | Logs and receipts contain no secret, raw biometric data, bearer token, or private-key material |
| M-20 | Recovery is safe | Crash-after-commit and lost-response tests reconcile by operation ID without double application |

Each test must report command, commit SHA, expected result, actual result, and evidence link. Tests must include property-based or generated sequences for conservation, replay, and transfer-order invariance. Mark a test **PASS** only after it is actually run; this document itself does not claim these tests passed.

## 5. Deterministic ledger rules

- Define one canonical serialization for every receipt and amount.
- Use integer base units or a formally specified decimal scale; never rely on binary floating-point equality for ledger consensus.
- Sort map keys and normalize strings/Unicode according to the protocol specification before hashing.
- Include the previous receipt hash and protocol/schema version in each receipt digest.
- Reject duplicate IDs with different payload hashes.
- Maintain an append-only event log; materialized balances are rebuildable projections, never the sole source of truth.
- Periodically replay the entire event history and compare its digest and balances with the live projection.
- Treat clock values as metadata unless the protocol's logical-clock law explicitly defines ordering.

## 6. Merit is not money by declaration

Before any external value, custody, payment, exchange, or production emission capability is enabled, separately prove:
- the legal classification and operating obligations in every intended jurisdiction;
- a complete, audited ledger and key-management model;
- a defined redemption/settlement contract and counterparty responsibilities;
- threat model, independent security review, incident response, and recovery drills;
- user disclosures and dispute/correction handling;
- evidence-backed energy measurement and peg methodology;
- the canonical parameter decisions currently marked HELD in `economics/PARAMS.md`;
- explicit founder authorization for the exact release and limits.

Until those gates are satisfied, describe Merit as a **testnet protocol concept/implementation**, and describe eFuse emission, wallet custody, and live settlement as **not live**.

## 7. Integration contract across the diamond

- **DCLM:** sole authority and write/commit boundary; checks rights before mutation.
- **Iris:** verifies truth, provenance, and that claims match evidence; cannot grant its own authority.
- **Twain²:** checks that user-visible decisions, refusals, and consequences are understandable; it cannot bypass DCLM.
- **Unity:** canonical identity binding, not public personal data.
- **Honor:** immutable recognition stream, separate from balances.
- **Merit:** transferable balance with immutable origin and non-transferable standing.
- **eFuse:** metered energy primitive; emission remains behind the decided peg and evidence gates.
- **Ledger:** append-only receipts, deterministic replay, idempotency, and audit.
- **Release control:** staging, exact-SHA tests, independent verification, explicit approval, and rollback.

No component is permitted to turn a missing dependency into a successful state. If one ring cannot verify, the operation is refused or left undecided.

## 8. Current limitations and next implementation order

This contract is not proof that every property is implemented in production. The current codebase labels the tokenomics engine TESTNET and records the energy peg and other parameters as HELD. Prior documentation also explicitly states there is no live coin, wallet, or emission.

Order of work:
1. Run the existing complete tokenomics, wallet, law, and purity suites on the exact candidate SHA.
2. Add any missing M-01 through M-20 tests to the existing canonical test modules, not a parallel token engine.
3. Close any invariant gaps in the canonical DCLM ledger and receipts path; preserve existing behavior with regression tests.
4. Perform concurrency, crash-recovery, property-based, replay, and tamper tests.
5. Obtain an independent security review and verify the deployment artifact.
6. Keep live emission/custody disabled until the held parameters, legal gates, and explicit release authorization are resolved.

**Decision:** engineering hardening can progress in testnet. Live economic operation remains BLOCKED until the above evidence exists.
