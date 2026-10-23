# Diamond ecosystem certification matrix

Status is evidence-scoped, not a blanket production certification. A row is certified only for the exact revision and behavior named; CI does not establish live deployment, distributed consensus, or untested effect paths.

## Governing invariant

Trinity is the sole authorization gate. Idempotency identifies and de-duplicates an operation; it never grants authority. Unknown authority, mismatched operation content, or unresolved prior effects fail closed. Remove duplicate policy/scaffolding only when the invariant remains enforced and tested.

## Evidence ledger (2026-10-23)

| Boundary | Revision / evidence | Current status | Remaining proof |
|---|---|---|---|
| Canonical idempotency contract | efuse-unity PR #8; CI run https://github.com/digenova77-ui/efuse-unity/actions/runs/39994072065 | Contract-vector CI passed on the vector-metadata revision | Re-run and certify latest PR head; review language-specific implementations |
| Factory event ledger | factory-queue PR #10; CI run https://github.com/digenova77-ui/dualiscapax-factory-queue/actions/runs/39993875614 | CI passed on queue revision with aligned shared-vector metadata | Verify latest branch head; concurrency/crash-recovery proof; distributed deployment claims excluded |
| Landing edge | landing PR #160; CI run https://github.com/digenova77-ui/dualiscapax-landing/actions/runs/39994113487 | Elite CI passed including shared canonicalization vectors | Verify exact current PR head and Pages/Worker release configuration; live route proof |
| Iris identity-to-world routing | Replit branch `feat/iris-backend-dev-restore-20261022`, HEAD `998902c64784fc1e7af256b1d6275234937de827`; recorded local suite 136/136 | Local contract suite reported passing at that revision | Repeat on current source; provider credentials/session gate; isolated staging route proof |
| Law core | `dualiscapax-law-core`, `master`; verify workflow runs exist | Existing Rust verification CI has passing runs on listed historical SHAs | Run `verify.sh` on current head; prove Trinity authority binding and replay/crash invariants against real effect boundary |
| Production release rail | Pages/Worker integration has reported missing Worker entrypoint/assets configuration | Not certified | Correct project/build configuration only after authorized review; stage and probe exact deployed SHA |
| Distributed execution / consensus | No cross-node fault-injection evidence linked here | Not certified | Multi-node partition, duplicate delivery, leader/recovery, and durability tests before any distributed exactly-once claim |

## Required conformance behavior

1. Canonical encoding is identical across implementations; reject unsupported values instead of silently normalizing them.
2. Same operation scope/ID + same semantic request returns the original recorded state/receipt without repeating effects.
3. Same scope/ID + changed semantic request conflicts.
4. Authorization denial causes no protected side effect. Idempotency is not authorization.
5. Reservation precedes effect. Crashes or ambiguous outcomes reconcile; they do not trigger blind replay.
6. Explicitly defined pre-reservation refusals may be re-evaluated only when tests prove no reservation and no side effect occurred.
7. Receipt/evidence binds contract version, operation identity, request hash, authority reference, outcome/state, and effect evidence.
8. Each claim names the exact commit and test run. Local/CI success is not production evidence.

## Certification rule

Do not mark the whole ecosystem Diamond-certified until every effect-owning component has a passing conformance suite on its current candidate revision, the integration suite passes across boundaries, and an isolated staging deployment proves the actual authorization and recovery paths. Production changes require explicit approval.