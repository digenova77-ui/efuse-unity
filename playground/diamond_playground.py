"""DIAMOND PLAYGROUND — floor → mesh → ceiling.

Traces the derivative diamond foundational floor up through the facet
mesh to the diamond ceiling. Pure, fail-closed, one light.

Floor properties (from DIAMOND_ARCHITECTURE_FLOOR.md):
  1. Hardest structure
  2. Formed under pressure
  3. Clarity graded
  4. Multi-faceted
  5. Refracts (one truth, many views)

Mesh: rings as circular facets, tree as branching, economy as circulatory.
Ceiling: the same light exiting through the highest facet — clarity FL,
LAW WINS, origin immutable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Clarity grades — binary gate preserved
CLARITY = {
    "FL": 1.0,   # Flawless — PASS
    "VVS": 0.95,
    "VS": 0.85,
    "SI": 0.6,   # FAIL — fixable
    "I": 0.3,    # FAIL — discard
}
PASS_GRADES = {"FL", "VVS", "VS"}


@dataclass(frozen=True)
class Facet:
    name: str
    kind: str          # "ring" | "tree" | "economy" | "ceiling"
    clarity: str
    reflects: str = "purity"   # must be purity; anything else is glass


@dataclass
class DiamondPlayground:
    """One stone. Floor, mesh, ceiling. One light."""
    floor_clarity: str = "FL"
    facets: List[Facet] = field(default_factory=list)
    pressure_passes: int = 0

    def __post_init__(self) -> None:
        if not self.facets:
            self.facets = [
                # Floor
                Facet("foundation", "floor", self.floor_clarity),
                # Mesh — rings (circular)
                Facet("DCLM", "ring", "FL"),
                Facet("Iris", "ring", "FL"),
                Facet("Twain²", "ring", "FL"),
                # Mesh — tree (branching)
                Facet("summer", "tree", "VS"),
                Facet("winter", "tree", "VS"),
                # Mesh — economy (circulatory)
                Facet("merit", "economy", "FL"),
                Facet("standing", "economy", "FL"),
                # Ceiling
                Facet("ceiling", "ceiling", "FL"),
            ]

    # -- Floor ----------------------------------------------------------
    def floor_holds(self) -> bool:
        """Hardest structure. Floor cannot fail."""
        return self.floor_clarity in PASS_GRADES

    def apply_pressure(self) -> Dict:
        """Formed under pressure. Each pass is heat."""
        self.pressure_passes += 1
        return {
            "pressure_passes": self.pressure_passes,
            "floor": "holds" if self.floor_holds() else "FAIL",
            "note": "pressure created the floor; it does not threaten it",
        }

    # -- Mesh -----------------------------------------------------------
    def mesh(self) -> List[Dict]:
        """Facets as the mesh. Glass (non-purity) is discarded."""
        out = []
        for f in self.facets:
            if f.kind == "ceiling":
                continue
            pure = f.reflects == "purity" and f.clarity in PASS_GRADES
            out.append({
                "name": f.name,
                "kind": f.kind,
                "clarity": f.clarity,
                "score": CLARITY.get(f.clarity, 0.0),
                "verdict": "PASS" if pure else "GLASS",
            })
        return out

    def rise(self) -> Dict:
        """Come up through the mesh. One light, many refractions."""
        if not self.floor_holds():
            return {"ok": False, "reason": "floor failed — cannot rise"}
        mesh = self.mesh()
        glass = [m for m in mesh if m["verdict"] == "GLASS"]
        if glass:
            return {
                "ok": False,
                "reason": "glass in mesh",
                "glass": [g["name"] for g in glass],
            }
        return {
            "ok": True,
            "mesh": mesh,
            "light": "one",
            "refractions": len(mesh),
        }

    # -- Ceiling --------------------------------------------------------
    def ceiling(self) -> Dict:
        """Diamond ceiling. Same light, highest facet. LAW WINS."""
        r = self.rise()
        if not r.get("ok"):
            return {"reached": False, "reason": r.get("reason")}
        return {
            "reached": True,
            "clarity": "FL",
            "law": "LAW WINS",
            "origin": "immutable",
            "learning": "advisory only — NOT_FOR_EMISSION",
            "light": "one truth, many views, all true",
            "pressure_passes": self.pressure_passes,
        }


def demo() -> Dict:
    """Fill the playground and traverse floor → mesh → ceiling."""
    p = DiamondPlayground()
    p.apply_pressure()
    p.apply_pressure()
    return {
        "floor_holds": p.floor_holds(),
        "rise": p.rise(),
        "ceiling": p.ceiling(),
    }
