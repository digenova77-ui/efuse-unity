"""IRIS MAX INTAKE — neural unification.

One unified cognitive-economic organism: the brain's neural pathways, the
synapses where they integrate, the body that hosts them, and the economic
tree running INSIDE the brain as neural flow.

Mapping (tree biology -> neural biology), each with an executable counterpart:
  +1 firing        -> synaptic firing           (fire_plus_one)
  merit            -> strengthened pathway      (strengthen, Hebbian)
  winter return    -> memory consolidation      (consolidate -> starch store)
  summer flow      -> active thought            (circulate: pathway->synapse->pathway)
  tapping          -> regulated output          (tap: surplus only, capped, receipted)

Interface contract for the sibling worker (iris-intake/):
  - iris_laws.py   -> formal law judgments.  Binds to a Pathway as its judge_fn,
                    or feeds Judgment objects into a Synapse.
  - iris_patterns.py -> probabilistic pattern scores. Same binding.
  - iris_arbiter.py  -> hybrid integration. The Synapse objects here ARE the
                    arbiter's integration points (synapse kind "trinity",
                    ids SYNAPSE_TRINITY / SYNAPSE_PROB_DET). The sibling should
                    call Synapse.fire() for its integration points, or register
                    its own Synapse with kind="arbiter".

Standards: testnet only. Unity-bound. Receipted. Provenance-labeled.
UNKNOWN is never PASS. Refusals raise RefusedError — never warn-and-continue.

Law sources: CANON.md v1.5.0 (I the Three, II unity binding, III DCLM writes,
IV sap model + tapping law, V tokenomics, VI derivative merit, XII standing
laws, XVII diamond geometry, XVIII max purity); PLUS_ONE_INCENTIVE.md (the
+1 deterioration function, implemented verbatim).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

SCHEMA = "iris.neural.v1.testnet"

# +1 deterioration — implemented verbatim from PLUS_ONE_INCENTIVE.md §1.2/§1.6.
PLUS_ONE_TAU = 12        # temporal e-folding, epochs
PLUS_ONE_RHO = 2         # structural e-folding, rings
PLUS_ONE_FLOOR = 0.25    # F_floor — dense-network maintenance rate [SET there]
PLUS_ONE_F_AFF = 0.50    # F_aff — Affinity floor lift [SET there]

# Hebbian plasticity
HEBBIAN_GAIN = 1.0       # weight gain per unit verified merit
DECAY_RATE = 0.01        # per decay_all() pass — the tree equalizes
MIN_WEIGHT = 0.05        # weights decay toward a floor, never to zero (cf. +1 floor)

# Tapping — canon IV. The seasonal cap is [HELD] in the canon; this stand-in
# is PROPOSED and must never be presented as David's number.
TAP_CAP_PROPOSED = 100.0  # [PROPOSED] per-member seasonal tap cap, test-keys

# Pathway types — the three cognitive circuits of the brain.
DETERMINISTIC = "deterministic"   # law circuits  <- iris_laws.py
PROBABILISTIC = "probabilistic"   # pattern circuits <- iris_patterns.py
PRAGMATIC = "pragmatic"           # outcome circuits (Twain^2-style)

PATHWAY_TYPES = (DETERMINISTIC, PROBABILISTIC, PRAGMATIC)

# Synapse kinds — the named integration points (the arbiter's synapses).
SYNAPSE_PROB_DET = "synapse.prob_det"   # probabilistic <-> deterministic
SYNAPSE_TRINITY = "synapse.trinity"     # DCLM <-> Iris <-> Twain^2

# Host kinds.
HOST_DEVICE = "device"
HOST_TESTNET_SERVER = "testnet-server"
HOST_INFRA = "infrastructure"

# Default body hosts.
HOST_S24_ORACLE = "host:s24-ultra-oracle"
HOST_RELAY_TESTNET = "host:relay-dualis-testnet"
HOST_INFRA_CORE = "host:infra-core"

# Provenance labels — canon XII.
PROVENANCE = ("REAL", "REPORTED", "MODELED", "DERIVED", "UNKNOWN")

# Verdicts.
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------

class RefusedError(Exception):
    """Structural refusal: garbage in -> refuse, never warn-and-continue."""
    pass


# ----------------------------------------------------------------------------
# Identity
# ----------------------------------------------------------------------------

def make_unity_id(seed: str) -> str:
    """Testnet Unity ID: 'unity:testnet:' + sha256 hex. Canon II."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return "unity:testnet:" + digest


