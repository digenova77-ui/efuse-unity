# Diamond ecosystem certification matrix

Status is evidence-scoped, not a blanket production certification. A row is certified only for the exact revision and behavior named; CI does not establish live deployment, distributed consensus, or untested effect paths.

## Governing invariant

Trinity is the sole authorization gate. Idempotency identifies and de-duplicates an operation; it never grants authority. Unknown authority, mismatched operation content, or unresolved prior effects fail closed. Remove duplicate policy/scaffolding only when the invariant remains enforced and tested.

## Evidence ledger (2026-10-23; refreshed after latest CI runs)

| Boundary | Revision / evidence | Current status | Remaining proof |
|---|---|---|---|
| Canonical idempotency contract | efuse-unity PR #8, head `42183c7456dc2737d35e58da5549784ff8954b62`; CI https://github.com/digenova77-ui/efuse-unity/actions/runs/39994681964 | CI passed on exact PR head; shared encoding/hash vector gate green and evidence ledger refreshed | Effect-boundary, cross-language and crash/concurrency tests remain outstanding |
| Factory event ledger | queue PR #10, head `22097bfb3cb9dafdc7f21215c77a77e2e36ef0fd`; CI https://github.com/digenova77-ui/dualiscapax-factory-queue/actions/runs/39994696267 | CI passed on exact PR head; strict canonicalization rejection and 48-attempt concurrent duplicate test included (one RECORDED, 47 ALREADY_RECORDED, one ledger entry) | This tests concurrent threads against a single-host file lock. Multi-process/multi-node consensus, crash-point recovery, and atomicity with external effects remain unproven |
| Landing edge | landing PR #160, head `35f138a3a55d07f2e2eae158020d894bfb2edafa`; CI https://github.com/digenova77-ui/dualiscapax-landing/actions/runs/39994113487 | Elite CI passed on exact PR head including shared canonicalization vectors | Read-only route behavior is CI evidence only; Pages/Worker configuration and live route still require staging proof |
| Iris identity-to-world routing | Replit local suite recorded 136/136 at `998902c64784fc1e7af256b1d6275234937de827`; GitHub staging runtime PR #158 head `2b735718241b85c28eb0eb410cd69f930062e47a`; Iris Runtime Adapter CI https://github.com/digenova77-ui/dualiscapax-landing/actions/runs/39995246304; Elite CI https://github.com/digenova77-ui/dualiscapax-landing/actions/runs/39995246333 | CI passed on exact GitHub head; worker binds durable claim to `dualis.idempotency.v1` and the same SHA-256 digest Trinity authorized; tests assert denied/mismatched authority causes no downstream memory/provider effects | Actual identity/Trinity/memory/provider service bindings are not configured in this PR; no deployed staging request proves atomic claim/replay semantics or live identity-to-world route |
| Law core | `dualiscapax-law-core` master HEAD `112597e969450cb96ec2fe786f351cb3d3f1a913`; CI https://github.com/digenova77-ui/dualiscapax-law-core/actions/runs/39118855035 | Rust verify workflow passed on current recorded master HEAD; deterministic trace/golden and replay checks are in the verification script | No shared v1 idempotency adapter or cross-service crash/recovery proof is established by that run; protected effect-boundary proof remains open |
| Production release rail | Pages/Worker integration has reported missing Worker entrypoint/assets configuration | Not certified | Correct project/build configuration only after authorized review; stage and probe exact deployed SHA |
| Distributed execution / consensus | No cross-node fault-injection evidence linked here | Not certified | Multi-node partition, duplicate delivery, leader/recovery, and durability tests before any distributed exactly-once claim |


## World Elite evidence discipline

Use these labels in every report and release record:

- **PROVEN-CI**: named automated tests passed on the exact SHA.
- **PROVEN-LOCAL**: a reproducible local test passed on the exact SHA; environment and command are recorded.
- **PROVEN-STAGING**: isolated deployed revision was probed, with sanitized request/response evidence and deployment identity.
- **PROVEN-PRODUCTION**: production behavior was verified through approved read-only probes and auditable evidence.
- **UNPROVEN**: evidence is absent, stale, incomplete, or only indirect.
- **FAILED**: a relevant test or probe failed; keep the failure visible until a corrected exact SHA passes.

A status cannot be promoted by documentation, a green unrelated workflow, a passing test on an older SHA, or a source-code inspection alone. A certification statement must name the claim, boundary, exact SHA, test/probe command, result, and limitations. Evidence artifacts must not contain credentials, biometric data, secrets, or raw private payloads.

## Minimal end-to-end proof campaign

1. **Canonical bytes:** every runtime validates the same shared vectors, safe-integer range, Unicode rules, object-key ordering, and array-order semantics.
2. **Effect harness:** a deterministic fake effect counter is the oracle; repeated same-key requests must leave the counter at one and return the same receipt.
3. **Conflict:** change one semantic request field under the same scope/operation ID; require a conflict and unchanged effect counter.
4. **Authority:** inject missing, revoked, malformed, and denied authority; require blocked outcome and zero effects.
5. **Concurrency:** issue simultaneous same-key requests through independent workers against the actual reservation store; require one reservation and one effect.
6. **Crash points:** terminate after reservation, after downstream effect, and before receipt commit; restart and prove reconciliation without blind replay.
7. **Integrity:** alter stored record, receipt, sequence, or previous hash; require fail-closed detection.
8. **Staging:** deploy only an explicitly approved isolated candidate, record deployed SHA/config identity, run sanitized probes, and retain outputs.
9. **Production:** require explicit release approval after all applicable gates pass. No CI-only claim may be described as production certification.

## Simplification gate

Before removing a framework, wrapper, policy module, or service, identify its invariant and callers; show the invariant remains enforced by a smaller component; run relevant tests; inspect the diff for lost authorization checks, logging, recovery, or rollback behavior. Delete only after that proof. No removal is justified solely because a layer looks redundant.

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