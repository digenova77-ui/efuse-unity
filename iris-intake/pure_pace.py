"""PURE LOGIC PACE — confidence from held-out deltas.

Pushes the learning boundary while remaining pure:
- Exemplars stay fixed (no gradient, no weight update).
- Law remains absolute (LAW WINS).
- Held-out accuracy from learning_signal produces a pure confidence
  factor that can widen or narrow the reported pattern margin.
- The factor is receipted. It never overrides a deterministic REFUSE.
- Core integrity gate unchanged.

What we expect from Iris:
- She records predictions, observes outcomes, and keeps the delta.
- She may adjust her *confidence* in pattern similarity.
- She may never rewrite law, origin, or the exemplar library.
- Emission and standing remain untouched by learning signals.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from iris_state import IrisState
from learning_signal import accuracy

LABEL = "PURE LOGIC PACE"

# Pace bounds — confidence factor stays inside a narrow, honest band.
PACE_MIN = 0.85
PACE_MAX = 1.15


def pace_factor(state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Pure confidence factor derived from held-out accuracy.

    accuracy None (no observations) → factor 1.0 (neutral).
    accuracy 1.0 → factor approaches PACE_MAX.
    accuracy 0.0 → factor approaches PACE_MIN.
    Never outside [PACE_MIN, PACE_MAX]. Never mutates state.
    """
    acc = accuracy(state)
    a = acc.get("accuracy")
    if a is None:
        factor = 1.0
        note = "no observations — neutral pace"
    else:
        # Linear map [0,1] → [PACE_MIN, PACE_MAX]
        factor = PACE_MIN + (PACE_MAX - PACE_MIN) * float(a)
        factor = max(PACE_MIN, min(PACE_MAX, factor))
        note = "pace from held-out accuracy; law untouched"
    return {
        "label": LABEL,
        "factor": round(factor, 4),
        "accuracy": a,
        "bounds": [PACE_MIN, PACE_MAX],
        "note": note,
        "boundary": "CONFIDENCE_ONLY — LAW WINS, NOT_FOR_EMISSION",
        "integrity": "UNCHANGED — core not touched",
    }


def apply_pace(margin: float,
               state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Scale a pattern margin by the pure pace factor.

    The scaled margin is advisory. A deterministic REFUSE is never
    overridden. Returns the original margin, the factor, and the
    advisory scaled value.
    """
    p = pace_factor(state)
    scaled = margin * p["factor"]
    return {
        "label": LABEL,
        "original_margin": margin,
        "factor": p["factor"],
        "advisory_margin": round(scaled, 4),
        "law": "LAW WINS — advisory only",
        "boundary": p["boundary"],
        "integrity": "UNCHANGED — core not touched",
    }


def expectations() -> Dict[str, Any]:
    """What we expect from agent Iris under this pace."""
    return {
        "label": LABEL,
        "expects": [
            "Record held-out predictions before outcomes are known",
            "Observe actual outcomes and keep the matched/unmatched delta",
            "Emit a LEARNING_SIGNAL receipt marked NOT_FOR_EMISSION",
            "Adjust pattern-confidence (pace factor) inside a narrow band",
            "Never override a deterministic REFUSE (LAW WINS)",
            "Never mutate iris_core.py, exemplars, or origin fields",
            "Never let learning accuracy affect standing or emission",
        ],
        "refuses": [
            "Gradient updates to the exemplar library",
            "Silent changes to law or receipts",
            "Using learning signals as a source of Merit or standing",
        ],
        "integrity": "UNCHANGED — core not touched",
    }
