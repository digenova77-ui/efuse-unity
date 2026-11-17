# Repair 16 — DCX-02 (caller-asserted component identity) — Attempt Record

Date: 2026-11-16. Author's seat: Idris (ARCHIVE), under the Founder's explicit
authorization of 07:10 EST ("push the repair, try it") — a deliberate,
recorded exception to the usual author/verifier separation. **This repair is
NOT independently verified.** Verification is queued for Grok's seat (see the
wake-queue). No branch was pushed; no PR was opened; PR #15's merge remains
the Founder's word, untouched by this record.

Trees: `repair-16/` = `repair-15/` (frozen baseline + PR #15) plus this
repair, nothing else. Diff of the 9 changed files: `repair16-dcx02.diff`
(361 lines). Raw outputs: `repair16-gauntlet.txt`, `repair16-discover.txt`,
`repair15-discover-rerun.txt`.

## The defect

`rights.check_rights` granted the entire write tier to any caller whose
context dict contained a string starting with `"dclm."` under the key
`"internal"`. Context is caller-supplied data; the module's own docstring
claimed "clients cannot supply this from outside DCLM," but nothing enforced
it. Any external caller could manufacture DCLM component authority from a
string — DCX-02, gauntlet property 2.

## The repair (authenticated component capabilities)

- `rights.py` now mints **ComponentCapability** objects through
  `issue_component_capability("dclm.*")`. The constructor refuses any call
  that does not present the module's private mint sentinel; issued objects
  are held in a module-private registry; the write-tier gate accepts only a
  registered capability object and reads the component name from the object,
  never from caller text. A bare string — any string — now DENYs with
  INTERNAL_SOURCE_REQUIRED.
- The eight production component modules (meter, seed, share, tap,
  token_engine, winter, helpers, onboard) each mint their capability once at
  import and present the object at all 14 call sites. No other production
  behavior changed; the identity gates (PR #15) are untouched and still
  evaluated after the source gate.
- Honest scope note: this authenticates component identity. It does NOT bind
  a component's capability to specific commit kinds (least-privilege
  kind-binding) — that question belongs to the DCX-03 layer and is recorded
  here as open, not silently decided.

## Gauntlet result (7 tests; baseline 7/7 FAIL)

| Test | Before | After | Grade |
|---|---|---|---|
| DCX-02 external context cannot claim component identity | FAIL | **PASS** | Genuinely repaired — all three forged labels DENY |
| DCX-01 constructed verdict | FAIL | FAIL | Unchanged, its own reason |
| DCX-05 seed continuity | FAIL | FAIL | Unchanged |
| DCX-06 missing Iris core | FAIL | FAIL | Unchanged |
| DCX-03 grant bound to commit kind | FAIL | "ok" | **MASKED — not a pass.** The gauntlet's `_grant()` helper presents the bare string, now receives DENY, and the commit refuses at the verdict gate. Kind-binding was not repaired; this test cannot measure DCX-03 until the helper presents a capability |
| DCX-04 receipt-validation atomicity | FAIL | "ok" | **MASKED — not a pass.** Same shadow: refusal happens before receipt validation is reached |
| DCX-04 signing-failure atomicity | FAIL | ERROR | Mode changed by the same shadow (CommitRefused surfaces where the test awaits RuntimeError). Still not passing |

The masked flips are a property of the gauntlet's own helper, which the
repair discipline does not permit the repair author to edit. The lane must
decide how the gauntlet helper obtains a legitimate grant (a capability
issued in the test fixture) before DCX-03/DCX-04 can be measured again.

## Full suite (same command both trees: `python3 -m unittest discover -s dclm -p 'test_*.py'`; 392 tests each)

Unique not-passing tests: repair-15 tree 34 → repair-16 tree 40. Every delta
is accounted for:

- **Resolved (3):** the DCX-02 gauntlet test (genuine) + the two masked
  gauntlet flips above.
- **Mode change (1):** signing-failure test FAIL → ERROR (masked shadow).
- **Newly failing (9)** — every one presents a bare-string `"internal"`
  claim in its own body and asserts the grant the defect used to give.
  These tests encode the defect; they are named here for contract
  amendment, and were NOT edited by this repair:
  - `test_rights_writes.TestRightsPurity.test_internal_write_tier` — its own
    docstring states the defect as doctrine: "All commit kinds currently
    grant for the asserted internal label."
  - `test_rights_writes.TestRightsPurity.test_write_tier_requires_identity_for_every_commit_kind`
    — tested identity-gate reasons through the forged-label path; the source
    gate now (correctly) refuses first.
  - `test_rights_writes.TestCommitBoundary.test_each_writable_kind_commits` (ERROR)
  - `test_rights_writes.TestCommitBoundary.test_tampered_commit_receipt_fails_verification` (ERROR)
  - `test_winter.RightsBoundaryTests.test_winter_kinds_commit_through_dclm_commit` (ERROR)
  - `test_winter.RightsBoundaryTests.test_winter_kinds_grant_for_dclm_internal_only`
  - `test_tap.TapTestCase.test_tap_outflow_in_commit_kinds`
  - `test_tokenize.TestMintExclusivity.test_new_commit_kinds_whitelisted`
  - `test_tokenize.TestRegressions.test_rights_writes_green` — a runner that
    asserts the test_rights_writes suite is green; it inherits the set above.
- **Production-path regressions: zero.** No test that reaches the write tier
  through a migrated component's own functions newly failed. All other
  not-passing tests are identical between the trees (name-normalized
  comparison; the earlier 417-test figure came from a wider discovery scope
  and is not the basis of this comparison).

## Verdict at the author's seat

DCX-02 is repaired at the rights boundary, by execution, with the blast
radius fully enumerated: 1 genuine gauntlet pass, 2 masked flips disclosed,
9 defect-encoding legacy tests named for amendment, 0 production regressions.
The repair stands as REPORTED-by-author until an independent seat reproduces
it. What remains for the lane: (1) independent verification (Grok, queued);
(2) the gauntlet-helper question; (3) contract amendments for the 9 named
legacy tests; (4) the open least-privilege kind-binding question, filed
under DCX-03.
