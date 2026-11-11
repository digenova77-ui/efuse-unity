"""PRAGMATISM — narrow until Flawless or stalemate.

DCLM is the logic constraint (x). Iris is the truth constraint (y).
There is no third constraint and no third seat.
A point may still carry z. That coordinate is never read.

The narrowing applies only constraints already in force. It stops only
when one candidate remains and that candidate satisfies every constraint,
or when no unused constraint can split the remainder.

One such candidate is Flawless: pure logic decision execution, free of
defect. It is not a victory. The other ending is stalemate.

Balance is not a constraint. List order is not a constraint.
A constraint that would remove every remaining candidate is not applied.
Two constraints that would leave different survivors are not resolved
by picking one of them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


FLAWLESS = "Flawless"
STALEMATE = "STALEMATE"


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0.0  # carried so older callers still construct; never consulted


@dataclass(frozen=True)
class Constraint:
    """One constraint already in force. One axis. One minimum. Nothing else."""

    name: str
    dimension: int          # 0 = x, 1 = y. No other dimension is a constraint.
    binding: float = 0.0    # minimum the candidate must meet on this axis


DCLM = Constraint("DCLM", 0, binding=0.0)
IRIS = Constraint("Iris", 1, binding=0.0)


def _axis(point: Point, dimension: int) -> float:
    if dimension == 0:
        return point.x
    if dimension == 1:
        return point.y
    raise ValueError(f"not a constraint dimension: {dimension}")


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


class Narrow:
    """Narrow by the constraints in force. The pure ending is Flawless."""

    def __init__(self, constraints: Optional[Sequence[Constraint]] = None):
        chosen = tuple(constraints) if constraints is not None else (DCLM, IRIS)
        self.constraints = tuple(
            constraint for constraint in chosen
            if constraint.dimension in (0, 1)
        )
        self.stalemates: List[DecisionWave] = []

    def _splitters(self, remaining: Sequence[Point], unused: Sequence[Constraint]):
        found = []
        for constraint in unused:
            passed = [
                candidate for candidate in remaining
                if _axis(candidate, constraint.dimension) >= constraint.binding
            ]
            if passed and len(passed) < len(remaining):
                found.append((constraint, passed))
        return found

    def collapse(self, wave: DecisionWave) -> Optional[Point]:
        remaining = list(wave.candidates)
        unused = list(self.constraints)
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
            for constraint, _passed in splitters:
                applied.append(constraint.name)
            unused = [
                constraint for constraint in unused
                if constraint.name not in applied
            ]
            remaining = list(splitters[0][1])

        satisfying = [
            candidate for candidate in remaining
            if all(
                _axis(candidate, constraint.dimension) >= constraint.binding
                for constraint in self.constraints
            )
        ]
        wave.applied = applied
        if len(satisfying) == 1:
            wave.decision = satisfying[0]
            wave.remaining = list(satisfying)
            wave.status = FLAWLESS
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
        """Flawless returns the one remaining point. Stalemate returns None.
        It does not raise, and it does not pick."""
        wave = DecisionWave(question, list(candidates))
        return self.collapse(wave)
