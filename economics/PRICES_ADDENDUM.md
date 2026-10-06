# PRICES ADDENDUM — new rows #101/#102 and stale-language resolution

**Date:** 2026-10-06 (Worker 1, unified economic model build)
**Engine:** `~/workspace/unity-world/economics/pricing.py`

## What was added

Two new factory-verdict rows, past the old index's 33 — the #1 ranked
improvement vector is the decision; the price is the REPORTED cost surface
the decision touches. Both maps state **no modeled dollar savings** on
their #1 vectors, so no modeled figure is banked here.

### Row #101 — Uber Technologies, Inc. (factory-101)

- **Decision (#1 vector):** V1. The platform take-rate machine: gross bookings
  $162,773M → $193,454M (+19%); revenue $43,978M → $52,017M; revenue margin
  27.0% → 26.9% FY; Q4 Mobility 30.3% (+160 bps YoY), Delivery 18.7% (+40 bps YoY)
- **REPORTED cost surface (USD):**
  - Gross bookings $162,773M (2024) → $193,454M (2025) — REPORTED-via-mirror
  - Total revenue $43,978M (2024) → $52,017M (2025) — REPORTED-via-mirror
  - Q4 revenue margin: Mobility 30.3% (+160 bps YoY), Delivery 18.7% (+40 bps YoY) — REPORTED-via-secondary
- **Row label:** REPORTED (engine-normalized; custody preserved per figure)
- **Claim hash:** `e75e4302836047626360dbc4b8985e60b799b37e35605514cd6ae5d53690061a`
- **Seal:** ED-SEAL-20260929-CORPHELPERS-UBER-V1 (rank #101, B1 RECONCILED-EXACT)
- **Source:** `~/workspace/goals/rte-wave-program-the-next-meaningful-things/hidden_files/ed-corp-helpers-uber-entry-20260929.md`

### Row #102 — Massachusetts Mutual Life Insurance Company (factory-102)

- **Decision (#1 vector):** V1. The whole-life protection franchise: ~$1.1T life
  insurance in force; premium income $21,288M → $21,777M; record domestic
  insurance sales >$41B → >$43B; whole-life sales No. 2 (LIMRA)
- **REPORTED cost surface (USD):**
  - Premium income $21,288M (2024) → $21,777M (2025) — REPORTED-via-mirror
  - Life insurance in force ~$1.1T (approx) — REPORTED-via-mirror
  - Domestic insurance sales >$41B (2024) → >$43B (2025) (approx) — REPORTED-via-secondary
- **Row label:** REPORTED (engine-normalized; custody preserved per figure)
- **Claim hash:** `820275aaf5eaaf38ef14f62b84057c1f1f07022555a03c1b024a27e6c606d54c`
- **Seal:** ED-VERDICT-20260929-CORPHELPERS-MASSMUTUAL-V1 (rank #102, B1 FENCED — databahn $43,072M vs statutory $34,232M, delta banked not averaged)
- **Source:** `~/workspace/goals/rte-wave-program-the-next-meaningful-things/hidden_files/ed-corp-helpers-massmutual-entry-20260929.md`

## Stale-language resolution (the old "57 missing")

The old `~/workspace/keys/PRICES.md` (Gaps §1) said: **"90 sealed vs 33 maps on
disk → the other 57 verdicts' paperwork was NOT pulled"** ("57 missing").
That arithmetic is stale. Verified on disk 2026-10-06:

| Measure | Verified value | Where |
|---|---|---|
| Factory sealed count | **102/102** (Uber #101, MassMutual #102) | `corporate-helpers-queue-20260929.md` roll-up: "All 102 entries sealed" |
| Entry papers on disk | 75 `ed-corp-helpers-*-entry-20260929.md` files | `hidden_files/` (includes uber + massmutual) |
| Improvement maps on disk | 38 `*-improvement-map-20260929.md` files | `hidden_files/` |
| Old index (PRICES.md) | 51 decisions (33 factory + 2 RTE + 16 claims) | `~/workspace/keys/PRICES.md` |
| Engine index (this build) | **53 rows** (33 factory + 2 RTE + 16 claims + **#101 + #102**) | `pricing.py` |

Resolution: the "57 missing" (90 − 33) language is retired. The honest state is:
**102 sealed at the factory; the engine now prices 53 decisions.** Factory rows
**#34–#100 remain unindexed** — sealed at the factory but not yet carried into
the pricing index. That is a pending extension (via `extend_index`, with
receipts), **not invented data** — no row is added without its sealed entry
paper and its REPORTED cost surface.

## Benchmark / reference / evolve (David's law)

- **Benchmark:** old 51-row index state, sha256 `16f693fff1ffdeed362503ba8634c546b3f7d8b0d013d8397f7e1bf163250344`
- **Reference:** this build's 53-row index, sha256 `603a9e7704984358544e5effd220e120d69c1f17254995d54d7d3e9314fe0f03` (receipt in `index_receipts.log`, actor `build-20261006-worker1`)
- **Evolve:** future rows enter only through `extend_index()`, which validates
  every figure's provenance label first and writes a before/after receipt.
  Every mutation needs a receipt — no exceptions.

## Honesty notes carried into the engine

- Rows #4 (broadcom), #11 (deere), #20 (intelcorporation) carry MODELED-DERIVED
  primary figures (debt stacks computed from reported components). They are
  labeled **DERIVED**, never REPORTED — modeled figures are never presented as real.
- Figures with no custody label in PRICES.md (e.g. broadcom cash, abbvie SG&A)
  are labeled **UNKNOWN** at the figure level and marked explicitly — never inflated.
- Claims rows: the verdict IS the price; dollar cost N/A (not UNKNOWN — the
  question doesn't apply). UNKNOWN prices never pass and pay nothing.
- Old-index date anomalies (conocophillips, deere filenames) and the 9 maps
  without a "Cost baseline" section are carried as per-row notes, as in PRICES.md.
- The old index's truncated claim hashes are stored as-published (`…` suffix).
