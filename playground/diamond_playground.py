"""DIAMOND PLAYGROUND — floor → mesh → ceiling.

Three gates on every facet: clarity, color, cut.
A facet passes only if all three are pure and it reflects purity.
One failed scale → glass → rise refused → ceiling not reached.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# Clarity
CLARITY_SCORE = {"FL": 1.0, "VVS": 0.95, "VS": 0.85, "SI": 0.6, "I": 0.3}
CLARITY_PASS = {"FL", "VVS", "VS"}

# Color (GIA-style). Colorless band passes.
COLOR_SCORE = {c: 1.0 - i * 0.04 for i, c in enumerate("DEFGHIJKLMNOPQRSTUVWXYZ")}
COLOR_PASS = {"D", "E", "F"}

# Cut
CUT_SCORE = {"Excellent": 1.0, "Very Good": 0.9, "Good": 0.75, "Fair": 0.5, "Poor": 0.3}
CUT_PASS = {"Excellent", "Very Good"}


@dataclass(frozen=True)
class Facet:
    name: str
    kind: str
    clarity: str = "FL"
    color: str = "D"
    cut: str = "Excellent"
    reflects: str = "purity"


def grade(f: Facet) -> dict:
    """Score each scale and return a structured purity judgment.

    Pure only if every scale is in its pass band AND the facet reflects purity.
    Returns scores, pass/fail per scale, and an overall verdict.
    """
    clarity_ok = f.clarity in CLARITY_PASS
    color_ok = f.color in COLOR_PASS
    cut_ok = f.cut in CUT_PASS
    reflects_ok = f.reflects == "purity"
    pure = clarity_ok and color_ok and cut_ok and reflects_ok
    return {
        "clarity": {"value": f.clarity, "score": CLARITY_SCORE.get(f.clarity, 0.0), "pass": clarity_ok},
        "color":   {"value": f.color,   "score": COLOR_SCORE.get(f.color, 0.0),   "pass": color_ok},
        "cut":     {"value": f.cut,     "score": CUT_SCORE.get(f.cut, 0.0),       "pass": cut_ok},
        "reflects": {"value": f.reflects, "pass": reflects_ok},
        "pure": pure,
        "verdict": "PASS" if pure else "GLASS",
        "failed": _failed_scales(f) if not pure else [],
    }


def _pure(f: Facet) -> bool:
    return grade(f)["pure"]


@dataclass
class DiamondPlayground:
    floor_clarity: str = "FL"
    floor_color: str = "D"
    floor_cut: str = "Excellent"
    facets: List[Facet] = field(default_factory=list)
    pressure_passes: int = 0

    def __post_init__(self) -> None:
        if not self.facets:
            self.facets = [
                Facet("foundation", "floor", self.floor_clarity, self.floor_color, self.floor_cut),
                Facet("DCLM", "ring"),
                Facet("Iris", "ring"),
                Facet("Twain²", "ring"),
                Facet("summer", "tree", clarity="VS", color="E", cut="Very Good"),
                Facet("winter", "tree", clarity="VS", color="F", cut="Very Good"),
                Facet("merit", "economy"),
                Facet("standing", "economy"),
                Facet("ceiling", "ceiling"),
            ]

    def floor_holds(self) -> bool:
        floor = next(f for f in self.facets if f.kind == "floor")
        return _pure(floor)

    def apply_pressure(self) -> Dict:
        self.pressure_passes += 1
        return {"pressure_passes": self.pressure_passes,
                "floor": "holds" if self.floor_holds() else "FAIL"}

    def mesh(self) -> List[Dict]:
        out = []
        for f in self.facets:
            if f.kind == "ceiling":
                continue
            g = grade(f)
            out.append({
                "name": f.name,
                "kind": f.kind,
                "clarity": g["clarity"],
                "color": g["color"],
                "cut": g["cut"],
                "reflects": g["reflects"],
                "verdict": g["verdict"],
                "failed": g["failed"],
            })
        return out

    def rise(self) -> Dict:
        if not self.floor_holds():
            return {"ok": False, "reason": "floor failed — cannot rise"}
        mesh = self.mesh()
        glass = [m for m in mesh if m["verdict"] == "GLASS"]
        if glass:
            return {"ok": False, "reason": "glass in mesh",
                    "glass": [{"name": g["name"], "failed": g["failed"]} for g in glass]}
        return {"ok": True, "mesh": mesh, "light": "one", "refractions": len(mesh)}

    def ceiling(self) -> Dict:
        r = self.rise()
        if not r.get("ok"):
            return {"reached": False, "reason": r.get("reason"), "detail": r.get("glass")}
        return {
            "reached": True,
            "clarity": "FL",
            "color": "D",
            "cut": "Excellent",
            "law": "LAW WINS",
            "origin": "immutable",
            "learning": "advisory only — NOT_FOR_EMISSION",
            "light": "one truth, many views, all true",
            "pressure_passes": self.pressure_passes,
        }


def _failed_scales(f: Facet) -> List[str]:
    failed = []
    if f.clarity not in CLARITY_PASS:
        failed.append(f"clarity:{f.clarity}")
    if f.color not in COLOR_PASS:
        failed.append(f"color:{f.color}")
    if f.cut not in CUT_PASS:
        failed.append(f"cut:{f.cut}")
    if f.reflects != "purity":
        failed.append("reflects:not-purity")
    return failed


def demo() -> Dict:
    p = DiamondPlayground()
    p.apply_pressure()
    p.apply_pressure()
    return {"floor_holds": p.floor_holds(), "rise": p.rise(), "ceiling": p.ceiling()}


def demo_with_impurity() -> Dict:
    """Show the gate refusing a tinted / poorly cut facet."""
    bad = Facet("tinted_claim", "economy", clarity="FL", color="J", cut="Fair", reflects="purity")
    p = DiamondPlayground(facets=[
        Facet("foundation", "floor"),
        Facet("DCLM", "ring"),
        bad,
        Facet("ceiling", "ceiling"),
    ])
    return {"floor_holds": p.floor_holds(), "rise": p.rise(), "ceiling": p.ceiling()}
