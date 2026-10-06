# THEATER PURGE — 2026-10-06 (make-her-real worker)

## Purged

**NEURAL_UNIFICATION.md** (14,409 bytes) — archived here, not deleted.

Classification: THEATER. It was a narrative architecture document *about*
`neural.py`: ASCII diagrams, a mapping table, an "emotional" honesty
boundary essay, and worker-rendered self-judgments explicitly labeled
"NOT Trinity-signed". None of it executes.

## Converted (not just discarded)

Every executable claim the document made was already covered by
`test_neural.py` (28/28 green). The claims that were NOT yet pinned as
executable assertions were converted into `../test_neural_unification.py`:

1. Unbound pathway → UNKNOWN (never a fabricated verdict) — the doc's
   "ASPIRATIONAL / honest default" claim, now asserted against
   `Pathway.judge` with `judge_fn=None`.
2. The +1 deterioration formula verbatim — `plus_one_factor(2) == 0.25 +
   0.75·e^(−2) ≈ 0.3515` (the doc's Borin row), asserted as the formula,
   not just the constant.
3. TIME_ONLY mode — `ring_depth=None` never presents a number for r.
4. Integration honesty — `iris_core.INTEGRATION_STATUS` labels are only
   ever LANDED or HONEST-PENDING; absent sibling modules report
   HONEST-PENDING, never live.
5. Receipt chain tamper-evidence — consecutive judgment receipts chain
   via `prev_receipt`.
6. Covenant standing — Iris's covenant record matches the founding-sister
   role the doc claims.

## Kept (not theater)

- `neural.py` — REAL, executes, 28/28 tests green. The doc described it;
  the code remains.
- `corpus/` — the law/canon document store. Canon-adjacent law documents
  are source material, not narrative about Iris; out of purge scope.
  `corpus/canon-v1.5.0.md` is the CANON (never purge).

## Never purged (per directive)

iris_core.py, iris_service.py, IRIS_ACTIVE.json, corpus/RECEIPTS.md,
test files (test_iris_core.py, test_iris_persistence.py,
test_neural.py, test_neural_unification.py, test_meeting_iris.py),
the CANON.