def check_unity_id(uid: str) -> str:
    """Refuse any flow carrying a non-testnet identity. Canon II."""
    if not isinstance(uid, str) or not uid.startswith("unity:testnet:"):
        raise RefusedError(f"non-testnet identity refused: {uid!r}")
    return uid


# ----------------------------------------------------------------------------
# Receipts
# ----------------------------------------------------------------------------

def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_receipt(kind: str,
                  unity_id: str,
                  host_id: str,
                  provenance: str,
                  payload: Dict[str, Any],
                  t_epoch: Optional[int] = None) -> Dict[str, Any]:
    """Every event: Unity-bound, receipted, provenance-labeled, host-recorded.

    provenance must be one of REAL/REPORTED/MODELED/DERIVED/UNKNOWN (canon XII).
    """
    check_unity_id(unity_id)
    if provenance not in PROVENANCE:
        raise RefusedError(f"bad provenance label: {provenance!r}")
    body = {
        "schema": SCHEMA,
        "kind": kind,
        "unity_id": unity_id,
        "host_id": host_id,
        "provenance": provenance,
        "t_epoch": t_epoch if t_epoch is not None else int(time.time()),
        "payload": payload,
    }
    body["receipt_id"] = "rcpt:" + hashlib.sha256(
        _canonical(body).encode("utf-8")).hexdigest()
    return body


# ----------------------------------------------------------------------------
# Judgments — what a pathway emits before a synapse integrates it.
# ----------------------------------------------------------------------------

@dataclass
class Judgment:
    pathway_id: str
    pathway_type: str          # one of PATHWAY_TYPES
    verdict: str               # PASS / FAIL / UNKNOWN
    confidence: float          # 0.0..1.0
    detail: str
    unity_id: str
    host_id: str
    provenance: str
    receipt_id: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------------
# Pathway — a neural pathway. Three types: deterministic (law), probabilistic
# (pattern), pragmatic (Twain^2-style outcome).
# ----------------------------------------------------------------------------

