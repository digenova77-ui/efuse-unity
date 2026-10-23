"""OMNI — one pure view over the available intelligence.

Reads:
  - diamond playground (clarity / color / cut gate)
  - frontier protocol (maximum band)
  - Iris pure pace (advisory confidence)
  - learning signal (NOT_FOR_EMISSION)
  - highest-order contract

Writes nothing. Mutates nothing.
LAW WINS. Origin immutable. Learning advisory only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iris-intake"))
sys.path.insert(0, str(ROOT / "playground"))

from diamond_playground import DiamondPlayground, grade
from frontier_protocol import frontier_report
from pure_pace import pace_factor, expectations
from learning_signal import accuracy
from highest_order import contract
from iris_state import IrisState

LABEL = "OMNI"


def omni(state: Optional[IrisState] = None,
         playground: Optional[DiamondPlayground] = None) -> Dict[str, Any]:
    """Single pure snapshot across all available layers."""
    st = state or IrisState()
    pg = playground or DiamondPlayground()
    fr = frontier_report(pg)
    pace = pace_factor(st)
    acc = accuracy(st)
    return {
        "label": LABEL,
        "diamond": {
            "floor_holds": pg.floor_holds(),
            "rise_ok": pg.rise().get("ok", False),
            "ceiling_reached": pg.ceiling().get("reached", False),
            "facets": [
                {"name": f.name, "verdict": grade(f)["verdict"]}
                for f in pg.facets if f.kind != "ceiling"
            ],
        },
        "frontier": {
            "protocol": fr["protocol"],
            "facing": fr["facing"],
            "held_count": len(fr["held"]),
            "ceiling_claimable": fr["ceiling_claimable"],
        },
        "learning": {
            "accuracy": acc.get("accuracy"),
            "pace_factor": pace.get("factor"),
            "boundary": acc.get("boundary"),
        },
        "contract": {
            "law": "LAW WINS",
            "origin": "immutable",
            "refuses": contract().get("iris_must_refuse", []),
        },
        "integrity": "UNCHANGED — core not touched",
    }


def omni_brief(state: Optional[IrisState] = None) -> str:
    """One-line Omni status."""
    o = omni(state)
    return (
        f"OMNI  floor={'HOLD' if o['diamond']['floor_holds'] else 'FAIL'}  "
        f"ceiling={'REACHED' if o['diamond']['ceiling_reached'] else 'HELD'}  "
        f"frontier_claimable={o['frontier']['ceiling_claimable']}  "
        f"pace={o['learning']['pace_factor']}  "
        f"boundary={o['learning']['boundary']}"
    )
