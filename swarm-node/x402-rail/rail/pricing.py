"""Energy-indexed pricing: the price of compute moves with measured Joules.

Standing design (David, Oct 12 2026 — "price index markers: energy"):
  * The real-time pricing rule is indexed to energy markers: the price of
    compute moves with the measured Joule cost per lane/substrate.
  * This is the spine's oldest job — measuring the true Joule cost of
    computation — now as the pricing index.
  * Markers per lane, updated with telemetry, denominated in verified Joules.
    The arbitrage (work flows to the cheapest verified Joule) and the pricing
    become the same motion: both read the same markers.

Two-state rule — "moves when X":
  * X = a fresh, honestly-graded Joule marker for the lane. Until X exists,
    every price is STATIC at its base Merit price. Nothing in today's
    telemetry justifies movement (no Joule readings, no time series), so the
    catalog boots STATIC and the index engages itself the moment real markers
    arrive. No extra gate, no human word needed — the fail-safe default is
    the base price.
  * Only REAL or REPORTED markers move money. INFERRED never moves a price.

Fail-closed, always:
  * Unknown lane, missing marker, stale marker, unparseable marker ->
    base price. Pricing never raises, never blocks a payment, never invents.

Bounds (parameters, not law — David tunes these at the parameter layer):
  * floor_mult = 0.5 — price never drops below half of base. Keeps the 1%
    residual meaningful and covers fixed infra cost no telemetry can see.
  * ceil_mult = 3.0 — price never exceeds 3x base. A faulty Joule meter must
    not be able to run the price away.
  * marker TTL = 900s — a marker older than 15 minutes is stale; the lane
    falls back to base until the Joule meter speaks again.

The 1% residual split and the receipt-as-collapse-trace law are untouched:
this module only decides the gross. What the index did is written onto the
receipt (quote detail), so every indexed price is auditable after the fact.

ROTATION PREMIUM (David, Oct 12 2026 — "key value goes up on things that
haven't been decided and need rotation"):
  * Undecided items — things sitting in the three-bucket rotation — carry a
    value premium. The harder a decision (more rotation rounds, longer it
    resists purity), the higher its key value. Exploration is work; hard
    problems cost more to decide; the price honestly reflects decision
    difficulty. The system earns most where the thinking is hardest.
  * Scope: the premium applies to DECISION work — a priced resource consumed
    as part of a deliberation (a rotation round, a re-verdict, the terminal
    write). It is keyed by decision_id, driven by actual rotation events
    from the deliberation pipeline, never by the payer. Plain compute
    resources never see it.
  * Formula (linear, capped): mult(r) = min(1 + ALPHA * r, ROTATION_CAP),
    r = completed rotation rounds. Linear because each round IS one more
    full judging pass — the same honest increment per round. NOT
    exponential (runs away) and NOT diminishing (would perversely discount
    the hardest problems at the margin).
  * Reset: PURITY sealed -> premium clears (entry removed, back to 1.0x).
    Sealed UNRESOLVED -> premium settles: frozen at its final multiplier,
    no further rounds accrue; the terminal trace carries the final price.
    A genuinely new dispute is a new decision_id and starts at r=0.
  * Interaction with the energy index: MULTIPLICATIVE.
    price = base x energy_mult x rotation_mult.
    They are independent cost dimensions — the energy index measures WHERE
    the work runs (Joules per lane), the rotation premium measures HOW HARD
    the work is (rounds of deliberation). Independent dimensions multiply,
    like rate x hours. Additive would need a shared unit and would let one
    dimension's movement mask the other's. Both terms are bounded, so the
    product is bounded: [0.5, 9.0]x base worst case.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .economy import Price, PriceCatalog

# Signing boundary (S4): oracle inputs crossing a trust boundary must be
# SIGNED events from allowlisted keys. The deliberation pipeline's key
# opens rotation rounds; the sealed meter's key submits Joule markers.
# The allowlist itself is signed by the offline root key.
import os as _os
import sys as _sys

def _load_signing():
    here = _os.path.dirname(_os.path.abspath(__file__))
    for cand in ("/opt/dualis/signing",
                 _os.path.join(here, "..", "..", "signing"),
                 _os.path.join(here, "..", "signing"),
                 _os.path.join(here, "signing")):
        if _os.path.exists(_os.path.join(cand, "__init__.py")):
            parent = _os.path.dirname(_os.path.abspath(cand))
            if parent not in _sys.path:
                _sys.path.insert(0, parent)
            try:
                import signing.allowlist as sallow
                import signing.envelope as senvelope
                return sallow, senvelope
            except Exception:
                continue
    return None


_SIGNING = _load_signing()

# Honest grades a marker may carry. Only REAL and REPORTED move money.
GRADES = ("REAL", "REPORTED", "INFERRED")
INDEXABLE_GRADES = ("REAL", "REPORTED")

# Bounds: parameters, not law.
FLOOR_MULT = 0.5
CEIL_MULT = 3.0
MARKER_TTL_S = 900.0

# Rotation premium: parameters, not law.
ROTATION_ALPHA = 0.25   # +25% per completed rotation round
ROTATION_CAP = 3.0      # premium never exceeds 3.0x (cap reached at r=8)


def _parse_ts(ts: str) -> float:
    """Parse an ISO-8601 timestamp to epoch seconds. Raises ValueError."""
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@dataclass(frozen=True)
class LaneEnergyMarker:
    """One lane's measured Joule cost, honestly graded.

    joules_per_unit: verified Joules per pricing unit (e.g. per 1k requests,
    per GB served — the unit is the priced resource's unit, documented in
    the catalog).
    """

    lane: str
    joules_per_unit: float
    measured_at: str  # ISO-8601
    source: str  # e.g. "joule-meter"
    grade: str = "REAL"

    def __post_init__(self):
        if not self.lane:
            raise ValueError("marker needs a lane")
        if not (self.joules_per_unit > 0):
            raise ValueError("joules_per_unit must be positive")
        _parse_ts(self.measured_at)  # fail fast on bad timestamps
        if self.grade not in GRADES:
            raise ValueError(f"grade must be one of {GRADES}")
        if not self.source:
            raise ValueError("marker needs a source")


class EnergyIndex:
    """The energy index: reference Joule cost + per-lane markers.

    index_for(lane) = clamp(lane_joules / reference_joules, floor, ceil).
    A lane at the reference cost prices at exactly 1.0x base — the index is
    a ratio, so it cannot drift with the absolute cost of energy, only with
    relative differences between lanes. That is the arbitrage, priced.
    """

    def __init__(
        self,
        reference_joules_per_unit: float,
        *,
        floor_mult: float = FLOOR_MULT,
        ceil_mult: float = CEIL_MULT,
        marker_ttl_s: float = MARKER_TTL_S,
    ) -> None:
        if not (reference_joules_per_unit > 0):
            raise ValueError("reference must be positive")
        if not (0 < floor_mult <= 1.0):
            raise ValueError("floor must be in (0, 1]")
        if not (ceil_mult >= 1.0):
            raise ValueError("ceiling must be >= 1")
        self.reference = reference_joules_per_unit
        self.floor_mult = floor_mult
        self.ceil_mult = ceil_mult
        self.marker_ttl_s = marker_ttl_s
        self._markers: dict[str, LaneEnergyMarker] = {}

    def update_marker(self, marker: LaneEnergyMarker) -> None:
        """Store a marker. Validation happened in the marker itself;
        a bad marker raises there and is never stored.

        NOTE (S4): this raw entry point is for the IN-PROCESS pipeline
        only. Anything crossing a trust boundary (a lane submitting a
        marker) must use update_marker_signed — the signed envelope from
        an allowlisted sealed-meter key. Unsigned remote submissions are
        dropped and the drop is attested.
        """
        self._markers[marker.lane] = marker

    def update_marker_signed(self, env: dict, allowlist_cfg: dict,
                             offline_pubkey: bytes) -> LaneEnergyMarker:
        """Accept a SIGNED energy-marker event (S4). Verifies: the
        allowlist's own signature (offline root), the event signature,
        and that the key is allowlisted for role 'sealed-meter'.
        Returns the stored marker. Raises EnvelopeError otherwise —
        the caller attests the drop."""
        if _SIGNING is None:
            raise RuntimeError("signing module unavailable — cannot accept "
                               "signed marker events")
        sallow, senvelope = _SIGNING
        payload = sallow.open_event(env, allowlist_cfg, offline_pubkey,
                                    "sealed-meter")
        if payload.get("type") != "energy-marker":
            raise senvelope.EnvelopeError("not an energy-marker event")
        marker = LaneEnergyMarker(
            lane=payload["lane"],
            joules_per_unit=float(payload["joules_per_unit"]),
            measured_at=payload["measured_at"],
            source=payload["source"],
            grade=payload.get("grade", "REPORTED"),
        )
        # S3 oracle rule, enforced at the boundary: a sealed meter's
        # signature authenticates the SOURCE, not the grade. Self-reports
        # arrive at most REPORTED; REAL requires calibrated-meter
        # provenance, declared in the payload and checked here.
        if marker.grade == "REAL" and not payload.get("calibrated"):
            marker = LaneEnergyMarker(
                lane=marker.lane, joules_per_unit=marker.joules_per_unit,
                measured_at=marker.measured_at, source=marker.source,
                grade="REPORTED")
        self._markers[marker.lane] = marker
        return marker

    def marker_for(self, lane: str) -> LaneEnergyMarker | None:
        return self._markers.get(lane)

    def _fresh(self, marker: LaneEnergyMarker, now: float) -> bool:
        age = now - _parse_ts(marker.measured_at)
        return 0 <= age <= self.marker_ttl_s

    def index_for(self, lane: str, now: float | None = None) -> float | None:
        """The price multiplier for a lane, or None if the price must not
        move (no marker, stale marker, ungradeable marker). None means the
        caller falls back to the base price — never invent a multiplier."""
        now = time.time() if now is None else now
        marker = self._markers.get(lane)
        if marker is None:
            return None
        if marker.grade not in INDEXABLE_GRADES:
            return None
        if not self._fresh(marker, now):
            return None
        raw = marker.joules_per_unit / self.reference
        return max(self.floor_mult, min(self.ceil_mult, raw))

    def mode_for(self, lane: str, now: float | None = None) -> str:
        return "INDEXED" if self.index_for(lane, now) is not None else "STATIC"


@dataclass
class RotationRound:
    """One rotation round of a decision, with its certification state.

    premium_quoted_micros: the premium slice of this round's quoted price.
    state: PENDING -> NOVEL | EMPTY | GAMED (set by the verdict pipeline).
    """

    n: int
    contributor: str
    premium_quoted_micros: int
    energy_mult: float = 1.0
    state: str = "PENDING"
    option_hash: str | None = None
    evidence_ids: tuple = ()


class RotationLedger:
    """Tracks rotation rounds per decision and the resulting premium,
    with the anti-gaming lifecycle.

    ANTI-GAMING (David, Oct 12 2026): the premium pays for NEW OPTIONS, not
    for time. Each rotation round earns its premium only if it produces
    novel options. A round that adds nothing new earns zero for that round.
    Deliberate stalling without genuine exploration pays nothing.

    Round lifecycle: PENDING -> NOVEL | EMPTY | GAMED.
      * NOVEL: cleared the novelty bar; its premium increment is EARNED
        into the solver pool.
      * EMPTY: honest round, nothing new; its premium advance is unearned
        and goes back to the payer as a rebate. No stigma.
      * GAMED: manufactured delay proven; its premium advance is rebated
        to the payer and the GAMED mark stays on the trace forever.
        The base fee is kept in all cases -- the work happened, energy was
        spent. Only the novelty pay is unearned.

    Where burned value goes: REBATE TO THE PAYER, via the rail's existing
    service-initiated forward (same shape as the residual leg), recorded on
    the round's trace as premium_rebate_micros with rebate_to=payer. In a
    receipt-first system the public GAMED mark IS the punishment, and
    reputation follows the traces.

    The decider never prices their own delay: the multiplier is computed by
    this rule from certified rounds; certification verdicts come from the
    Trinity pipeline, never from whoever holds the decision. Only the
    verdict pipeline calls certify_round; the holder calls open_round.

    The solver earns, the holder doesn't: earned_pool() splits the pool
    pro-rata by certified novel rounds per contributor.

    Novelty bar -- mechanical half enforced here, judgment half belongs to
    the Trinity's verdict on the round (which the caller represents):
      * option_hash must be new: never seen in any prior round of this
        decision (no duplicates).
      * evidence_ids must introduce at least one item never cited by any
        prior round of this decision (no rehashed evidence).
    """

    def __init__(
        self,
        *,
        alpha: float = ROTATION_ALPHA,
        cap: float = ROTATION_CAP,
    ) -> None:
        if not (alpha > 0):
            raise ValueError("alpha must be positive")
        if not (cap >= 1.0):
            raise ValueError("cap must be >= 1")
        self.alpha = alpha
        self.cap = cap
        self._rounds: dict[str, list] = {}
        self._terminal: dict[str, float] = {}  # decision_id -> frozen multiplier

    @staticmethod
    def _check_id(decision_id: str) -> None:
        if not decision_id:
            raise ValueError("decision_id is required")

    def _live(self, decision_id: str) -> list:
        self._check_id(decision_id)
        if decision_id in self._terminal:
            raise ValueError(
                "decision %s is sealed UNRESOLVED; no further rounds" % decision_id
            )
        return self._rounds.setdefault(decision_id, [])

    def open_round(
        self,
        decision_id: str,
        contributor: str,
        premium_quoted_micros: int,
        energy_mult: float = 1.0,
    ) -> int:
        """The holder opens a round: who tried, what premium was quoted.
        Returns the round number."""
        if not contributor:
            raise ValueError("contributor is required")
        if premium_quoted_micros < 0:
            raise ValueError("premium_quoted_micros cannot be negative")
        rounds = self._live(decision_id)
        n = len(rounds) + 1
        rounds.append(
            RotationRound(
                n=n,
                contributor=contributor,
                premium_quoted_micros=premium_quoted_micros,
                energy_mult=energy_mult,
            )
        )
        return n

    def open_round_signed(self, env: dict, allowlist_cfg: dict,
                          offline_pubkey: bytes) -> int:
        """Accept a SIGNED rotation-round event (S4). The event must come
        from a key allowlisted for role 'deliberation-pipeline'. Returns
        the round number. Raises EnvelopeError otherwise — the caller
        attests the drop (a flood of dropped forgeries is itself a signal).
        """
        if _SIGNING is None:
            raise RuntimeError("signing module unavailable — cannot accept "
                               "signed round events")
        sallow, senvelope = _SIGNING
        payload = sallow.open_event(env, allowlist_cfg, offline_pubkey,
                                    "deliberation-pipeline")
        if payload.get("type") != "rotation-round":
            raise senvelope.EnvelopeError("not a rotation-round event")
        return self.open_round(
            decision_id=payload["decision_id"],
            contributor=payload["contributor"],
            premium_quoted_micros=int(payload["premium_quoted_micros"]),
            energy_mult=float(payload.get("energy_mult", 1.0)),
        )

    def certify_round(
        self,
        decision_id: str,
        n: int,
        verdict: str,
        option_hash: str | None = None,
        evidence_ids: tuple = (),
    ) -> None:
        """The Trinity's verdict on the round: NOVEL | EMPTY | GAMED."""
        if verdict not in ("NOVEL", "EMPTY", "GAMED"):
            raise ValueError("verdict must be NOVEL, EMPTY, or GAMED")
        rounds = self._live(decision_id)
        if not (1 <= n <= len(rounds)):
            raise ValueError("round %d does not exist for %s" % (n, decision_id))
        rnd = rounds[n - 1]
        if rnd.state != "PENDING":
            raise ValueError("round %d already certified as %s" % (n, rnd.state))
        if verdict == "NOVEL":
            if not option_hash:
                raise ValueError("NOVEL requires an option_hash")
            prior_hashes = {r.option_hash for r in rounds[: n - 1] if r.option_hash}
            if option_hash in prior_hashes:
                raise ValueError("duplicate option_hash: not a new option")
            prior_evidence: set = set()
            for r in rounds[: n - 1]:
                prior_evidence.update(r.evidence_ids)
            if evidence_ids and not (set(evidence_ids) - prior_evidence):
                raise ValueError("rehashed evidence: no new evidence cited")
            rnd.option_hash = option_hash
            rnd.evidence_ids = tuple(evidence_ids)
        rnd.state = verdict

    def novel_rounds(self, decision_id: str) -> int:
        return sum(1 for r in self._rounds.get(decision_id, []) if r.state == "NOVEL")

    def gamed_rounds(self, decision_id: str) -> list:
        return [r.n for r in self._rounds.get(decision_id, []) if r.state == "GAMED"]

    def state_for(self, decision_id: str) -> str:
        if decision_id in self._terminal:
            return "TERMINAL"
        if decision_id in self._rounds:
            return "ACTIVE"
        return "CLEARED"

    def multiplier_for(self, decision_id: str | None) -> float:
        """1 + alpha * (certified NOVEL rounds), capped. Only novelty moves
        the multiplier -- stalling without exploration pays nothing."""
        if not decision_id:
            return 1.0
        if decision_id in self._terminal:
            return self._terminal[decision_id]
        return min(1.0 + self.alpha * self.novel_rounds(decision_id), self.cap)

    def earned_pool(self, decision_id: str) -> dict:
        """Premium micros earned, per contributor, pro-rata by certified
        novel rounds. The solver earns; the holder doesn't."""
        self._check_id(decision_id)
        novel = [r for r in self._rounds.get(decision_id, []) if r.state == "NOVEL"]
        if not novel:
            return {}
        total = sum(r.premium_quoted_micros for r in novel)
        by_contrib: dict = {}
        for r in novel:
            by_contrib[r.contributor] = by_contrib.get(r.contributor, 0) + 1
        total_rounds = len(novel)
        shares: dict = {}
        assigned = 0
        ordered = sorted(by_contrib.items(), key=lambda kv: (-kv[1], kv[0]))
        for contrib, cnt in ordered:
            share = total * cnt // total_rounds
            shares[contrib] = share
            assigned += share
        dust = total - assigned
        if dust > 0:
            shares[ordered[0][0]] += dust
        return shares

    def rebate_due_micros(self, decision_id: str) -> int:
        """Premium advances on EMPTY and GAMED rounds: unearned, owed back
        to the payer via the rail's service-initiated forward."""
        self._check_id(decision_id)
        return sum(
            r.premium_quoted_micros
            for r in self._rounds.get(decision_id, [])
            if r.state in ("EMPTY", "GAMED")
        )

    def seal(self, decision_id: str, outcome: str) -> None:
        """PURITY -> premium clears (entry removed, back to 1.0x).
        UNRESOLVED -> premium settles: multiplier frozen at its final value,
        no further rounds accrue. Earned pool and rebates stay queryable
        for the terminal trace."""
        self._check_id(decision_id)
        if outcome == "PURITY":
            self._rounds.pop(decision_id, None)
            self._terminal.pop(decision_id, None)
        elif outcome == "UNRESOLVED":
            self._terminal[decision_id] = self.multiplier_for(decision_id)
        else:
            raise ValueError("outcome must be PURITY or UNRESOLVED")


