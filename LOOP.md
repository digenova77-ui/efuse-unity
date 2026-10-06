# THE LOOP — Keep → Evolve → Fix → Discard, until loop end

**David's standing order (2026-10-06):** LOOP PROCESS UNTIL LOOP END, TARGET UNDEFINED.

## The loop

```
┌──────────────────────────────────────────────────┐
│  PASS N                                          │
│    1. BUILD      workers complete their pieces   │
│    2. MEASURE    loop.py runs every test suite   │
│                  + the purity index scores live  │
│    3. AUDIT      four-bucket disposition per      │
│                  component: KEEP / EVOLVE /       │
│                  FIX / FALSE GOLD (§7 PURITY.md) │
│    4. APPLY      fixes fixed, false gold          │
│                  discarded, evolutions built     │
│    5. MEASURE    index re-scores                  │
│  → if termination condition met: LOOP END        │
│  → else: PASS N+1                                │
└──────────────────────────────────────────────────┘
```

## Termination (emergent, not a deadline)

The loop ends itself when ALL of the following hold:

1. The purity index (`purity/index.py`) returns aggregate **PURE** (exit 0).
2. It holds across **2 consecutive passes** — one pure reading is a snapshot, two is a state.
3. The audit finds **zero FIX items** (nothing broken left) and **zero FALSE GOLD items** (nothing false left).
4. Every component test suite passes.

Purity is the termination condition, not a date. There is no milestone, no fixed endpoint. The loop runs until there is nothing left to fix and nothing left to discard.

## Rules of the loop

- **Every pass is measurable.** No pass completes without the index score on record (`passes/pass-N.json`).
- **The index is honest.** If a pass scores FAIL, the loop continues. A failing pass is information, not failure.
- **False gold is discarded, never repaired.** Fix what's fixable; throw out what's false.
- **Evolve, don't rebuild.** Each pass benchmarks against the last (benchmark → reference → evolve).
- **UNKNOWN never PASS.** Unmeasurable components keep the loop running.
- **The loop runner never invents.** `loop.py` measures and reports. Dispositions are applied by workers, judged by the audit.

## Pass history

| Pass | Date (UTC) | Index | Tests | Disposition | Notes |
|---|---|---|---|---|---|
| 1 | — | — | — | — | armed; begins when active workers land |

## Files

- `loop.py` — the runner: discovers and executes every test suite + the purity index, writes `passes/pass-N.json` and updates this table.
- `passes/` — one JSON record per pass. The record is the truth of the loop.