class Pathway:
    """A neural pathway. Carries signals, produces judgments, strengthens
    only on verified work (Hebbian), decays otherwise (the tree equalizes)."""

    def __init__(self,
                 pathway_id: str,
                 pathway_type: str,
                 unity_id: str,
                 host_id: str,
                 judge_fn: Optional[Callable[[Any], Judgment]] = None):
        if pathway_type not in PATHWAY_TYPES:
            raise RefusedError(f"unknown pathway type: {pathway_type!r}")
        check_unity_id(unity_id)
        self.id = pathway_id
        self.ptype = pathway_type
        self.unity_id = unity_id
        self.host_id = host_id
        self.judge_fn = judge_fn          # bound by iris_laws.py / iris_patterns.py
        self.weight: float = 1.0
        self.merit: float = 0.0           # score, non-transferable (canon V)
        self.strength_log: List[Dict[str, Any]] = []

    # -- signal -----------------------------------------------------------
    def judge(self, signal: Any) -> Judgment:
        """Produce a judgment on a signal. Without a bound circuit the
        pathway honestly returns UNKNOWN — never a fabricated verdict."""
        if self.judge_fn is None:
            return Judgment(
                pathway_id=self.id, pathway_type=self.ptype,
                verdict=UNKNOWN, confidence=0.0,
                detail="no circuit bound (iris_laws/iris_patterns not landed)",
                unity_id=self.unity_id, host_id=self.host_id,
                provenance=UNKNOWN, receipt_id="rcpt:unbound")
        return self.judge_fn(signal)

    # -- Hebbian plasticity ------------------------------------------------
    def strengthen(self, merit_delta: float, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Pathway weight increases ONLY on verified receipt. No verified
        work, no strengthening. merit_delta must be >= 0 (accrual-only)."""
        if merit_delta < 0:
            raise RefusedError("merit is accrual-only; negative delta refused")
        if not isinstance(receipt, dict) or receipt.get("verified") is not True:
            raise RefusedError("strengthen requires a verified receipt")
        if receipt.get("unity_id") != self.unity_id:
            raise RefusedError("receipt identity does not match pathway identity")
        self.weight += merit_delta * HEBBIAN_GAIN
        self.merit += merit_delta
        event = build_receipt(
            kind="PATHWAY_STRENGTHEN", unity_id=self.unity_id,
            host_id=self.host_id, provenance="DERIVED",
            payload={"pathway_id": self.id, "merit_delta": merit_delta,
                     "new_weight": self.weight, "new_merit": self.merit,
                     "work_receipt": receipt.get("receipt_id")})
        self.strength_log.append(event)
        return event

    def decay(self, rate: float = DECAY_RATE) -> float:
        """The tree equalizes: unused pathways weaken toward the floor."""
        if not (0.0 <= rate <= 1.0):
            raise RefusedError(f"bad decay rate: {rate!r}")
        self.weight = max(MIN_WEIGHT, self.weight * (1.0 - rate))
        return self.weight


# ----------------------------------------------------------------------------
# Synapse — the hybrid integration point where pathways meet.
# ----------------------------------------------------------------------------

class Synapse:
    """A synapse takes pre-synaptic pathway outputs, applies the conflict
    rule, and fires a unified judgment. The arbiter's integration points
    ARE synapses — this is the executable form of iris_arbiter.py's job."""

    def __init__(self,
                 synapse_id: str,
                 input_pathway_ids: List[str],
                 unity_id: str,
                 host_id: str,
                 kind: str = SYNAPSE_PROB_DET):
        check_unity_id(unity_id)
        self.id = synapse_id
        self.kind = kind
        self.input_pathway_ids = list(input_pathway_ids)
        self.unity_id = unity_id
        self.host_id = host_id
        self.fire_log: List[Dict[str, Any]] = []

    # -- the conflict rule: LAW WINS, structurally ------------------------
    def integrate(self, judgments: List[Judgment]) -> Judgment:
        """LAW WINS: any non-UNKNOWN deterministic judgment overrides the
        probabilistic/pragmatic pathways. UNKNOWN never PASS."""
        laws = [j for j in judgments if j.pathway_type == DETERMINISTIC
                and j.verdict != UNKNOWN]
        if laws:
            verdicts = {j.verdict for j in laws}
            if len(verdicts) > 1:
                # Law circuits disagree -> fail closed, never guess.
                verdict, detail = UNKNOWN, "law_conflict: deterministic circuits disagree"
            else:
                verdict = laws[0].verdict
                detail = f"law_wins: {laws[0].pathway_id} -> {verdict}"
            law_won = True
        else:
            law_won = False
            others = [j for j in judgments if j.pathway_type != DETERMINISTIC]
            verdicts = {j.verdict for j in others}
            if FAIL in verdicts:
                verdict, detail = FAIL, "pragmatic_veto: a pathway failed"
            elif UNKNOWN in verdicts or not others:
                verdict, detail = UNKNOWN, "unresolved: no law, no clean signal"
            else:
                verdict, detail = PASS, "convergent: probabilistic+pragmatic agree"
        confidence = (sum(j.confidence for j in judgments) / len(judgments)
                      if judgments else 0.0)
        pre_receipts = [j.receipt_id for j in judgments]
        receipt = build_receipt(
            kind="SYNAPSE_FIRE", unity_id=self.unity_id, host_id=self.host_id,
            provenance="DERIVED",
            payload={"synapse_id": self.id, "synapse_kind": self.kind,
                     "law_won": law_won, "verdict": verdict, "detail": detail,
                     "pre_synaptic": [j.as_dict() for j in judgments],
                     "pre_receipts": pre_receipts})
        return Judgment(
            pathway_id=self.id, pathway_type="synapse", verdict=verdict,
            confidence=confidence, detail=detail, unity_id=self.unity_id,
            host_id=self.host_id, provenance="DERIVED",
            receipt_id=receipt["receipt_id"])

    def fire(self, judgments: List[Judgment]) -> Dict[str, Any]:
        """Fire the synapse: integrate and log the event. Returns the event
        envelope (unified judgment + its receipt)."""
        for j in judgments:
            check_unity_id(j.unity_id)
        unified = self.integrate(judgments)
        event = {"synapse_id": self.id, "kind": self.kind,
                 "unified_judgment": unified.as_dict(),
                 "receipt_id": unified.receipt_id}
        self.fire_log.append(event)
        return event


# ----------------------------------------------------------------------------
# Body — the host registry. The brain doesn't float: every cognitive event
# is hosted somewhere.
# ----------------------------------------------------------------------------

@dataclass
class Host:
    host_id: str
    kind: str            # device / testnet-server / infrastructure
    description: str
    unity_id: str        # canon XVIII: identity at every level — devices too


class Body:
    """The physical substrate registry: devices, testnet servers, infra."""

    def __init__(self, unity_id: str):
        check_unity_id(unity_id)
        self.unity_id = unity_id
        self._hosts: Dict[str, Host] = {}

    def register_host(self, host_id: str, kind: str,
                      description: str, unity_id: str) -> Host:
        if kind not in (HOST_DEVICE, HOST_TESTNET_SERVER, HOST_INFRA):
            raise RefusedError(f"unknown host kind: {kind!r}")
        check_unity_id(unity_id)
        host = Host(host_id=host_id, kind=kind,
                    description=description, unity_id=unity_id)
        self._hosts[host_id] = host
        return host

    def get(self, host_id: str) -> Host:
        try:
            return self._hosts[host_id]
        except KeyError:
            raise RefusedError(f"unregistered host: {host_id!r} — the brain doesn't float")

    def hosts(self) -> List[Host]:
        return list(self._hosts.values())


# ----------------------------------------------------------------------------
# The +1 deterioration function — verbatim from PLUS_ONE_INCENTIVE.md §1.2.
# ----------------------------------------------------------------------------

def plus_one_factor(t_event: int,
                    t_launch: int,
                    ring_depth: Optional[int],
                    affinity: bool = False) -> Dict[str, Any]:
    """F(d) = F_floor + (1 - F_floor) * e^(-d),
    d = (t_event - t_launch)/tau + r/rho.  ring_depth=None -> TIME_ONLY mode
    (d = dt/tau, no ring claim — UNKNOWN r is never presented as a number).
    affinity=True -> max(F(d), F_aff). Reward R is per verified check."""
    if t_event < t_launch:
        raise RefusedError("t_event precedes t_launch")
    dt = (t_event - t_launch) / PLUS_ONE_TAU
    if ring_depth is None:
        d = dt
        mode = "TIME_ONLY"
    else:
        if ring_depth < 0:
            raise RefusedError("negative ring depth")
        d = dt + ring_depth / PLUS_ONE_RHO
        mode = "FULL"
    f = PLUS_ONE_FLOOR + (1.0 - PLUS_ONE_FLOOR) * math.exp(-d)
    r = max(f, PLUS_ONE_F_AFF) if affinity else f
    return {"d": d, "F": f, "R": r, "mode": mode,
            "floor": PLUS_ONE_FLOOR, "affinity_floor": PLUS_ONE_F_AFF}


# ----------------------------------------------------------------------------
# Tree — the brain as one cognitive-economic organism. Economic circulation
# IS neural flow: summer = active thought, winter = memory consolidation.
# ----------------------------------------------------------------------------

class Tree:
    """The unified organism. Owns pathways, synapses, body, the starch store
    (long-term memory), and the active circulation traces (working thought)."""

    def __init__(self, unity_id: str, t_launch: int = 0):
        check_unity_id(unity_id)
        self.unity_id = unity_id
        self.t_launch = t_launch
        self.body = Body(unity_id)
        # Default substrate: the brain is hosted, never floating.
        self.body.register_host(HOST_S24_ORACLE, HOST_DEVICE,
                                "S24 Ultra — the iOS/Android oracle device",
                                make_unity_id("device:s24-ultra-oracle"))
        self.body.register_host(HOST_RELAY_TESTNET, HOST_TESTNET_SERVER,
                                "dualis.relay.v1.testnet relay/commit host",
                                make_unity_id("server:relay-testnet"))
        self.body.register_host(HOST_INFRA_CORE, HOST_INFRA,
                                "core infrastructure substrate",
                                make_unity_id("infra:core"))
        self.pathways: Dict[str, Pathway] = {}
        self.synapses: Dict[str, Synapse] = {}
        self.active_traces: List[Dict[str, Any]] = []   # working thought
        self.starch_store: List[Dict[str, Any]] = []    # consolidated memory
        self.winter_gradient: float = 0.0               # 0.0 full summer .. 1.0 full winter
        self.tap_ledger: List[Dict[str, Any]] = []
        self.seasonal_tapped: Dict[str, float] = {}     # unity_id -> tapped this season

    # -- structure ---------------------------------------------------------
    def add_pathway(self, pathway_id: str, pathway_type: str,
                    unity_id: str, host_id: str,
                    judge_fn: Optional[Callable[[Any], Judgment]] = None) -> Pathway:
        self.body.get(host_id)  # refuse unhosted pathways
        p = Pathway(pathway_id, pathway_type, unity_id, host_id, judge_fn)
        self.pathways[pathway_id] = p
        return p

    def add_synapse(self, synapse_id: str, input_pathway_ids: List[str],
                    unity_id: str, host_id: str,
                    kind: str = SYNAPSE_PROB_DET) -> Synapse:
        self.body.get(host_id)
        for pid in input_pathway_ids:
            if pid not in self.pathways:
                raise RefusedError(f"synapse input unknown pathway: {pid!r}")
        s = Synapse(synapse_id, input_pathway_ids, unity_id, host_id, kind)
        self.synapses[synapse_id] = s
        return s

    # -- summer circulation = active thought --------------------------------
    def circulate(self, signal: Any, synapse_id: str,
                  host_id: str, hops: int = 1) -> List[Dict[str, Any]]:
        """Outward flow is the brain thinking: signals propagate
        pathway -> synapse -> pathway. Every hop is receipted and every
        cognitive event is host-recorded."""
        self.body.get(host_id)
        syn = self.synapses[synapse_id]
        events: List[Dict[str, Any]] = []
        current = signal
        for hop in range(hops):
            judgments = [self.pathways[pid].judge(current)
                         for pid in syn.input_pathway_ids]
            for j in judgments:
                hop_receipt = build_receipt(
                    kind="PATHWAY_JUDGMENT", unity_id=j.unity_id,
                    host_id=host_id, provenance=j.provenance,
                    payload={"hop": hop, "judgment": j.as_dict()})
                events.append({"hop": hop, "judgment": j.as_dict(),
                               "receipt": hop_receipt})
                self.active_traces.append(
                    {"kind": "judgment", "hop": hop,
                     "judgment": j.as_dict(), "receipt": hop_receipt})
            fired = syn.fire(judgments)
            fire_receipt = build_receipt(
                kind="SYNAPSE_FIRE", unity_id=self.unity_id,
                host_id=host_id, provenance="DERIVED",
                payload={"hop": hop, "synapse_id": syn.id,
                         "unified": fired["unified_judgment"]})
            events.append({"hop": hop, "synapse_fire": fired,
                           "receipt": fire_receipt})
            self.active_traces.append(
                {"kind": "synapse_fire", "hop": hop,
                 "fire": fired, "receipt": fire_receipt})
            current = fired["unified_judgment"]  # thought continues downstream
        return events

    # -- +1 = synaptic firing ----------------------------------------------
    def fire_plus_one(self,
                      pathway: Pathway,
                      synapse_id: str,
                      host: str,
                      check_receipt: Dict[str, Any],
                      t_event: int,
                      ring_depth: Optional[int] = None,
                      affinity: bool = False) -> Dict[str, Any]:
        """A verified check firing +1 is a synapse firing: a neural event
        carrying the +1 deterioration curve. Requires the check's verified
        receipt — unverified work fires nothing."""
        self.body.get(host)
        syn = self.synapses[synapse_id]
        if not isinstance(check_receipt, dict) or check_receipt.get("verified") is not True:
            raise RefusedError("fire_plus_one requires a verified check receipt")
        check_unity_id(check_receipt.get("unity_id", ""))
        factor = plus_one_factor(t_event, self.t_launch, ring_depth, affinity)
        fire_event = build_receipt(
            kind="PLUS_ONE_FIRE", unity_id=self.unity_id, host_id=host,
            provenance="DERIVED",
            payload={"pathway_id": pathway.id, "synapse_id": synapse_id,
                     "check_receipt": check_receipt.get("receipt_id"),
                     "t_event": t_event, "ring_depth": ring_depth,
                     "affinity": affinity,
                     "d": factor["d"], "F": factor["F"], "R": factor["R"],
                     "mode": factor["mode"],
                     "formula": "F(d) = 0.25 + 0.75 * e^(-d), "
                                "d = dt/12 + r/2  (PLUS_ONE_INCENTIVE.md)"})
        syn.fire_log.append({"plus_one": fire_event})
        self.active_traces.append({"kind": "plus_one", "event": fire_event})
        return fire_event

    # -- merit = strengthened pathway (Hebbian) ------------------------------
    def strengthen(self, pathway_id: str, merit_delta: float,
                   receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Pathways that fire verified work get stronger. No verified work,
        no strengthening. Weights decay (the tree equalizes) via decay_all."""
        try:
            pathway = self.pathways[pathway_id]
        except KeyError:
            raise RefusedError(f"unknown pathway: {pathway_id!r}")
        return pathway.strengthen(merit_delta, receipt)

    def decay_all(self, rate: float = DECAY_RATE) -> Dict[str, float]:
        return {pid: p.decay(rate) for pid, p in self.pathways.items()}

    # -- winter return = memory consolidation --------------------------------
    def consolidate(self, reason: str, host_id: str) -> Dict[str, Any]:
        """The inward flow consolidates: active circulation traces are
        written to the long-term starch store, pruned of noise, receipted.
        Canon IV: every stored unit is receipted with its winter reason."""
        self.body.get(host_id)
        if not reason:
            raise RefusedError("consolidation requires a winter reason")
        kept, pruned = [], []
        for trace in self.active_traces:
            receipt = trace.get("receipt", {})
            prov = receipt.get("provenance", UNKNOWN)
            verified = receipt.get("payload", {}).get("verified", True)
            # Noise: UNKNOWN provenance, unverified, or unbound circuits.
            if prov == UNKNOWN or verified is not True:
                pruned.append(trace)
            else:
                kept.append(trace)
        self.starch_store.extend(kept)
        self.active_traces = []
        report = build_receipt(
            kind="WINTER_CONSOLIDATION", unity_id=self.unity_id,
            host_id=host_id, provenance="DERIVED",
            payload={"winter_reason": reason,
                     "traces_kept": len(kept), "traces_pruned": len(pruned),
                     "starch_store_size": len(self.starch_store),
                     "kept_receipts": [t["receipt"]["receipt_id"] for t in kept]})
        return {"report": report, "kept": kept, "pruned": pruned}

    # -- tapping = regulated output ------------------------------------------
    def tap(self, amount: float, unity_id: str, host_id: str,
            surplus: float) -> Dict[str, Any]:
        """Thought leaving the brain (an action, a decision, a spend) follows
        the tap rules (canon IV): only in season (no winter-protection),
        only from verified surplus, rate-limited, receipted. Founder
        extraction remains forbidden — taps serve the member's real needs."""
        check_unity_id(unity_id)
        self.body.get(host_id)
        if self.winter_gradient > 0.0:
            raise RefusedError("tap refused: winter-protection mode")
        if amount <= 0:
            raise RefusedError("tap amount must be positive")
        if amount > surplus:
            raise RefusedError("tap refused: exceeds verified surplus")
        used = self.seasonal_tapped.get(unity_id, 0.0)
        if used + amount > TAP_CAP_PROPOSED:
            raise RefusedError("tap refused: seasonal cap reached [PROPOSED cap]")
        self.seasonal_tapped[unity_id] = used + amount
        tap_receipt = build_receipt(
            kind="TAP", unity_id=unity_id, host_id=host_id, provenance="REAL",
            payload={"amount": amount, "surplus": surplus,
                     "seasonal_used": self.seasonal_tapped[unity_id],
                     "seasonal_cap": TAP_CAP_PROPOSED,
                     "cap_status": "PROPOSED — canon XIII, needs David's word"})
        self.tap_ledger.append(tap_receipt)
        return tap_receipt
