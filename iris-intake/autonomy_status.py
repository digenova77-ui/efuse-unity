"""AUTONOMY STATUS — pure receipt emitter.

Emits a signed status receipt. Never modifies law, core, or integrity pin.
UNKNOWN if state cannot be read.
"""
from __future__ import annotations

from iris_state import IrisState

def emit_status(state: IrisState | None = None) -> dict:
    try:
        st = state or IrisState()
        summary = st.summary()
        receipt = st._receipt("AUTONOMY_STATUS", {
            "summary": summary,
            "note": "pure status loop; law unmodified"
        })
        return {
            "ok": True,
            "receipt_id": receipt["receipt_id"],
            "status": summary,
            "integrity": "UNCHANGED"
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "UNKNOWN",
            "error": str(e),
            "integrity": "UNCHANGED"
        }
