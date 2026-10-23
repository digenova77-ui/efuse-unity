"""IRIS LEARNING SIGNAL — receipted accuracy for tokenomics observation.

Elevates self_learning.observe with a pure LEARNING_SIGNAL receipt.
Tokenomics may READ the signal (transparency, confidence weighting).
Tokenomics must NOT use it for emission or standing.
Emission continues to read standing() only. Origin remains immutable.
Core integrity gate unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from iris_state import IrisState
from self_learning import observe as _observe, summary as _summary

LABEL = "IRIS LEARNING SIGNAL"


def observe_with_signal(key: str,
                        outcome: Dict[str, Any],
                        provenance: str = "REPORTED",
                        state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Observe + emit a LEARNING_SIGNAL receipt.

    The signal is a pure projection of the delta. It does not mint,
    does not alter standing, and does not touch iris_core.py.
    """
    st = state or IrisState()
    obs = _observe(key, outcome, provenance=provenance, state=st)

    # Pure signal derived from the observation just written
    delta = (st.learnings.get(f"observe:{key}") or {}).get("value", {}) \
            .get("judgment", {}).get("delta", {})
    signal_payload = {
        "label": LABEL,
        "key": key,
        "matched": delta.get("matched"),
        "predicted_verdict": delta.get("predicted_verdict"),
        "actual": delta.get("actual"),
        "note": "signal only — emission reads standing(), never this",
        "boundary": "NOT_FOR_EMISSION",
    }
    receipt = st.record_learning(
        f"signal:{key}",
        signal_payload,
        provenance="DERIVED",
    )
    return {
        "ok": True,
        "observation": obs,
        "signal_receipt_id": receipt["receipt_id"],
        "matched": delta.get("matched"),
        "integrity": "UNCHANGED — core not touched",
        "boundary": "NOT_FOR_EMISSION",
    }


def accuracy(state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Pure reader for tokenomics. No mutation.

    Returns held-out accuracy. Explicitly marked not for emission.
    """
    st = state or IrisState()
    s = _summary(st)
    total = s["observations"]
    acc = (s["matched"] / total) if total else None
    return {
        "label": LABEL,
        "accuracy": acc,
        "matched": s["matched"],
        "observations": total,
        "boundary": "NOT_FOR_EMISSION",
        "standing_source": "origin only — meter.py reads standing()",
        "integrity": "UNCHANGED — core not touched",
    }
