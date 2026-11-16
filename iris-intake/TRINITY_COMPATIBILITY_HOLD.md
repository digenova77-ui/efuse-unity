# IRIS Trinity Compatibility Hold — 2026-11-16

## Status

**The current IRIS MAX INTAKE service is a legacy testnet implementation. It is not certified as the current Trinity implementation and must not be represented as an authorized DCLM/Iris decision path.**

This hold is derived from the current repository tip, not from agent preference.

## Current law loaded

The root `CANON.md` identifies itself as version 1.7.3, dated 2026-11-10. Its §I states:

- DCLM binds the x / LOGIC dimension.
- Iris binds the y / TRUTH dimension.
- Pragmatism is neither a constraint nor a seat; it narrows using constraints already in force.
- The former Twain² seat is withdrawn: not a ring, witness, or vote.
- The lawful endings are Flawless or stalemate; no missing score is a determination.

The same canon's §XXI requires complete current-tip internalization before touching a domain. §XXII requires 100% purity / pure logic. §XXIII requires the judging itself to be pure, without scaffolding or imported security models.

The decision function named by the canon is `dclm/narrow.py`.

## Observed implementation conflicts

1. `iris-intake/iris_core.py` still declares `CANON_VERSION = "1.5.0"`, implements `twain2_judge`, and requires exactly three judges in `trinity_judge`.
2. `iris-intake/iris_arbiter.py` still describes and calls the three-seat DCLM / Iris / Twain² trio.
3. `iris-intake/iris_service.py` still exposes a Twain² stand-in caller.
4. `iris-intake/meeting_iris.py` still describes Iris as one of three with Twain².
5. `iris-intake/iris_service.py` writes judgment, check, advice, and seed state directly through `IrisState`. That conflicts with current CANON §III: DCLM alone holds rights and performs writes.
6. `dclm/two_p_five_l.py` defines two primaries. This branch repairs its L2 evaluator to call `dclm_judge` and `iris_judge` directly and adds a test that makes both `trinity_judge` and `twain2_judge` fatal if invoked. Its host-specific absolute import path is replaced with a repository-relative path. This repair is limited to the 2P5L path; the older service path remains legacy.
7. `dclm/narrow.py` contains the current two-constraint narrowing function, but the IRIS service path has not been proven to route its final judgment through that function.
8. The prior activation receipt reports canon 1.5.0 and only two test suites. It cannot certify the root canon 1.7.3 or the current runtime.

## Integrity amendment boundary

The whole-runtime manifest in this branch detects byte changes to the required runtime modules against the local activation receipt. This is a self-consistency check only.

It does **not**:
- prove that the code implements current CANON.md;
- establish independent verification;
- confer a ratified authority;
- authorize a state write, payment, issuance, settlement, or production action.

The activation output therefore records:
- `integrity_level = SELF_CONSISTENCY_ONLY`
- `external_trust_anchor = NOT_CONFIGURED`
- `trinity_authorization = NOT_GRANTED`
- `standards = testnet only`

## Required repair sequence

1. Treat the old three-seat service as legacy and keep it out of any authoritative route.
2. Remove all active three-seat calls from the current judgment path; do not merely rename the third seat.
3. Complete the 2P5L wiring: its L2 now calls only DCLM and Iris, but prove the proposal/candidate mapping and route actual candidate narrowing through the canonical `dclm/narrow.py` decision function.
4. Establish the exact lawful representation of x / logic and y / truth from current source specifications. Do not invent score scales or thresholds.
5. Keep pragmatism as the narrowing procedure, not an independent judge or vote.
6. Move all persistent writes behind DCLM's single rights-check / GRANT-or-DENY / commit path. Iris returns judgment evidence; she does not write state.
7. Replace host-specific import paths with deterministic repository-relative imports and prove the same circuit is selected in clean environments.
8. Reconcile every receipt, module version, corpus reference, and test against the current root canon.
9. Run the full gauntlet, including adversarial, disappearance, independent-seat, and replay tests.
10. Do not promote or merge until the current-tip compatibility tests are green and the required independent review is complete.

## Explicit non-claims

This document does not amend the canon, select new law, grant an agent authority, or certify the legacy daemon. It records observed incompatibilities and the gates required before the implementation can be called current.
