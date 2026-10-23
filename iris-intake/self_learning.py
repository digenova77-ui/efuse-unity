"""IRIS SELF-LEARNING — held-out prediction → outcome → delta.

Builds on learning_pulse. Never mutates iris_core.py or the pinned
integrity receipt. Every step is a receipted learning. Core gate unchanged.

Usage:
    from self_learning import predict, observe, summary
    r = predict("held_out:unity_transfer",
                judgment={"verdict": "REFUSE", "law_wins": True})
    observe("held_out:unity_transfer",
            outcome={"actual": "REFUSE", "matched": True})
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from iris_state import IrisState
from learning_pulse import pulse

LABEL = "IRIS SELF-LEARNING"


def predict(key: str,
            judgment: Dict[str, Any],
            provenance: str = "DERIVED",
            state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Record a held-out prediction. Receipted. Core untouched."""
    if not isinstance(judgment, dict):
        raise ValueError("judgment must be a dict")
    return pulse(
        key=f"predict:{key}",
        judgment={
            "phase": "PREDICT",
            "label": LABEL,
            "judgment": judgment,
            "note": "prediction only; outcome not yet observed"
        },
        provenance=provenance,
        state=state,
    )


def observe(key: str,
            outcome: Dict[str, Any],
            provenance: str = "REPORTED",
            state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Record the observed outcome and the delta against the prediction.

    Fail-closed: refuses if no prior prediction exists for the key.
    """
    if not isinstance(outcome, dict):
        raise ValueError("outcome must be a dict")
    st = state or IrisState()
    pred_key = f"predict:{key}"
    prior = st.learnings.get(pred_key)
    if prior is None:
        raise ValueError(f"no prediction for {key!r} — observation refused")

    predicted = (prior.get("value") or {}).get("judgment", {}).get("judgment", {})
    matched = outcome.get("actual") == predicted.get("verdict")
    delta = {
        "predicted_verdict": predicted.get("verdict"),
        "actual": outcome.get("actual"),
        "matched": matched,
        "note": "delta computed; core integrity gate unchanged"
    }
    return pulse(
        key=f"observe:{key}",
        judgment={
            "phase": "OBSERVE",
            "label": LABEL,
            "outcome": outcome,
            "delta": delta,
            "prior_receipt": prior.get("receipt_id"),
        },
        provenance=provenance,
        state=st,
    )


def summary(state: Optional[IrisState] = None) -> Dict[str, Any]:
    """Pure projection over learnings. No mutation."""
    st = state or IrisState()
    preds = [k for k in st.learnings if k.startswith("predict:")]
    obs = [k for k in st.learnings if k.startswith("observe:")]
    matched = 0
    for k in obs:
        d = (st.learnings[k].get("value") or {}).get("judgment", {}).get("delta", {})
        if d.get("matched") is True:
            matched += 1
    return {
        "label": LABEL,
        "predictions": len(preds),
        "observations": len(obs),
        "matched": matched,
        "unmatched": len(obs) - matched,
        "integrity": "UNCHANGED — core not touched",
        "last_receipt": st.meta.get("last_receipt"),
    }
