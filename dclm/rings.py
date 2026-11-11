"""PRAGMATISM — narrow until victory or stalemate.

DCLM binds logic (x). Iris binds truth (y). There is no third ring.
A point may still carry z. That coordinate is never read.

Pragmatism applies only constraints already in force. It stops only when
one candidate remains and that candidate satisfies every constraint
(victory), or when no unused constraint can split the remainder
(stalemate). Balance is not a constraint. List order is not a constraint.
A constraint that would remove every remaining candidate is not applied.
Two constraints that would leave different survivors are not resolved by
picking one of them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


VICTORY = "VICTORY"
STALEMATE = "STALEMATE"


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0.0  # carried so older callers still construct; never consulted


@dataclass(frozen=True)
class Ring:
    name: str
    dimension: int          # 0 = x, 1 = y. No other dimension is a ring.
    binding: float = 0.0    # minimum the candidate must meet on this axis


RING_DCLM = Ring("DCLM", 0, binding=0.0)
RING_IRIS = Ring("Iris", 1, binding=0.0)


def _axis(point: Point, dimension: int) -> float:
    if dimension == 0:
        return point.x
    if dimension == 1:
        return point.y
    raise ValueError(f"not a ring dimension: {dimension}")


@dataclass
class DecisionWave:
    question: str
    candidates: List[Point] = field(default_factory=list)
    _collapsed: bool = False
    decision: Optional[Point] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    remaining: List[Point] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)

    def is_collapsed(self) -> bool:
        return self._collapsed


class Parliament:
    """Narrow by the constraints in force. Never a third vote."""

    def __init__(self, rings: Optional[Sequence[Ring]] = None):
        chosen = tuple(rings) if rings is not None else (RING_DCLM, RING_IRIS)
        self.rings = tuple(
            ring for ring in chosen
            if ring.dimension in (0, 1)
        )
        self.stalemates: List[DecisionWave] = []

    def _splitters(self, remaining: Sequence[Point], unused: Sequence[Ring]):
        found = []
        for ring in unused:
            passed = [
                candidate for candidate in remaining
                if _axis(candidate, ring.dimension) >= ring.binding
            ]
            if passed and len(passed) < len(remaining):
                found.append((ring, passed))
        return found

    def collapse(self, wave: DecisionWave) -> Optional[Point]:
        remaining = list(wave.candidates)
        unused = list(self.rings)
        applied: List[str] = []

        while True:
            splitters = self._splitters(remaining, unused)
            if not splitters:
                break
            signatures = {
                tuple(id(candidate) for candidate in passed)
                for _, passed in splitters
            }
            if len(signatures) != 1:
                self._stalemate(
                    wave, remaining, applied, "CONSTRAINTS_DISAGREE",
                )
                return None
            for ring, _passed in splitters:
                applied.append(ring.name)
            unused = [ring for ring in unused if ring.name not in applied]
            remaining = list(splitters[0][1])

        satisfying = [
            candidate for candidate in remaining
            if all(
                _axis(candidate, ring.dimension) >= ring.binding
                for ring in self.rings
            )
        ]
        wave.applied = applied
        if len(satisfying) == 1:
            wave.decision = satisfying[0]
            wave.remaining = list(satisfying)
            wave.status = VICTORY
            wave.reason = "ONE_REMAINS"
            wave._collapsed = True
            return satisfying[0]

        if not wave.candidates:
            reason = "NO_CANDIDATES"
        elif not satisfying:
            reason = "NONE_SATISFIES"
        else:
            reason = "NO_CONSTRAINT_SPLITS"
        self._stalemate(wave, satisfying, applied, reason)
        return None

    def _stalemate(self, wave, remaining, applied, reason) -> None:
        wave.decision = None
        wave.remaining = list(remaining)
        wave.applied = list(applied)
        wave.status = STALEMATE
        wave.reason = reason
        wave._collapsed = False
        self.stalemates.append(wave)

    def decide(self, question: str, candidates: List[Point]) -> Optional[Point]:
        """Victory returns the one remaining point. Stalemate returns None.
        It does not raise, and it does not pick."""
        wave = DecisionWave(question, list(candidates))
        return self.collapse(wave)
