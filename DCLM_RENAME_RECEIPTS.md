# DCLM Rename Sweep — Receipts

**Date:** 2026-10-06 ~08:55 EDT
**Law:** DCLM = **Deterministic Compute Logic Machine** (the computer). NOT "DualisCapax Logic Model." The company is DualisCapax.
**Scope:** `~/workspace/unity-world/` — docs, .py docstrings/comments, .json/.yaml description fields, website copy (`client/`, `gate/`). Binary/`__pycache__` skipped.

## Result: NO REPLACEMENTS NEEDED

**Files changed:** 0
**Total replacements:** 0

Every expansion of the DCLM acronym was searched for, in all case variants and identifier forms:
- `DualisCapax Logic Model` / `dualis capax logic model` — **0 hits**
- `DualisCapax Logic Machine` / `Dualis Capax Logic Machine` — **0 hits**
- `DualisCapaxLogic*` (CamelCase), `dualis_capax_logic*`, `dualis-capax-logic*` — **0 hits**
- `logic model` / `logic machine` standalone, anywhere — **0 hits**
- Multiline-spanning `dualis…capax…logic…model` matches (Python regex scan of whole tree) — **0 hits**
- `DCLM =` / `DCLM —` / `stands for` style definitions — **0 hits**
- JSON/YAML `description`/`title` fields expanding DCLM — **0 hits**

## What IS present (all correct, untouched per sweep rules)

- The acronym **DCLM** stands alone in 162 files — exactly the law's separation: DCLM is the computer, used as a bare proper name everywhere.
- Parenthetical role labels like `DCLM (logic)`, `DCLM (pure logic)`, `DCLM (deterministic)` — role descriptions, not acronym expansions. Left alone.
- Standalone **DualisCapax** (22 hits): the company name, `dualiscapax.ai` domain, "DualisCapax DCLM WASM", "DualisCapax architecture", "DualisCapax Economic System" — company references only. Left alone per rule 3.

## Old → new strings applied

_None — no wrong expansions existed in the tree._

## DEFERRED list (mtime-collision avoidance)

_Empty._ No file required editing, so no file was opened for edit and no collision check was triggered. The max-purity worker's files (`dclm/purify.py`, `dclm/meter.py`, `dclm/token_engine.py`, `dclm/onboard.py`, `dclm/share.py`, `dclm/tap.py`, `dclm/winter.py`) and the wallet worker's `economics/*` files were observed to be modified within the last 30 minutes, but were never touched by this sweep — read-only grep only.

## Verification

Re-grep after sweep for all old expansions → **zero hits** anywhere in `~/workspace/unity-world/` (excluding this receipts file, which quotes them historically). Verified: YES.

## Observation for a wider sweep (out of scope, no action taken)

The old expansion **"DualisCapax Logic Model"** does exist outside `unity-world` in the wider workspace (e.g., `~/workspace/user/sima-dclm-spec.md` — the SIMA-DCLM official spec V1 — and the `dccp-world` law docs, per memory). If the rename is meant to hold workspace-wide, a second sweep pass on `~/workspace/user/`, `~/workspace/dccp-world/`, and memory references may be wanted. This worker stayed inside its assigned scope.
