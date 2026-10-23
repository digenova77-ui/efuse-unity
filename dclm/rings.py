"""RINGS — pure three-ring collapse contract.

Transform: local pure implementation of the DecisionWave / Parliament / Point
interface expected by dclm/compute.py and dclm/test_compute.py.
Not a copy of an external file; a self-contained contract that satisfies the
observed tests and the fail-closed rule (no survivors → undecided, never forced).

Balance prefers candidates that are equal and non-zero across the three
dimensions. A perfectly equal point scores 1.0. Weak points can still score
high on balance but are rejected by ring binding thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


@dataclass
class Ring:
    name: str
    dimension: int          # 0=x, 1=y, 2=z
    binding: float = 0.0    # minimum strength required on this dimension


RING_DCLM  = Ring("DCLM",  0, binding=0.0)
RING_IRIS  = Ring("Iris",  1, binding=0.0)
RING_TWAIN = Ring("Twain²", 2, binding=0.0)


@dataclass
class DecisionWave:
    question: str
    candidates: List[Point] = field(default_factory=list)
    _collapsed: bool = False
    decision: Optional[Point] = None

    def is_collapsed(self) -> bool:
        return self._collapsed


class Parliament:
    """Three-ring collapse. Highest balance among survivors wins.
    No survivors → wave goes to undecided, never forced."""

    def __init__(self, rings: Optional[Sequence[Ring]] = None):
        self.rings = tuple(rings) if rings is not None else (
            RING_DCLM, RING_IRIS, RING_TWAIN)
        self.undecided: List[DecisionWave] = []

    @staticmethod
    def balance(p: Point) -> float:
        """1.0 when all three dimensions are equal and positive.
        Otherwise a [0,1] measure of equality × strength.
        """
        vals = (p.x, p.y, p.z)
        mn, mx = min(vals), max(vals)
        if mn <= 0:
            return 0.0
        if abs(mx - mn) < 1e-12:
            return 1.0
        mean = sum(vals) / 3.0
        spread = mx - mn
        equality = max(0.0, 1.0 - spread / mean) if mean > 0 else 0.0
        return equality * mn

    def _survives(self, p: Point) -> bool:
        for r in self.rings:
            dim = (p.x, p.y, p.z)[r.dimension]
            if dim < r.binding:
                return False
        return True

    def collapse(self, wave: DecisionWave) -> Optional[Point]:
        survivors = [c for c in wave.candidates if self._survives(c)]
        if not survivors:
            wave._collapsed = False
            self.undecided.append(wave)
            return None
        best = max(survivors, key=lambda c: (self.balance(c), -survivors.index(c)))
        wave.decision = best
        wave._collapsed = True
        return best

    def decide(self, question: str, candidates: List[Point]) -> Point:
        wave = DecisionWave(question, list(candidates))
        decision = self.collapse(wave)
        if decision is None:
            raise RuntimeError("no survivors — undecided, never forced")
        return decision
