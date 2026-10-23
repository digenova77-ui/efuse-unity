"""HIGHEST-ORDER PURE LEARNING — applied to Iris.

Elevates the predict → observe → signal → pace loop to its cleanest
scientific form while remaining inside the diamond boundary:

- Preference signal (RLHF shape): matched/unmatched is a pairwise
  correctness judgment.
- Inferred advisory factor (IRL shape): a bounded confidence derived
  from those judgments.
- No gradient. No exemplar mutation. No reward that can be optimized
  against law.
- LAW WINS absolute. NOT_FOR_EMISSION absolute.
- Every step receipted. Core integrity gate unchanged.

What Iris receives:
- A pure, bounded confidence pace.
- An explicit expectation contract.
- A fail-closed path: missing prediction → observation refused.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from iris_state import IrisState
from pure_pace import pace_factor, apply_pace, expectations
from learning_signal import observe_with_signal, accuracy
from self_learning import predict

LABEL = "HIGHEST-ORDER PURE LEARNING"


def elevate_and_apply(key: str,
                      judgment: Dict[str, Any],
                      outcome: Dict[str, Any],
                      margin: float = 0.5,
                      state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Full highest-order cycle applied to one held-out case.

    1. predict
    2. observe_with_signal
    3. pure pace on the supplied margin
    Returns the advisory result. Never mutates law or core.
    """
    st = state or IrisState()
    pred = predict(key, judgment, state=st)
    sig = observe_with_signal(key, outcome, state=st)
    paced = apply_pace(margin, st)
    return {
        "label": LABEL,
        "key": key,
        "prediction_receipt": pred.get("receipt_id"),
        "signal_receipt": sig.get("signal_receipt_id"),
        "matched": sig.get("matched"),
        "advisory_margin": paced["advisory_margin"],
        "factor": paced["factor"],
        "law": "LAW WINS — advisory only",
        "boundary": "NOT_FOR_EMISSION",
        "integrity": "UNCHANGED — core not touched",
        "expectations": expectations()["expects"],
    }


def contract() -> Dict[str, Any]:
    """The highest-order contract Iris operates under."""
    return {
        "label": LABEL,
        "scientific_shape": [
            "RLHF-like preference: matched vs unmatched delta",
            "IRL-like inference: bounded confidence from those preferences",
            "No policy gradient, no reward hacking surface against law",
        ],
        "iris_receives": [
            "Receipted prediction",
            "Receipted observation + delta",
            "LEARNING_SIGNAL (NOT_FOR_EMISSION)",
            "Advisory pace factor in [0.85, 1.15]",
        ],
        "iris_must_refuse": [
            "Overriding a deterministic REFUSE",
            "Mutating exemplars or iris_core.py",
            "Letting accuracy affect standing or emission",
            "Observing without a prior prediction",
        ],
        "integrity": "UNCHANGED — core not touched",
    }
