"""DIAMOND ARCHITECTURE — MAXIMUM FRONTIER FACING PROTOCOL

Cutting-edge elevation of the playground.

Frontier rule:
  A facet may face the ceiling only if it is in the maximum pure band
  on every scale:
    clarity = FL
    color   = D
    cut     = Excellent
    reflects = purity

Anything short of the maximum band is held at the mesh.
The ceiling is claimed only when every facing facet is maximum-pure.
LAW WINS. Origin immutable. Learning advisory only.
"""
from __future__ import annotations

from typing import Dict, List

from diamond_playground import DiamondPlayground, Facet, grade

PROTOCOL = "DIAMOND.FRONTIER.MAX.v1"
MAX_BAND = {"clarity": "FL", "color": "D", "cut": "Excellent"}


def faces_frontier(f: Facet) -> bool:
    """True only at the absolute pure maximum on every scale."""
    return (
        f.clarity == MAX_BAND["clarity"]
        and f.color == MAX_BAND["color"]
        and f.cut == MAX_BAND["cut"]
        and f.reflects == "purity"
    )


def frontier_report(p: DiamondPlayground | None = None) -> Dict:
    """Classify every facet: FACING or HELD."""
    if p is None:
        p = DiamondPlayground()
    facing: List[str] = []
    held: List[Dict] = []
    for f in p.facets:
        if f.kind == "ceiling":
            continue
        if faces_frontier(f):
            facing.append(f.name)
        else:
            g = grade(f)
            held.append({
                "name": f.name,
                "clarity": f.clarity,
                "color": f.color,
                "cut": f.cut,
                "reason": "below maximum pure band",
                "grade_verdict": g["verdict"],
            })
    ceiling_ok = len(held) == 0 and p.floor_holds()
    return {
        "protocol": PROTOCOL,
        "facing": facing,
        "held": held,
        "ceiling_claimable": ceiling_ok,
        "law": "LAW WINS",
        "origin": "immutable",
        "learning": "advisory only — NOT_FOR_EMISSION",
        "standard": "maximum pure band on every scale",
    }


def demo_frontier() -> Dict:
    clean = frontier_report()
    # A VS / E / Very Good facet is pure under the old gate
    # but held under the maximum frontier.
    soft = Facet("soft_facet", "tree", clarity="VS", color="E", cut="Very Good")
    p = DiamondPlayground(facets=[
        Facet("foundation", "floor"),
        Facet("DCLM", "ring"),
        soft,
        Facet("ceiling", "ceiling"),
    ])
    return {"clean": clean, "with_soft": frontier_report(p)}