@dataclass
class DynamicPriceCatalog(PriceCatalog):
    """A PriceCatalog whose prices move with the energy index and the
    rotation premium.

    price = base x energy_mult x rotation_mult (multiplicative: the energy
    index measures WHERE the work runs, the rotation premium measures HOW
    HARD the work is -- independent dimensions multiply, like rate x hours).
    Combined bounds: [0.5, 9.0]x base worst case. Both terms fail closed to
    their neutral value, so a plain price_for(path) is always the base price.

    The rotation premium applies only when a decision_id is passed -- the
    deliberation pipeline passes it for decision work; plain compute never
    sees it.
    """

    energy_index: EnergyIndex | None = None
    rotation_ledger: RotationLedger | None = None

    def _multipliers(
        self,
        lane: str | None,
        decision_id: str | None,
        now: float | None,
    ) -> tuple:
        energy_mult = 1.0
        if lane is not None and self.energy_index is not None:
            energy_mult = self.energy_index.index_for(lane, now) or 1.0
        rotation_mult = 1.0
        if decision_id is not None and self.rotation_ledger is not None:
            rotation_mult = self.rotation_ledger.multiplier_for(decision_id)
        return energy_mult, rotation_mult

    def price_for(
        self,
        resource_path: str,
        lane: str | None = None,
        decision_id: str | None = None,
        now: float | None = None,
    ) -> Price | None:
        base = super().price_for(resource_path)
        if base is None:
            return None
        energy_mult, rotation_mult = self._multipliers(lane, decision_id, now)
        total = energy_mult * rotation_mult
        if total == 1.0:
            return base
        notes = []
        if energy_mult != 1.0:
            notes.append("energy-indexed x%.3f on lane %s" % (energy_mult, lane))
        if rotation_mult != 1.0:
            notes.append("rotation premium x%.3f on %s" % (rotation_mult, decision_id))
        note = " [%s]" % ", ".join(notes)
        return Price(
            merit=base.merit * total,
            description=(base.description + note if base.description else note.strip()),
        )

    def quote(
        self,
        resource_path: str,
        lane: str | None = None,
        decision_id: str | None = None,
        now: float | None = None,
    ) -> dict | None:
        """Everything the receipt needs to audit this price after the fact."""
        base = super().price_for(resource_path)
        if base is None:
            return None
        energy_mult, rotation_mult = self._multipliers(lane, decision_id, now)
        detail: dict = {
            "resource": resource_path,
            "base_merit": base.merit,
            "lane": lane,
            "decision_id": decision_id,
            "mode": "STATIC",
            "energy_multiplier": energy_mult,
            "rotation_multiplier": rotation_mult,
            "multiplier": energy_mult * rotation_mult,
            "marker": None,
            "rotation": None,
        }
        if energy_mult != 1.0:
            marker = (
                self.energy_index.marker_for(lane)
                if self.energy_index is not None
                else None
            )
            detail.update(
                {
                    "mode": "INDEXED",
                    "marker": (
                        {
                            "lane": marker.lane,
                            "joules_per_unit": marker.joules_per_unit,
                            "measured_at": marker.measured_at,
                            "source": marker.source,
                            "grade": marker.grade,
                        }
                        if marker is not None
                        else None
                    ),
                }
            )
        if rotation_mult != 1.0 and self.rotation_ledger is not None:
            detail["rotation"] = {
                "decision_id": decision_id,
                "novel_rounds": self.rotation_ledger.novel_rounds(decision_id or ""),
                "multiplier": rotation_mult,
                "state": self.rotation_ledger.state_for(decision_id or ""),
            }
            if detail["mode"] == "STATIC":
                detail["mode"] = "ROTATION"
            elif detail["mode"] == "INDEXED":
                detail["mode"] = "INDEXED+ROTATION"
        price = self.price_for(resource_path, lane, decision_id, now)
        assert price is not None
        detail["merit"] = price.merit
        detail["micros"] = price.micros
        return detail
