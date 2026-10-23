"""IRIS LEARNING PULSE — held-out judgments, receipted only.

Transforms existing IrisState. Never mutates iris_core.py or the pinned
integrity receipt. Daemon still refuses to start on core drift.

Usage:
    from learning_pulse import pulse
    pulse(key="held_out:unity_transfer_perfect_paperwork",
          judgment={"mode": "hybrid", "law_wins": True, "verdict": "REFUSE"})
"""
from __future__ import annotations

from typing import Any, Dict

from iris_state import IrisState

LABEL = "IRIS LEARNING PULSE"

def pulse(key: str, judgment: Dict[str, Any],
          provenance: str = "DERIVED",
          state: IrisState | None = None) -> Dict[str, Any]:
    """Record one held-out learning. Receipted, versioned, never silent."""
    if not isinstance(key, str) or not key.strip():
        raise ValueError("learning key required")
    if not isinstance(judgment, dict):
        raise ValueError("judgment must be a dict")
    st = state or IrisState()
    receipt = st.record_learning(key.strip(), {
        "label": LABEL,
        "judgment": judgment,
        "note": "held-out pulse; core integrity gate unchanged"
    }, provenance=provenance)
    return {
        "ok": True,
        "key": key.strip(),
        "receipt_id": receipt["receipt_id"],
        "learnings_count": len(st.learnings),
        "integrity": "UNCHANGED — core not touched"
    }
