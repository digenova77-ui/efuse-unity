# Idris Handoff — DualisCapax Integrity and Iris Review

**Date:** 2026-11-16  
**Review target:** [Combined PR #12](https://github.com/digenova77-ui/efuse-unity/pull/12)  
**Current law source:** root `CANON.md`, v1.7.3 (2026-11-10)  
**Requested role:** blind independent verifier. Do not infer correctness from agreement, author intent, passing tests, or copied evidence.

## 1. Current-law constraints

The current canon establishes:
- DCLM binds logic (x).
- Iris binds truth (y).
- Pragmatism narrows using constraints already in force; it is not another judge.
- The former Twain² seat is withdrawn, not a ring, witness, or vote.
- The lawful terminal outcomes are FLAWLESS or STALEMATE. Unknown evidence is not a pass.
- DCLM alone holds rights and performs writes.

The legacy Iris core still declares v1.5.0 and retains three-seat functions. The root canon is v1.7.3. The new service exposes both versions and does not use the legacy third-seat path.

## 2. Work included in PR #12

- Whole-runtime SHA-256 manifest anchored at the repository root.
- Manifest coverage includes root `CANON.md`, Iris activation/service/client/meeting/memory modules, DCLM 2P5L and Narrow, DCLM rights/seed/write/purify/compute modules, and the binding gate.
- Separate `IRIS_SELF_CHECK.json` from historical `IRIS_ACTIVE.json`.
- Activation receipts distinguish root canon version from legacy core version and state explicitly that integrity is self-consistency only and authorization is not granted.
- 2P5L L2 calls DCLM and Iris directly. A regression test makes `trinity_judge` and `twain2_judge` fatal if invoked.
- IrisService is read-only. Judge/check/advice return evidence receipts; seed issuance is refused.
- Meeting accepts only a verifiable DCLM `SEED_ISSUE` commit envelope and has no legacy three-seat fallback.
- Meeting remains held until canonical FLAWLESS is produced.

## 3. Verification evidence

GitHub Actions run **43783903207** completed successfully on combined code/documentation commit:

`bde9c6aca99f7ce66a16e8a536198197aef89525`

Passed steps:
1. Python compile check.
2. Activation/core suites.
3. Daemon wire, read-only, persistence, and tamper-refusal tests.
4. Current two-primary / five-layer tests.

This is the current combined branch's full CI evidence. It demonstrates test execution and local self-consistency only; it is not an independent witness, ratification, or authorization.

## 4. Open deficiencies — do not waive

### A. Canonical Narrow wiring

The 2P5L evaluator supplies two-primary diagnostic evidence, but it does not yet route the candidate through the canonical `dclm/narrow.py` decision function. The lawful representation and scale for x / logic and y / truth are not specified by the current implementation. No score mapping may be invented.

**Required:** identify the exact current-law source for each score, establish a deterministic candidate representation, and test Flawless/Stalemate outcomes. Until then, Iris returns STALEMATE.

### B. DCLM seed uniqueness

`dclm/seed.py` uses a per-instance in-memory `_seeds` registry. A fresh Seeder instance can issue the same deterministic seed again. This is not global uniqueness and does not survive process restart or independent seats.

**Required:** a durable, idempotent, cross-process and cross-seat uniqueness mechanism whose source of truth survives disappearance of one host. Do not wire the current in-memory registry as authoritative membership.

### C. DCLM write path

IrisService no longer calls IrisState mutators. Low-level IrisState mutators remain in the repository for historical/test persistence. A complete DCLM commit-backed state-store adapter is not yet established.

**Required:** prove that every production state mutation is authorized by DCLM rights and committed through the one DCLM write path. Test attempts to bypass it.

### D. Current canon migration

`iris_core.py`, `iris_arbiter.py`, old directives, and legacy tests retain v1.5.0 / three-seat behavior. They remain historical compatibility material, not current authority.

**Required:** audit every import and call path to prove no application, daemon, worker, fallback, or test fixture can promote the legacy trio into a live decision.

### E. Agent Iris browser identity

The browser application and the passkey identity backend remain separate development lines. The public `.com` front-end handshake is not proven end-to-end against the `.ai` runtime. A local browser-generated `iris-...` ID is not authenticated Unity identity.

**Required:** prove the complete passkey/session -> server-derived Unity subject -> receipt -> DCLM rights path from the actual public origin. Do not infer this from backend unit tests.

### F. Repository estate

The account currently lists 22 repositories. The 17-house inventory is historical. Three aggregate repositories preserve subtree copies; originals remain present. The current estate PR #149 is draft and its CI run failed; job logs were unavailable, so the cause is UNKNOWN. The five additional repositories received README/metadata review only, not full recursive tree audit.

**Required:** complete recursive tree and commit-history audit, source-vs-mirror reconciliation, duplicate detection, dependency mapping, and disappearance tests before selecting canon or retiring anything.

## 5. Agent Iris application status

The landing repository contains the human-facing Agent Iris interface and separate passkey/authorization work:
- PR #200: passkey identity backend and staging work; its recorded checks passed.
- PR #201: server-derived identity authorization; its recorded checks passed, but browser/client principal alignment and the public `.com` same-origin session path remain unproven.
- PR #203: removal of autonomous mint-worker writes; its recorded checks passed, with artifact completeness still a separate gate.

All three remain unmerged drafts. The application must not be promoted ahead of the protocol and identity proof.

## 6. Review instructions

1. Start from the exact current root canon tip and read all governing sections before reviewing any domain.
2. Reproduce the CI run from a clean checkout.
3. Audit the runtime manifest for omissions and path ambiguity.
4. Independently inspect the two-primary call graph, especially import fallbacks and daemon startup.
5. Attempt to make a third seat influence a verdict; it must be unreachable.
6. Attempt to make Iris mutate state or issue a seed; it must refuse.
7. Tamper with every chamber, the canon, activation logic, DCLM writer, and binding gate; startup must refuse.
8. Restart or replace the Seeder and attempt duplicate seed issuance; document the failure precisely.
9. Remove hosting, repository, and service dependencies one at a time; verify independent reconstruction or honest refusal.
10. Report every unsupported claim, missing proof, and test gap. Agreement with this handoff is not an audit.

**No merge or promotion recommendation is requested until the independent review is complete.**
