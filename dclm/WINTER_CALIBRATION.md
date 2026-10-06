# WINTER TRIGGER CALIBRATION

**Status: every threshold below is PROPOSED. None is decided. Final numbers are HELD-FOR-DAVID — his word, his call, per his standing rule.**

Testnet only. All amounts in test-keys, clearly TEST.

## What this document is

The winter mechanism (`winter.py`) has two layers:

1. **Structure (decided by the build, David's binding words):** summer/winter
   as a continuous gradient 0.0→1.0 with no phase cliffs; winter flow as
   PROTECTION never accumulation; the survival-need cap; every stored unit
   receipted with its winter reason; phantom claims refused and logged for
   L5; UNKNOWN never PASS (unreadable signal → stays SUMMER).
2. **Calibration (PROPOSED below, awaiting David):** the band edges, the
   softnesses, the weights, the cap, the emission floor, the claim floor.
   The structure works with any numbers; the numbers decide how jumpy or
   how calm the winter is. That is a judgment call, and it is his.

## The trigger structure (built, not proposed)

Three candidate signals combine into one gradient:

- **Peg stress** — |peg deviation| beyond the band edge starts a tilt.
- **Real-economy contraction** — measured activity drop beyond the edge starts a tilt.
- **Crisis** — declared AND verified counts at full weight; declared-but-unverified is NOT a signal (it is a phantom candidate).

Each numeric signal passes through the tilt curve
`tilt(x) = max(0, 2·(sigmoid(x) − 0.5))` with `x = (stress − edge) / softness`:
stress below the edge contributes nothing, stress at the edge starts to
rise, deep stress saturates toward 1 — smoothly, no cliff at the edge.
The gradient is the weighted sum, clamped to [0, 1]. Small signal changes
always produce small gradient changes (tested: max step < 0.02 over a
400-step sweep of each signal).

Labels SUMMER / TILTING / WINTER at gradient 0.25 / 0.75 are **display
only** — the throttle, the store, and the release all read the continuous
gradient. There is deliberately no behavioral cliff at a label line.

## Proposed thresholds (ALL HELD-FOR-DAVID)

| # | Constant | Proposed | Reasoning for the proposal | What David must decide |
|---|----------|----------|----------------------------|------------------------|
| 1 | `PEG_BAND_EDGE` | 0.02 (2%) | A 2% peg deviation is where "under stress" starts to mean something in most band designs; below that is noise. The edge is where the tilt *begins*, not a switch. | Is 2% the right onset of stress, or should the root start protecting earlier/later? |
| 2 | `PEG_BAND_SOFT` | 0.01 (1%) | At edge+2×soft (4% deviation) the tilt is ~0.76; at edge+4×soft (6%) ~0.96. So the mechanism goes from "noticing" to "nearly full winter on this signal" across a 4-point band — fast enough to matter, slow enough to be smooth. | How fast should peg stress saturate: a hair-trigger or a slow lean? |
| 3 | `ACTIVITY_DROP_EDGE` | 0.15 (15%) | A 15% measured activity drop is a real contraction, not weekly noise; below that the economy is assumed to be breathing normally. | What counts as a real-economy contraction worth protecting against? |
| 4 | `ACTIVITY_DROP_SOFT` | 0.05 (5%) | At 25% drop the tilt is ~0.76 — deep recession reads as deep winter on this signal. | Same as #2, for the real economy. |
| 5 | `WEIGHT_PEG` / `WEIGHT_ACTIVITY` / `WEIGHT_CRISIS` | 0.35 / 0.35 / 0.30 | Peg stress and real contraction are the two honest economic signals and share the load; a verified crisis is a human judgment layered on top, slightly lighter so no single declared event can max the gradient alone. Note: even all three at full tilt clamp at 1.0 — the weights shape the middle, not the ends. | The relative voice of each signal. Should a verified crisis outweigh the numbers, or the numbers outweigh the declaration? |
| 6 | `SURVIVAL_NEED_CAP` | 25 test-keys per identity | The root stores only what it needs to survive. 25 test-keys is 5 COMPUTE runs or 25 SEARCHes — enough for the creator's capacity to keep building through a storm, small enough that it can never become accumulation. Anything above the cap keeps flowing outward. | How much does the root need to survive a winter? This is the "protection vs accumulation" line — his most important number here. |
| 7 | `EMISSION_FLOOR` | 0.25 | At full winter, emission runs at 25% of summer: the economy slows to protect the core but never freezes. Zero would be a shutdown; the model says protection, not shutdown. | How slow is winter allowed to get? |
| 8 | `WINTER_CLAIM_MIN_GRADIENT` | 0.10 | A store claim needs at least this much evaluated winter pressure, or it is the phantom pattern (claiming crisis to pull value inward). 0.10 means a single signal has to be genuinely tilting — e.g. peg deviation ≈ 3.5% — not just twitching. Below it: refused as PHANTOM, logged for L5. | How much proof should a winter claim carry? Lower = easier to store, easier to game; higher = safer, but a real early winter might be locked out. |
| 9 | `LABEL_SUMMER_MAX` / `LABEL_WINTER_MIN` | 0.25 / 0.75 | Display-only bands. Chosen so TILTING is the wide middle where most real weather lives. | Only matters for what humans read; still his words if he wants different ones. |

## Design decisions the worker made (David can overturn)

- **Partial reads:** if one signal is readable and another is not, the gradient is computed from what is readable (missing inputs contribute 0) and the receipt notes which inputs were UNKNOWN. Rationale: a dead sensor should not blind the live ones. Alternative he could order: any UNKNOWN input forces the whole signal UNKNOWN.
- **Release needs no signal:** moving value OUT of the reserve (the summer direction) cannot game winter, so `winter_release` requires the winter reason but not a supporting signal. It is still receipted and logged for L5.
- **Partial stores:** a store request larger than the remaining room under the cap stores what fits and leaves the excess in circulation, with the receipt recording requested / stored / excess. Alternative: refuse the whole request. The worker chose the sap reading — what fits flows down, the rest keeps feeding the canopy.
- **Crisis weight is binary:** a verified crisis contributes its full 0.30, not a gradient. Rationale: verification is itself the measurement; there is no "slightly verified."

## What is NOT decided here (open, honest)

- The actual peg band of the live economy (this mechanism reads a deviation fraction; who publishes the band center is outside this module).
- What "measured activity" is (the input is a fractional change; the measurement pipeline is a separate build).
- The crisis verification channel (who can verify, how — this module only checks the verified flag and its provenance label).
- L5's audit tooling (this module writes the trail; L5 reads it).

## How David decides

Each row above has a question addressed to him. His word on any number
changes one named constant in `winter.py` — the structure does not move.
Until he speaks, the proposals stand as the working calibration, clearly
marked PROPOSED everywhere they appear (code comments, receipts, and
this document).
