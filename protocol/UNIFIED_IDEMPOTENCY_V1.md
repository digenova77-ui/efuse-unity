# Unified Idempotency Contract v1

**Status:** proposed, testable protocol contract. Not a claim that every repository implements it.
**Authority:** Trinity remains the only authorization gate. Idempotency prevents duplicate effects; it never grants authority.
**Canonical home:** `efuse-unity`. Consumers must pin this contract version and implement local durable storage appropriate to their runtime.

## Purpose

One logical operation must not create a second effect because a client, worker, queue, workflow, relay, or edge runtime retries it. Every repository uses the same semantic rules while retaining its own storage adapter.

## Required operation envelope

Every side-effecting operation MUST bind these fields before execution:

- `contract`: `dualis.idempotency.v1`
- `scope`: stable namespace for the authority and effect owner (for example `meter.debit`, `queue.inventory`, `relay.deliver`, `deploy.release`)
- `operation_id`: caller-generated stable identifier, non-empty and bounded
- `request_hash`: SHA-256 of the canonical semantic request, excluding transport-only fields and secrets
- `authority_ref`: reference to a verified authorization decision; absent/unknown means BLOCKED
- `created_at`: informational UTC timestamp; timestamps are not identity
- `schema_version`: version of the operation payload

The canonical request encoding is UTF-8 JSON with recursively sorted object keys, no insignificant whitespace, preserved array order, and no non-finite numbers. Each language implementation MUST share conformance vectors before it can claim compatibility. Hashing raw transport bytes is not sufficient.

## Identity and collision rules

The idempotency identity is the pair `(scope, operation_id)`; the stored record binds it to `request_hash`.

1. First use atomically reserves the pair before any side effect.
2. Same pair + same hash returns the existing state/receipt and MUST NOT execute the effect again.
3. Same pair + different hash returns `IDEMPOTENCY_CONFLICT`; never overwrite the original record.
4. Missing, malformed, or unverified identity/authority fails closed before side effects.
5. A duplicate is not proof of success. Return only the stored, verifiable state.
6. Scope names must prevent cross-operation key collisions. Keys are never authorization tokens.

## State machine

- `RESERVED`: durable intent recorded; effect has not been proven complete.
- `APPLIED`: effect and durable receipt are committed consistently.
- `REJECTED`: a terminal, policy-grounded refusal with a reason and evidence reference.
- `IN_DOUBT`: effect outcome cannot be established safely; block automatic re-execution and require reconciliation.

Allowed transitions: absent -> RESERVED -> APPLIED; absent -> RESERVED -> REJECTED; RESERVED -> IN_DOUBT; IN_DOUBT -> APPLIED or REJECTED only through a verifiable reconciliation procedure. No transition may erase history or reset a completed key.

A system may use a richer local state machine, but it MUST map to these semantics. If an operation is rejected because of transient state (for example insufficient balance), that refusal may be re-evaluated under an explicit new operation ID; do not silently mutate a terminal record or reuse a key with a different request.

## Atomicity, crash recovery, and retries

- Reservation must be atomic for the uniqueness scope. In-process maps, local JSONL, and single-host file locks are not distributed consensus.
- The effect and APPLIED receipt must share a transaction where possible. Otherwise use an idempotent downstream effect plus a transactional outbox/inbox or a verifiable reconciliation protocol.
- A crash after reservation MUST NOT trigger blind replay. Recover the existing operation and prove whether the effect occurred; unresolved cases become IN_DOUBT.
- Retry policy is bounded and transport-specific. Retries reuse the same operation ID and request hash. Backoff does not change identity.
- Retention must exceed the maximum replay/recovery horizon. Expiry never authorizes a duplicate financial, identity, release, or ledger effect.

## Receipts and audit

A receipt MUST bind contract version, scope, operation ID, request hash, final state, effect/result hash where applicable, authority reference, previous-ledger hash where applicable, and verifier/evidence reference. Timestamps are metadata, not proof. Secrets and sensitive payloads MUST NOT be copied into idempotency records or logs.

Corrections are new append-only events referencing the prior receipt; never rewrite a receipt to make history appear different.

## Repository mapping

- `efuse-unity`: canonical semantics; meter, tokenization, relay and economics adapters must preserve receipt/manifest hashes and avoid double apply.
- `dualiscapax-factory-queue`: map WORK_KEY/job lifecycle and event ledger to the state machine; current lifecycle primitive is single-host only and the worker remains disabled unless separately authorized.
- `dualiscapax-law-core`: verify transition/receipt invariants as pure law functions; no storage or external effects.
- `dccp-world` and `dualiscapax-hud`: UI/session retries may deduplicate display/request work but never authorize protected operations.
- `dualiscapax-landing`: edge routes are read-only and must not imply idempotent settlement; mutating API routes require durable storage and authority binding.
- `dualiscapax-deploy`: a release operation is bound to exact repository, commit SHA, target, and approved release reference; repeated invocation returns the recorded release state, not a second deployment.
- `coin-repo`: ledger event identity and chain position are immutable; duplicate event IDs cannot mint, transfer, or append a second effect.
- `unity-site`: static-only; no authority-bearing side effects.

These are mapping requirements, not assertions of current implementation.

## Acceptance gate

A consumer cannot claim conformance until its tests demonstrate:
1. same-key/same-request replay produces one effect and the same receipt;
2. same-key/different-request conflicts without mutation;
3. concurrent duplicate requests reserve once;
4. crash after reservation does not blindly repeat the effect;
5. authority denial causes zero side effects;
6. corrupted or missing record fails closed;
7. receipt/hash tampering is detected;
8. retry after a transient refusal follows the documented new-operation policy;
9. retention/recovery behavior is tested;
10. exact tested commit SHA is recorded.

**Non-goals:** this contract does not itself provide distributed consensus, exactly-once effects across arbitrary external systems, cryptographic signing, authorization, physical energy measurement, or production readiness.
