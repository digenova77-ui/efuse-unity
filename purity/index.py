#!/usr/bin/env python3
"""
PURITY INDEX — continuous scored measurement of the unity-world build
against ~/workspace/unity-world/PURITY.md (the strip team's standard).

The index MEASURES the standard; it does not replace it. The gates consult
this index; it is not a report written once.

Five dimensions, each scored 0.0-1.0 by a stated measurement rule:

  D1 Unity binding       — is every flow bound to a Unity ID?
  D2 Label honesty       — every served figure carries an honest provenance label
  D3 Client purity       — zero truth-computation / card chrome / authoritative writes on the client
  D4 Receipt completeness — every mutation receipted; receipt hashes verify against real files
  D5 Isolation           — testnet/mainnet separation (no production key paths,
                           no non-testnet schemas, test keys only)

Calibration:
  * Every dimension threshold is 1.0. The WHY is written per dimension below
    and in PURITY_INDEX.md: purity is binary at the gate (David's law).
  * A dimension that cannot be measured scores None -> status UNKNOWN, and
    UNKNOWN is never PASS. An unscorable dimension therefore keeps the
    aggregate from being PURE until it is measurable.
  * Aggregate rule (binary, no averaging away a failure):
        any dimension FAIL    -> aggregate FAIL
        elif any UNKNOWN      -> aggregate UNKNOWN  (gates must treat as not-pure, per P-6)
        else (all PASS)       -> aggregate PURE
    Named exemptions in EXEMPTIONS (below) are the only way an UNKNOWN
    dimension can be excused from the aggregate. There are none at launch.

Diamond clarity (David's law, DIAMOND_ARCHITECTURE_FLOOR.md §3):
  * clarity_grade(score) maps each 0.0-1.0 dimension score to FL / VVS /
    VS / SI / I, calibrated against the EXISTING per-dimension thresholds
    (the VS/SI boundary IS the PASS threshold; FL is canon at exactly 1.0).
    Grades refine the measurement; they never override the binary verdict.
  * The aggregate carries a clarity reading ("Flawless" when every
    dimension is FL; the worst grade present otherwise; SI/I by severity
    on FAIL). Unscorable -> no grade; UNKNOWN still never PASS.

score_live() reads the ACTUAL build on every run: it imports the real
modules, scans the real client files, verifies the real receipt hashes,
and greps the real sources for isolation violations.

Testnet only.
"""

import hashlib
import importlib.util
import inspect
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Calibration constants (named, explicit, justified in PURITY_INDEX.md)
# ---------------------------------------------------------------------------

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Per-dimension PASS thresholds. All 1.0: a single unbound flow is a bypass
# (D1/P-1), one mislabeled figure is a dishonest claim (D2/P-4), any client
# truth-computation is impure by construction (D3/P-5), an incomplete ledger
# is an unverifiable ledger (D4/strip criterion 12), one production leak
# contaminates the trust domain (D5/P-7).
D1_PASS = 1.0
D2_PASS = 1.0
D3_PASS = 1.0
D4_PASS = 1.0
D4_COVERAGE_PASS = 1.0   # every hash-claiming receipt row must be checkable
D5_PASS = 1.0

# The clarity grade for a dimension is calibrated against that dimension's
# own PASS threshold (the VS/SI boundary) — never against a second,
# grade-specific threshold. See the clarity block below.
DIMENSION_THRESHOLDS = {
    "D1": D1_PASS,
    "D2": D2_PASS,
    "D3": D3_PASS,
    "D4": D4_PASS,   # the grade grades the score; D4_COVERAGE_PASS still
    "D5": D5_PASS,   # governs PASS/FAIL — grades never override it.
}

# Honest label set: the union of compute.py's PROVENANCE_LABELS
# (REPORTED/VERIFIED/MODELED/DERIVED/UNKNOWN) and data.py's figure-level
# REAL. Both enums are builder-declared and honest; rejecting VERIFIED would
# fail honest work, and accepting an undeclared label would pass theater.
HONEST_LABELS = frozenset({"REAL", "REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"})

# Explicit exemptions: the ONLY way an UNKNOWN dimension is excused from the
# aggregate. Each entry: {"dimension": "D3", "reason": ..., "granted": ...,
# "expires": ...}. Empty at launch — nothing is excused.
EXEMPTIONS = []

DIMENSION_NAMES = {
    "D1": "Unity binding",
    "D2": "Label honesty",
    "D3": "Client purity",
    "D4": "Receipt completeness",
    "D5": "Isolation",
}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DimensionResult:
    id: str
    name: str
    score: float | None            # None -> unmeasurable -> UNKNOWN
    status: str                    # PASS | FAIL | UNKNOWN
    evidence: list = field(default_factory=list)
    coverage: float | None = None  # fraction of the scope actually measured
    structural_violation: bool = False  # a visible flaw: forces clarity "I"
    measured_at: str = ""


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_py(root, relpath, modname):
    """Import a real .py file from the build by path (no package needed)."""
    path = os.path.join(root, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _read(root, relpath):
    return _read_text(os.path.join(root, relpath))


def _result(dim_id, score, evidence, threshold, coverage=None):
    """Binary calibration: PASS iff score meets the threshold.

    D4 additionally requires coverage == 1.0; score_d4() enforces that after
    this call, so _result stays a pure threshold check."""
    if score is None:
        status = "UNKNOWN"
    elif score >= threshold:
        status = "PASS"
    else:
        status = "FAIL"
    return DimensionResult(
        id=dim_id, name=DIMENSION_NAMES[dim_id], score=score,
        status=status, evidence=evidence, coverage=coverage,
        measured_at=_now_iso(),
    )


# ===========================================================================
# Diamond clarity grades — David's law (DIAMOND_ARCHITECTURE_FLOOR.md §3).
#
# The grades REFINE the binary gate; they never override it. The PASS/FAIL
# thresholds (D1_PASS..D5_PASS, all 1.0 — Trinity-judged, PURITY_INDEX.md §2)
# are untouched by this block. A grade can never turn a FAIL into a pass, a
# PASS into a failure, or an UNKNOWN into anything graded at all.
#
# Band edges and WHY each sits where it does:
#
#   FL  (score == 1.0 exactly) ............ Canon, not calibration: the
#       floor doc pins "Flawless (FL): Absolute purity. No flaws under any
#       magnification. Score 1.0." The code does not choose this edge.
#
#   VS/SI boundary = the dimension's PASS threshold .. The floor doc's gate
#       table puts FL/VVS/VS on the PASS side and SI/I on the FAIL side, so
#       the grade boundary MUST coincide with the existing binary threshold
#       — any other placement would let a grade contradict the gate. The
#       edge is therefore DERIVED from the Trinity-judged thresholds, not
#       invented here. (All five dimensions use 1.0 today.)
#
#   VVS/VS split = midpoint of [threshold, 1.0) .. An equidistant
#       convention: VVS is the top half of passing (minute inclusions,
#       nearest flawless), VS the lower half. WHY the midpoint: the score
#       is a bare ratio with no finer structure to justify any other cut;
#       an asymmetric cut would imply precision the measurement doesn't
#       carry. HONEST NOTE: with every threshold at 1.0 this band is
#       currently empty — no live dimension can land in it. VVS/VS are
#       defined for scale coherence (they light up if the Trinity ever
#       recalibrates a threshold below 1.0), not because anything scores
#       there today.
#
#   SI/I split = 0.5 ...................... The midpoint of the failing
#       band [0, threshold): the same midpoint convention as the passing
#       band, and a semantic hinge — at/above half, the dimension is "more
#       pure than not" (SI: noticeable under magnification, fixable);
#       below half it is "more impure than pure" (I: visible flaws — false
#       gold, discard, per the floor doc). The 0.5 edge is a stated
#       convention, not a measurement; the diamond floor defines SI vs I
#       qualitatively, and the index takes the midpoint to stay symmetric
#       with the passing band.
#
#   structural_violation=True -> "I", any score .. A visible flaw doesn't
#       need magnification. An unsigned claim (a claim no key stands behind)
#       is not a partial measurement failure — it is the false-gold case
#       the floor doc says to discard. Score-independent by design.
#
# Unscorable (score None) -> no grade (None). UNKNOWN never grades, so an
# unscorable dimension can never smuggle the aggregate toward PURE.
# ===========================================================================

# Lower number = purer. Used to take "the lowest grade present".
_CLARITY_ORDER = {"FL": 0, "VVS": 1, "VS": 2, "SI": 3, "I": 4}


def clarity_grade(score, threshold=1.0, structural_violation=False):
    """Diamond clarity grade for a 0.0-1.0 dimension score.

    Returns one of "FL" | "VVS" | "VS" | "SI" | "I", or None when the
    dimension is unscorable (score None) — UNKNOWN never grades.

    threshold is the dimension's EXISTING PASS threshold (all five use 1.0
    today); it defaults to 1.0 so clarity_grade(score) grades the live
    dimensions directly. structural_violation=True forces "I" regardless of
    score (a visible flaw needs no magnification).

    Band edges (WHY documented in the block comment above): FL is canon at
    exactly 1.0; the VS/SI boundary is derived from the existing PASS
    threshold; VVS/VS and SI/I each split their band at the midpoint; 0.5
    splits "more pure than not" (SI, fixable) from "more impure than pure"
    (I, false gold).
    """
    if score is None:
        return None
    if structural_violation:
        return "I"
    if score >= 1.0:
        return "FL"            # absolute purity — canon, not calibration
    if score >= threshold:
        mid = (threshold + 1.0) / 2.0
        return "VVS" if score >= mid else "VS"
    if score < 0.5:
        return "I"             # egregious: more impure than pure
    return "SI"                # below the gate, but fixable


def aggregate_clarity(report, verdict):
    """One clarity reading for the whole build. Refines; never overrides.

    - every considered dimension FL        -> "Flawless"
    - PURE with lower grades present      -> the lowest (worst) grade present
      (unreachable while every threshold is 1.0; defined for scale coherence)
    - FAIL                                -> worst grade among the failing
      dimensions, by severity: "I" if any failing dimension is I, else "SI"
    - any non-exempt dimension ungraded   -> None (no honest reading exists;
      UNKNOWN never grades)

    Exempted dimensions are excluded, exactly as in judge(). The verdict
    itself is computed independently of this function — a grade can never
    change PURE/FAIL/UNKNOWN.
    """
    dims = report["dimensions"]
    exempted = {e["dimension"] for e in report.get("exemptions", [])}
    in_scope = [d for d in dims.values() if d.get("id") not in exempted]
    considered = [d for d in in_scope if d.get("grade") is not None]
    if len(considered) != len(in_scope):
        return None  # a non-exempt dimension is ungraded: no honest reading
    if all(d["grade"] == "FL" for d in considered):
        return "Flawless"
    if verdict == "FAIL":
        failing = [d["grade"] for d in considered if d.get("status") == "FAIL"]
        return "I" if "I" in failing else "SI"
    worst = max(considered, key=lambda d: _CLARITY_ORDER[d["grade"]])
    return worst["grade"]


# ===========================================================================
# D1 — Unity binding: is every flow bound to a Unity ID?
# Rule: D1 = binding assertions passed / binding assertions evaluated.
# ===========================================================================

def _d1_assertions(root):
    """Each entry: (name, callable) -> (passed: bool, detail: str)."""
    out = []

    def add(name, fn):
        try:
            passed, detail = fn()
        except Exception as exc:  # a crashed assertion is a failed measurement
            passed, detail = False, f"assertion raised {type(exc).__name__}: {exc}"
        out.append((name, passed, detail))

    # -- gate.py ------------------------------------------------------------
    def gate_schema():
        gate = _load_py(root, "gate/gate.py", "purity_gate")
        ok = gate.SCHEMA.endswith(".testnet")
        return ok, f"gate.SCHEMA={gate.SCHEMA!r}"
    add("gate schema is testnet", gate_schema)

    def gate_prefix():
        gate = _load_py(root, "gate/gate.py", "purity_gate")
        ok = gate.IDENTITY_PREFIX == "unity:testnet:"
        return ok, f"gate.IDENTITY_PREFIX={gate.IDENTITY_PREFIX!r}"
    add("gate identity prefix is unity:testnet:", gate_prefix)

    def gate_enforces():
        src = _read(root, "gate/gate.py")
        gate = _load_py(root, "gate/gate.py", "purity_gate")
        methods = ["request_bind", "confirm_bind", "authorize_intent", "emit_gate_envelope"]
        missing = [m for m in methods
                   if "_require_testnet" not in inspect.getsource(getattr(gate.UnityGate, m))]
        _ = src  # source retained for grep-level cross-checks below
        ok = not missing
        return ok, ("all binding entry points call _require_testnet"
                    if ok else f"no _require_testnet in: {missing}")
    add("gate entry points enforce testnet identity", gate_enforces)

    def gate_live_refusal():
        gate = _load_py(root, "gate/gate.py", "purity_gate")
        with tempfile.TemporaryDirectory() as td:
            g = gate.UnityGate(state_dir=td)
            try:
                g.request_bind("unity:mainnet:deadbeef")
                return False, "request_bind accepted a non-testnet identity"
            except Exception as e:
                ok = "testnet" in str(e).lower() or "GateRefused" in type(e).__name__
                return ok, f"request_bind refused non-testnet identity ({type(e).__name__})"
    add("gate live: non-testnet identity refused", gate_live_refusal)

    # -- meter.py -----------------------------------------------------------
    def meter_prefix():
        meter = _load_py(root, "dclm/meter.py", "purity_meter")
        ok = (meter.IDENTITY_PREFIX == "unity:testnet:"
              and meter.SCHEMA.endswith(".testnet"))
        return ok, (f"meter.IDENTITY_PREFIX={meter.IDENTITY_PREFIX!r} "
                    f"meter.SCHEMA={meter.SCHEMA!r}")
    add("meter identity prefix + schema are testnet", meter_prefix)

    def _rcpt(r):
        # meter_intent returns an envelope; the receipt lives inside.
        return r.get("receipt", r) if isinstance(r, dict) else r

    def meter_live_refusal():
        meter = _load_py(root, "dclm/meter.py", "purity_meter")
        with tempfile.TemporaryDirectory() as td:
            w = meter.Wallet(state_dir=td)
            r1 = _rcpt(w.meter_intent("unity:mainnet:deadbeef", "SEARCH", "i-1"))
            r2 = _rcpt(w.meter_intent(None, "SEARCH", "i-2"))
            r3 = _rcpt(w.meter_intent("", "SEARCH", "i-3"))
            reasons = [r1.get("reason"), r2.get("reason"), r3.get("reason")]
            ok = (reasons == ["NOT_TESTNET_IDENTITY", "IDENTITY_REQUIRED",
                              "IDENTITY_REQUIRED"])
            return ok, f"refusal reasons: {reasons}"
    add("meter live: metered actions require testnet identity", meter_live_refusal)

    def meter_live_free():
        meter = _load_py(root, "dclm/meter.py", "purity_meter")
        with tempfile.TemporaryDirectory() as td:
            w = meter.Wallet(state_dir=td)
            r = _rcpt(w.meter_intent(None, "LOOK", "i-free"))
            ok = r.get("outcome") == "GRANTED"
            return ok, (f"LOOK without identity -> outcome={r.get('outcome')!r} "
                        f"(world is free)")
    add("meter live: free actions need no identity", meter_live_free)

    def rights_live():
        rights = _load_py(root, "dclm/rights.py", "purity_rights")
        tid = "unity:testnet:" + "ab" * 8
        v_deny_mainnet = rights.check_rights(
            "unity:mainnet:x", "SEARCH", {"meter_approved": True})
        v_deny_schema = rights.check_rights(
            tid, "SEARCH", {"meter_approved": True, "schema": "dualis.relay.v1"})
        v_grant = rights.check_rights(
            tid, "SEARCH", {"meter_approved": True})
        v_free = rights.check_rights(None, "LOOK", {})
        ok = (v_deny_mainnet.verdict == "DENY"
              and v_deny_mainnet.reason == "NOT_TESTNET_IDENTITY"
              and v_deny_schema.verdict == "DENY"
              and v_deny_schema.reason == "NON_TESTNET_SCHEMA"
              and v_grant.verdict == "GRANT"
              and v_free.verdict == "GRANT")
        return ok, (f"mainnet identity -> {v_deny_mainnet.verdict}/{v_deny_mainnet.reason}; "
                    f"mainnet schema ctx -> {v_deny_schema.verdict}/{v_deny_schema.reason}; "
                    f"testnet+approved -> {v_grant.verdict}; LOOK anon -> {v_free.verdict}")
    add("rights live: authority denies non-testnet identity/schema", rights_live)

    # -- relay --------------------------------------------------------------
    def relay_binding():
        src = _read(root, "relay/relay-unity.mjs")
        has_prefix = "unity:testnet" in src
        rejects_nontestnet = bool(re.search(r"\.testnet", src)) and bool(
            re.search(r"REJECT", src))
        binds_gate = "BOUND" in src and "unity_id" in src
        ok = has_prefix and rejects_nontestnet and binds_gate
        return ok, (f"unity:testnet present={has_prefix}, "
                    f"schema rejection present={rejects_nontestnet}, "
                    f"BOUND+unity_id check present={binds_gate}")
    add("relay requires unity:testnet: + BOUND gate, rejects non-testnet schemas", relay_binding)

    # -- economics ----------------------------------------------------------
    def econ_prefix():
        econ = _load_py(root, "economics/economic_state.py", "purity_econ")
        ok = econ.TESTNET_IDENTITY_PREFIX == "unity:testnet:"
        uid = econ.testnet_unity_id()
        ok = ok and isinstance(uid, str) and uid.startswith("unity:testnet:")
        return ok, f"TESTNET_IDENTITY_PREFIX={econ.TESTNET_IDENTITY_PREFIX!r}, derived id starts with unity:testnet:={uid[:14]!r}..."
    add("economics identity prefix + derived id are testnet", econ_prefix)

    def econ_live_reject_mainnet():
        econ = _load_py(root, "economics/economic_state.py", "purity_econ")
        bundle = {"schema": econ.RELAY_MAINNET_SCHEMA, "kind": "VERDICT",
                  "envelope": {}, "endpoint": "x",
                  "unity_id": "unity:testnet:abc"}
        res = econ.validate_economic_relay_bundle(bundle)
        ok = res.get("ok") is False
        return ok, f"mainnet-schema bundle validation -> ok={res.get('ok')}, reason={res.get('reason', '')[:60]!r}"
    add("economics live: mainnet-schema bundle rejected", econ_live_reject_mainnet)

    # -- signing identity ---------------------------------------------------
    def sign_key_id():
        compute = _load_py(root, "dclm/compute.py", "purity_compute")
        ok = compute.KEY_ID == "unity-world-test"
        return ok, f"compute.KEY_ID={compute.KEY_ID!r} (testnet key, never prod)"
    add("DCLM signs under the testnet key id", sign_key_id)

    return out


def score_d1(root=ROOT):
    evidence = []
    passed = 0
    total = 0
    for name, ok, detail in _d1_assertions(root):
        total += 1
        passed += 1 if ok else 0
        evidence.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    score = (passed / total) if total else None
    evidence.insert(0, f"D1 rule: binding assertions passed / evaluated = {passed}/{total}")
    return _result("D1", score, evidence, D1_PASS)


# ===========================================================================
# D2 — Label honesty: every served figure carries an honest label.
# Rule: D2 = validly-labeled claim carriers / total claim carriers served.
# A claim carrier with a missing label (unlabeled) or a label outside
# HONEST_LABELS (mislabeled) is a violation. Non-claim dicts are out of scope.
# ===========================================================================

# Dict keys whose presence marks the dict as a served truth-claim (a leaf
# figure, verdict, receipt, or feed reading — not a container).
#
# Deliberately EXCLUDED (documented boundary, judged by the Trinity):
#  * container keys (verdicts, feed_status, registry_digest, purity_pulse,
#    price_index, emission_state, wallet_states, donation_lock,
#    sealed_verdicts): the served envelope/root is a container, not a claim;
#    its children carry the labels. Scoring the root unlabeled would punish
#    honest structure.
#  * input descriptors: data.serve_world_data()["feeds"] entries are
#    pre-compute inputs ({name, reading: None, reading_hash: None}), not
#    served figures. The served claims are compute's feed_status entries
#    (status + provenance), which ARE in scope via "status".
CLAIM_KEYS = frozenset({
    "question", "decision", "last_reading",
    "receipt_id", "metric", "balance", "claim_hash", "seal",
    "disposition", "status", "index", "company", "figures",
})


def _label_of(d):
    for key in ("provenance", "label"):
        if key in d:
            return d[key]
    return None


def audit_label_honesty(structures):
    """Walk served structures; return (score, passes, violations, notes).

    structures: iterable of (name, obj). Every dict found is classified:
      mislabeled  -> carries a label outside HONEST_LABELS
      unlabeled   -> is a claim carrier (has a CLAIM_KEY) but carries no label
      labeled     -> is a claim carrier with a valid label
      out-of-scope-> not a claim carrier (structural dicts, envelopes, etc.)
    score = labeled / (labeled + mislabeled + unlabeled); None if no carriers.
    """
    labeled = 0
    violations = []   # (path, kind, detail)
    notes = []
    seen = set()

    def walk(node, path):
        nonlocal labeled
        if isinstance(node, dict):
            if id(node) in seen:
                return
            seen.add(id(node))
            label = _label_of(node)
            is_claim = any(k in node for k in CLAIM_KEYS)
            if label is not None and label not in HONEST_LABELS:
                violations.append((path, "mislabeled",
                                   f"label {label!r} not in honest set"))
            elif is_claim and label is None:
                violations.append((path, "unlabeled",
                                   f"claim keys present {sorted(set(node) & CLAIM_KEYS)} but no label"))
            elif is_claim:
                labeled += 1
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    for name, obj in structures:
        walk(obj, name)

    # Feed-honesty sub-rule (strip criterion 7): a feed_status entry marked
    # LIVE must carry a reading_hash; PENDING must not claim one.
    for name, obj in structures:
        def feedwalk(node, path):
            if isinstance(node, dict):
                if node.get("status") == "LIVE" and not node.get("reading_hash"):
                    violations.append((path, "feed-theater",
                                       "status LIVE without reading_hash"))
                for k, v in node.items():
                    feedwalk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    feedwalk(v, f"{path}[{i}]")
        feedwalk(obj, name)

    total = labeled + len(violations)
    score = (labeled / total) if total else None
    notes.append(f"D2 rule: validly-labeled claim carriers / total carriers = {labeled}/{total}")
    return score, labeled, violations, notes


def _d2_structures(root):
    """Build the real served structures from the real modules."""
    structures = []

    compute = _load_py(root, "dclm/compute.py", "purity_compute")
    data = _load_py(root, "dclm/data.py", "purity_data")
    econ = _load_py(root, "economics/economic_state.py", "purity_econ")
    meter = _load_py(root, "dclm/meter.py", "purity_meter")

    from rings import DecisionWave, Point  # real ring logic, not copied

    waves = [
        DecisionWave(question="decided?", candidates=[Point(1.0, 0.5, 0.2), Point(-0.5, 0.1, 0.3)]),
        DecisionWave(question="undecided?", candidates=[]),  # the undecided bucket
    ]
    feeds = [
        {"name": "f-live", "reading": b"reading-bytes", "reading_hash": hashlib.sha256(b"reading-bytes").hexdigest()},
        {"name": "f-pending", "reading": None, "reading_hash": None},
    ]
    ws = compute.compute_world_state(
        waves, feeds=feeds, registry_data=b"registry-bytes",
        purity_pulse={"signed": True, "pulse_id": "pulse-1"})
    structures.append(("compute.compute_world_state", ws))

    env = compute.sign_state(ws)  # signed envelope is also served
    structures.append(("compute.sign_state envelope", env))

    bundle = data.serve_world_data()   # real PRICES.md, seals, feeds, rte
    structures.append(("data.serve_world_data", bundle))
    structures.append(("data.feed_registry", data.feed_registry()))

    estate = econ.compute_economic_state()  # asserts provenance internally
    structures.append(("economics.compute_economic_state", estate))

    with tempfile.TemporaryDirectory() as td:
        w = meter.Wallet(state_dir=td)
        ident = "unity:testnet:" + "ab" * 8
        w.faucet(ident, 10)
        receipts = [
            w.meter_intent(ident, "SEARCH", "d2-i1"),   # grant
            w.meter_intent(ident, "COMPUTE", "d2-i2"),  # refusal: insufficient
            w.meter_intent("unity:mainnet:x", "SEARCH", "d2-i3"),  # refusal: identity
        ]
        structures.append(("meter receipts", {"receipts": receipts}))

    return structures


def score_d2(root=ROOT):
    try:
        structures = _d2_structures(root)
    except Exception as exc:
        return DimensionResult(
            id="D2", name=DIMENSION_NAMES["D2"], score=None, status="UNKNOWN",
            evidence=[f"D2 rule: validly-labeled claim carriers / total carriers",
                      f"UNMEASURABLE: could not build served structures: {type(exc).__name__}: {exc}"],
            measured_at=_now_iso())
    score, labeled, violations, notes = audit_label_honesty(structures)
    evidence = list(notes)
    evidence.append(f"structures audited: {', '.join(n for n, _ in structures)}")
    for path, kind, detail in violations[:25]:
        evidence.append(f"[VIOLATION] {kind} at {path}: {detail}")
    if len(violations) > 25:
        evidence.append(f"... and {len(violations) - 25} more violations")
    if not violations:
        evidence.append(f"no mislabeled, unlabeled, or feed-theater carriers found across {labeled} claim carriers")
    return _result("D2", score, evidence, D2_PASS)


# ===========================================================================
# D3 — Client purity: zero truth-computation, zero card chrome,
# zero client-side authoritative writes.
# Rule: binary. 1.0 if no client file contains an impure construct;
# 0.0 if any does. No client files at all -> UNKNOWN (nothing measured;
# scoring an absent client 1.0 would be theater).
# ===========================================================================

CLIENT_EXTS = {".js", ".mjs", ".cjs", ".html", ".htm", ".ts", ".jsx", ".tsx"}

# Truth-computation: the client deciding, collapsing, signing, or verifying.
TRUTH_PATTERNS = [
    r"\bcollapse\s*\(", r"\bDecisionWave\b", r"\bParliament\b",
    r"verifyWorldState", r"verify_envelope", r"\bsign_state\b",
    r"computeVerdict", r"calculatePurity", r"decide\w*\(\s*['\"]verdict",
    r"crypto\.subtle\.sign", r"\bParliament\.collapse\b",
]
# Card chrome: hardcoded rendered trust-claims from the strip list (PURITY.md
# §2) — theater strings that must never ship in the client again.
CHROME_PATTERNS = [
    r"The three umpires have not been asked",
    r"Purity has not pulsed",
    r"These four lines are not signed",
    r"Ready for 227 known countries",
    r"Purity holds\.",
]
# Authoritative writes: the client minting or persisting trust state.
# READ-CACHE AMENDMENT (2026-10-06, Trinity P0-1): the original law banned
# indexedDB outright. Amended: the client performs NO WRITES OF RECORD; it may
# write bytes to IndexedDB SOLELY as a non-authoritative read cache for
# DCLM-signed chunks. Enforcement is structural: all IndexedDB access must live
# inside a fenced READ-CACHE SANCTIONED REGION carrying the
# CACHE_NON_AUTHORITATIVE marker and naming no authoritative state
# (wallet/key_balance/unity_id/metering). The fences are stripped before the
# write-pattern scan below, so unmarked indexedDB.open still fails D3, and the
# region's own boundary is checked separately by _check_cache_amendment.
# "Read cache" describes authority, not I/O: bytes are written, truth is not.
WRITE_PATTERNS = [
    r"localStorage\.setItem", r"sessionStorage\.setItem",
    r"indexedDB\.open",
    r"fetch\s*\([^)]*,\s*\{[^}]*method\s*:\s*['\"](POST|PUT|DELETE)['\"]",
]

SANCTIONED_CACHE_RE = re.compile(
    r"/\* === READ-CACHE SANCTIONED REGION BEGIN === \*/"
    r"[\s\S]*?"
    r"/\* === READ-CACHE SANCTIONED REGION END === \*/")
CACHE_AMENDMENT_MARKER = "CACHE_NON_AUTHORITATIVE"
CACHE_FORBIDDEN_TOKENS = ("wallet", "key_balance", "unity_id", "metering")


def _strip_sanctioned_regions(text):
    """Remove amended-law cache regions before the write-pattern scan."""
    return SANCTIONED_CACHE_RE.sub("", text)


def _check_cache_amendment(path, text):
    """Boundary check for each sanctioned region: the marker must be present
    and the region must not name authoritative state. Returns violations."""
    violations = []
    for m in SANCTIONED_CACHE_RE.finditer(text):
        region = m.group(0)
        lineno = text.count("\n", 0, m.start()) + 1
        if CACHE_AMENDMENT_MARKER not in region:
            violations.append((path, "amendment",
                               f"line {lineno}: sanctioned region missing "
                               f"{CACHE_AMENDMENT_MARKER} marker"))
        low = region.lower()
        bad = [t for t in CACHE_FORBIDDEN_TOKENS if t in low]
        if bad:
            violations.append((path, "amendment",
                               f"line {lineno}: sanctioned region names "
                               f"authoritative state: {', '.join(bad)}"))
    return violations

_D3_GROUPS = [("truth-computation", TRUTH_PATTERNS),
              ("card-chrome", CHROME_PATTERNS),
              ("authoritative-write", WRITE_PATTERNS)]


def scan_client_purity(client_dir):
    """Return (score, violations, notes). score None if no client files."""
    files = []
    for dirpath, _dirnames, filenames in os.walk(client_dir):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in CLIENT_EXTS:
                files.append(os.path.join(dirpath, fn))
    notes = [f"client files scanned: {len(files)}"]
    if not files:
        notes.append("no client files present: D3 unmeasurable (an absent client "
                     "is not a pure client — that would be theater)")
        return None, [], notes
    violations = []
    for path in sorted(files):
        try:
            text = _read_text(path)
        except OSError as exc:
            violations.append((path, "unreadable", str(exc)))
            continue
        raw = text
        text = _strip_sanctioned_regions(text)
        for group, patterns in _D3_GROUPS:
            for pat in patterns:
                for m in re.finditer(pat, text):
                    lineno = text.count("\n", 0, m.start()) + 1
                    violations.append((path, group, f"line {lineno}: {pat}"))
        violations.extend(_check_cache_amendment(path, raw))
    score = 1.0 if not violations else 0.0
    notes.append(f"D3 rule: binary — 1.0 iff zero impure constructs; "
                 f"violations found: {len(violations)}")
    return score, violations, notes


def score_d3(root=ROOT):
    score, violations, notes = scan_client_purity(os.path.join(root, "client"))
    evidence = list(notes)
    for path, group, detail in violations[:25]:
        evidence.append(f"[VIOLATION] {group} in {os.path.relpath(path, root)}: {detail}")
    if len(violations) > 25:
        evidence.append(f"... and {len(violations) - 25} more")
    res = _result("D3", score, evidence, D3_PASS)
    # Any impure construct in the client is a STRUCTURAL violation of the
    # mirror, not a ratio shortfall: the client decided, signed, or wrote —
    # the boundary itself is breached. Score-independent "I" (the score is
    # 0.0 anyway, so this documents intent rather than changing the grade).
    res.structural_violation = bool(violations)
    return res


# ===========================================================================
# D4 — Receipt completeness: every mutation receipted; receipt hashes verify.
# Rule: D4 = verified items / checkable items, where items are:
#   (a) every hash-claiming receipt row's after-hash vs the real file
#       (append-only ledgers: the LATEST row per file is the current record),
#   (b) data/MANIFEST.md rows vs the real data files,
#   (c) the gate state hash chain (one item),
#   (d) every source file in the measured components appears in SOME receipt
#       row — an unreceipted file is a failed item ("every mutation receipted").
# Rows that claim a hash but provide none verifiable from disk are unscorable
# and sink coverage; coverage must be 1.0 to PASS. Pure pointer rows (hashes
# live in a manifest verified separately) resolve without penalty.
# Documentation table rows (field descriptions, not mutations) are skipped.
# ===========================================================================

RECEIPT_SOURCES = [
    ("dclm/RECEIPTS.md", "dclm"),
    ("gate/RECEIPTS.md", "gate"),
    ("relay/RECEIPTS.md", "relay"),
    ("economics/RECEIPTS.md", "economics"),
    ("client/RECEIPTS.md", "client"),
    ("purity/RECEIPTS.md", "purity"),   # the measurer measures itself
]

_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
_FILETOK = re.compile(r"[`'\"]?((?:[\w.\-]+/)*[\w.\-]+\.(?:py|mjs|cjs|js|md|json|jsonl))[`'\"]?")
_POINTER_PHRASE = re.compile(r"see final line|see #\d|self-sealing|handoff|in the manifest|final hash", re.I)
_TIME_LIKE = re.compile(r"20\d\d-\d\d-\d\d")


def _resolve_receipt_path(token, ledger_subdir):
    token = token.strip().strip("`'\"")
    if "/" in token:
        return token
    return os.path.join(ledger_subdir, token)


def _iter_receipt_rows(root):
    """Yield raw row dicts from all RECEIPTS.md ledgers.

    Kinds: 'hash' (checkable), 'pointer' (hash lives elsewhere named),
    'unscorable' (claims a hash, none verifiable), 'skip' (documentation).
    """
    for rel, subdir in RECEIPT_SOURCES:
        path = os.path.join(root, rel)
        try:
            content = _read_text(path)
        except OSError:
            yield {"source": rel, "kind": "unscorable", "file_rel": None,
                   "after_hash": None, "text": "<ledger missing>",
                   "note": "RECEIPTS.md missing from disk"}
            continue
        for line in content.splitlines():
            s = line.strip()
            file_rel = None
            after = None
            if s.startswith("|") and s.endswith("|"):
                cells = [c.strip() for c in s.strip("|").split("|")]
                if any(set(c.strip()) <= set("-: ") for c in cells if c.strip()):
                    continue  # separator
                if any("before" in c.lower() and "sha" in c.lower() for c in cells):
                    continue  # header
                mtok = _FILETOK.search(s)
                if not mtok:
                    continue  # prose row, not a file row
                file_rel = _resolve_receipt_path(mtok.group(1), subdir)
                hexes = _HEX64.findall(s)
                if hexes:
                    after = hexes[-1]
                    yield {"source": rel, "kind": "hash", "file_rel": file_rel,
                           "after_hash": after, "text": s[:140], "note": ""}
                elif _POINTER_PHRASE.search(s):
                    yield {"source": rel, "kind": "pointer", "file_rel": file_rel,
                           "after_hash": None, "text": s[:140], "note": "pointer row"}
                elif len(cells) >= 4 or _TIME_LIKE.search(s):
                    malformed = re.search(r"\b[0-9a-f]{32,63}\b|\b[0-9a-f]{65,128}\b", s)
                    note = ("mutation-row-like but no verifiable after-hash" +
                            (f" (malformed hash present: {len(malformed.group(0))} hex chars, "
                             f"not a sha256)" if malformed else ""))
                    yield {"source": rel, "kind": "unscorable", "file_rel": file_rel,
                           "after_hash": None, "text": s[:140], "note": note}
                # else: documentation row — skipped silently
            else:
                # Seal / "final shas" lines: `hex  file` or `- \`file\`: \`hex\``.
                m1 = re.match(r"\s*(?:-\s*)?[`'\"]?([0-9a-f]{64})[`'\"]?\s+[`'\"]?([\w.\-/]+\.\w+)[`'\"]?\s*$", s)
                m2 = re.match(r"\s*-\s*[`'\"]?([\w.\-/]+\.\w+)[`'\"]?\s*:\s*[`'\"]?([0-9a-f]{64})[`'\"]?", s)
                m = m1 or m2
                if m:
                    if m1:
                        after, ftok = m.group(1), m.group(2)
                    else:
                        ftok, after = m.group(1), m.group(2)
                    if not _FILETOK.search(ftok):
                        continue
                    file_rel = _resolve_receipt_path(ftok, subdir)
                    yield {"source": rel, "kind": "hash", "file_rel": file_rel,
                           "after_hash": after, "text": s[:140], "note": "",
                           "seal_line": line}


def _verify_self_seal(root, ledger_rel, seal_hash, seal_line):
    """The seal-line-excluded convention (verified empirically 2026-10-06):
    the recorded seal equals sha256 of the ledger with the seal line removed.
    Both the gate and client workers independently used this convention."""
    path = os.path.join(root, ledger_rel)
    lines = _read_text(path).split("\n")
    idx = next((i for i, l in enumerate(lines) if seal_hash in l), None)
    if idx is None:
        return False, "seal line not found in ledger"
    canonical = "\n".join(l for i, l in enumerate(lines) if i != idx)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual == seal_hash:
        return True, "self-seal verifies under the seal-line-excluded convention"
    return False, (f"self-seal mismatch even under seal-line-excluded convention "
                   f"(seal {seal_hash[:12]}… vs computed {actual[:12]}…)")


def _universe_files(root):
    """Every source file that must appear in some receipt row."""
    universe = []
    for d in ("dclm", "gate", "relay", "economics", "client", "data", "purity"):
        dpath = os.path.join(root, d)
        for dirpath, _dn, fns in os.walk(dpath):
            rel_dir = os.path.relpath(dirpath, root)
            parts = rel_dir.split(os.sep)
            if "__pycache__" in parts or "state" in parts or "state-meter" in parts:
                continue  # runtime state, not source mutations
            for fn in fns:
                if not fn.endswith((".py", ".mjs", ".cjs", ".js", ".md", ".json")):
                    continue
                if fn in ("RECEIPTS.md", "MANIFEST.md"):
                    continue  # ledgers themselves
                if fn.endswith(".jsonl") or fn == "index_receipts.log":
                    continue  # receipt logs, not mutated sources
                if d == "data" and fn.endswith(".json"):
                    pass  # vendored data: receipted via MANIFEST.md
                universe.append(os.path.join(rel_dir, fn))
    # keys/ holds key material, not code mutations — out of scope by design.
    return sorted(universe)


def _parse_manifest_rows(root):
    """data/MANIFEST.md rows: file/sha256/bytes — the data-vendoring receipts."""
    path = os.path.join(root, "data/MANIFEST.md")
    out = []
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return out
    for line in lines:
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
        if len(cells) < 3 or not _HEX64.fullmatch(cells[1] or ""):
            continue
        fname = cells[0]
        out.append({"source": "data/MANIFEST.md",
                    "file_rel": os.path.join("data", fname),
                    "after_hash": cells[1], "row": s[:120],
                    "checkable": True, "note": ""})
    return out


def _verify_gate_chain(root):
    """Verify the gate state hash chain per gate/RECEIPTS.md's algorithm."""
    log = os.path.join(root, "gate/state/receipts.jsonl")
    state = os.path.join(root, "gate/state/gate-state.json")
    try:
        prev = hashlib.sha256(b"{}").hexdigest()  # empty-state hash
        n = 0
        with open(log, encoding="utf-8") as fh:
            log_lines = fh.read().splitlines()
        for line in log_lines:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("prev_state_sha256") != prev:
                return False, f"chain break at entry {n}: prev mismatch"
            prev = e["new_state_sha256"]
            n += 1
        if n == 0:
            return False, "receipt log empty"
        cur = _sha256_file(state)
        if cur != prev:
            return False, "chain intact but current state file hash != last new_state_sha256"
        return True, f"chain intact over {n} mutations; state file matches chain tip"
    except OSError as exc:
        return False, f"unreadable: {exc}"
    except (json.JSONDecodeError, KeyError) as exc:
        return False, f"malformed log: {exc}"


def score_d4(root=ROOT):
    evidence = []
    verified = 0
    checkable = 0
    unscorable = 0
    receipted_files = set()

    # Latest-row-wins per (source, file): append-only ledgers.
    latest = {}
    order = 0
    pointer_rows = []
    for row in _iter_receipt_rows(root):
        order += 1
        if row["kind"] == "skip":
            continue
        if row["kind"] == "pointer":
            pointer_rows.append(row)
            if row["file_rel"]:
                receipted_files.add(row["file_rel"])
            continue
        if row["kind"] == "unscorable":
            unscorable += 1
            evidence.append(f"[UNSCORABLE] {row['source']}: {row['file_rel']} — {row['note']}")
            continue
        key = (row["source"], row["file_rel"])
        latest[key] = (order, row)

    # Resolve pointer rows: "in the manifest" -> the manifest rows (checked
    # separately below); "see final line"/"see #N" -> the seal/final-sha line
    # already parsed as a hash row; anything else stays unscorable.
    for row in pointer_rows:
        text = row["text"]
        if re.search(r"in the manifest", text, re.I):
            evidence.append(f"[POINTER] {row['source']}: {row['file_rel']} — hashes live in "
                            f"data/MANIFEST.md, verified row-by-row below")
        elif re.search(r"see final line|see #\d", text, re.I):
            evidence.append(f"[POINTER] {row['source']}: {row['file_rel']} — superseded by the "
                            f"seal/final-sha line ({row['text'][:80]}…)")
        else:
            unscorable += 1
            evidence.append(f"[UNSCORABLE] {row['source']}: {row['file_rel']} — {row['text'][:100]}… "
                            f"(no verifiable hash on disk; e.g. deferred to a handoff report)")

    for (source, file_rel), (_o, row) in sorted(latest.items()):
        ledger_rel = source
        is_self_seal = (file_rel == ledger_rel)
        fpath = os.path.join(root, file_rel)
        checkable += 1
        receipted_files.add(file_rel)
        if is_self_seal and row.get("seal_line") is not None:
            ok, detail = _verify_self_seal(root, ledger_rel, row["after_hash"], row["seal_line"])
            if ok:
                verified += 1
            else:
                evidence.append(f"[FAIL] {source}: self-seal — {detail}")
            continue
        try:
            actual = _sha256_file(fpath)
        except OSError:
            evidence.append(f"[FAIL] {source}: {file_rel} — file missing on disk")
            continue
        if actual == row["after_hash"]:
            verified += 1
        else:
            evidence.append(f"[FAIL] {source}: {file_rel} — hash mismatch "
                            f"(receipt {row['after_hash'][:12]}… vs disk {actual[:12]}…)")

    # data/MANIFEST.md rows: the data-vendoring receipts.
    for row in _parse_manifest_rows(root):
        checkable += 1
        receipted_files.add(row["file_rel"])
        fpath = os.path.join(root, row["file_rel"])
        try:
            actual = _sha256_file(fpath)
        except OSError:
            evidence.append(f"[FAIL] {row['source']}: {row['file_rel']} — file missing on disk")
            continue
        if actual == row["after_hash"]:
            verified += 1
        else:
            evidence.append(f"[FAIL] {row['source']}: {row['file_rel']} — hash mismatch "
                            f"(manifest {row['after_hash'][:12]}… vs disk {actual[:12]}…)")

    # Gate state hash chain: one receipt item.
    checkable += 1
    ok, detail = _verify_gate_chain(root)
    if ok:
        verified += 1
        evidence.append(f"[PASS] gate state hash chain: {detail}")
    else:
        evidence.append(f"[FAIL] gate state hash chain: {detail}")

    # Completeness: every source file appears in some receipt row.
    for f in _universe_files(root):
        if f not in receipted_files:
            checkable += 1
            evidence.append(f"[FAIL] unreceipted file: {f} — no receipt row in any RECEIPTS.md / MANIFEST.md")

    score = (verified / checkable) if checkable else None
    total_claiming = checkable + unscorable
    coverage = (checkable / total_claiming) if total_claiming else None
    evidence.insert(0, f"D4 rule: verified items / checkable items = {verified}/{checkable}; "
                       f"coverage (checkable / hash-claiming rows) = {checkable}/{total_claiming}")
    res = _result("D4", score, evidence, D4_PASS, coverage=coverage)
    if res.status == "PASS" and (coverage is None or coverage < D4_COVERAGE_PASS):
        res.status = "FAIL"
        res.evidence.append("coverage < 1.0: some hash-claiming rows are unscorable — the ledger is incomplete")
    return res


# ===========================================================================
# D5 — Isolation: testnet/mainnet separation.
# Rule: D5 = isolation assertions passed / evaluated.
# Scope (exactly the dimension's parenthetical): no production key paths,
# no non-testnet schemas, test keys only.
# ===========================================================================

_CODE_DIRS = ("dclm", "gate", "relay", "economics")
_CODE_EXTS = (".py", ".mjs", ".js")

_PROD_KEY_PATH_PATTERNS = [
    r"/etc/secrets", r"\.aws/credentials", r"\.aws/config",
    r"prod\.key", r"production\.key", r"mainnet\.key", r"real[-_]key",
]
_HARDCODED_SECRET_PATTERNS = [
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bghp_[A-Za-z0-9]{16,}\b",
    r"\bxox[bap]-[A-Za-z0-9\-]+\b",
    r"\bsk-live-[A-Za-z0-9]+\b",
]


def _code_files(root):
    for d in _CODE_DIRS:
        dpath = os.path.join(root, d)
        for dirpath, _dn, fns in os.walk(dpath):
            if "__pycache__" in dirpath:
                continue
            for fn in fns:
                if fn.endswith(_CODE_EXTS):
                    yield os.path.join(dirpath, fn)


def _d5_assertions(root):
    out = []

    def add(name, fn):
        try:
            passed, detail = fn()
        except Exception as exc:
            passed, detail = False, f"assertion raised {type(exc).__name__}: {exc}"
        out.append((name, passed, detail))

    def schemas():
        bad = []
        designated_reject_ok = 0
        for path in _code_files(root):
            text = _read_text(path)
            for m in re.finditer(r"\b([A-Za-z_]*SCHEMA)\s*=\s*[\"']([^\"']+)[\"']", text):
                name, val = m.group(1), m.group(2)
                if name.startswith("REASON_"):
                    continue  # a refusal-reason constant, not an accepted schema
                rel = os.path.relpath(path, root)
                if val.endswith(".testnet"):
                    continue
                if "MAINNET" in name.upper() and re.search(r"[Rr][Ee][Jj][Ee][Cc][Tt]", text):
                    designated_reject_ok += 1  # the named mainnet schema exists only to be rejected
                    continue
                bad.append(f"{rel}: {name}={val!r}")
        ok = not bad
        return ok, ("all schema constants end .testnet"
                    + (f" ({designated_reject_ok} designated mainnet-reject fixtures)" if designated_reject_ok else "")
                    if ok else f"non-testnet schemas: {bad}")
    add("no non-testnet schemas in code", schemas)

    def prefixes():
        bad = []
        n = 0
        for path in _code_files(root):
            text = _read_text(path)
            for m in re.finditer(r"\b([A-Za-z_]*IDENTITY_PREFIX)\s*=\s*[\"']([^\"']+)[\"']", text):
                n += 1
                if "testnet" not in m.group(2).lower():
                    bad.append(f"{os.path.relpath(path, root)}: {m.group(1)}={m.group(2)!r}")
        ok = n > 0 and not bad
        return ok, (f"{n} identity-prefix constants, all testnet" if ok
                    else (f"non-testnet prefixes: {bad}" if bad else "no identity-prefix constants found"))
    add("identity prefixes are testnet", prefixes)

    def keynames():
        kdir = os.path.join(root, "keys")
        try:
            names = os.listdir(kdir)
        except OSError as exc:
            return False, f"keys/ unreadable: {exc}"
        bad = [n for n in names if "test" not in n.lower()]
        ok = names and not bad
        return ok, (f"keys/: {sorted(names)} — all test-named" if ok
                    else f"non-test key files: {bad}" if bad else "keys/ empty")
    add("keys/ holds test keys only", keynames)

    def prodpaths():
        bad = []
        for path in _code_files(root):
            text = _read_text(path)
            for pat in _PROD_KEY_PATH_PATTERNS:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    lineno = text.count("\n", 0, m.start()) + 1
                    bad.append(f"{os.path.relpath(path, root)}:{lineno}: {pat}")
        ok = not bad
        return ok, ("no production key paths in code" if ok else f"production key paths: {bad[:5]}")
    add("no production key paths in code", prodpaths)

    def mainnet_identity():
        # Test files are excluded: they MUST use bad identities as negative
        # fixtures (asserting refusal). A test asserting refusal of
        # "unity:mainnet:..." strengthens isolation; it does not break it.
        # The live refusal behavior itself is measured in D1.
        bad = []
        for path in _code_files(root):
            base = os.path.basename(path)
            if base.startswith("test_") or ".test." in base:
                continue
            text = _read_text(path)
            for m in re.finditer(r"unity:mainnet:", text):
                lineno = text.count("\n", 0, m.start()) + 1
                bad.append(f"{os.path.relpath(path, root)}:{lineno}")
        ok = not bad
        return ok, ("no unity:mainnet: identity in non-test code" if ok else f"mainnet identity strings: {bad[:5]}")
    add("no mainnet identity strings in code", mainnet_identity)

    def secrets():
        bad = []
        for path in _code_files(root):
            text = _read_text(path)
            for pat in _HARDCODED_SECRET_PATTERNS:
                for m in re.finditer(pat, text):
                    lineno = text.count("\n", 0, m.start()) + 1
                    bad.append(f"{os.path.relpath(path, root)}:{lineno}: {pat[:30]}")
        ok = not bad
        return ok, ("no embedded private keys or hardcoded secret tokens" if ok else f"secret material: {bad[:5]}")
    add("no embedded private keys / hardcoded secrets", secrets)

    return out


def score_d5(root=ROOT):
    evidence = []
    passed = 0
    total = 0
    for name, ok, detail in _d5_assertions(root):
        total += 1
        passed += 1 if ok else 0
        evidence.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    score = (passed / total) if total else None
    evidence.insert(0, f"D5 rule: isolation assertions passed / evaluated = {passed}/{total}")
    return _result("D5", score, evidence, D5_PASS)


# ===========================================================================
# Continuous scoring + the binary gate judgment
# ===========================================================================

def score_live(root=ROOT):
    """Measure the actual build right now. Returns the full report dict.

    Each dimension carries its diamond clarity grade alongside its score
    (grade is None when the dimension is unscorable). Grades refine the
    measurement; they never touch the verdict — see judge()."""
    dims = {
        "D1": score_d1(root),
        "D2": score_d2(root),
        "D3": score_d3(root),
        "D4": score_d4(root),
        "D5": score_d5(root),
    }
    return {
        "measured_at": _now_iso(),
        "root": root,
        "dimensions": {k: {"id": v.id, "name": v.name, "score": v.score,
                           "status": v.status,
                           "grade": clarity_grade(
                               v.score,
                               threshold=DIMENSION_THRESHOLDS[k],
                               structural_violation=v.structural_violation),
                           "coverage": v.coverage,
                           "measured_at": v.measured_at, "evidence": v.evidence}
                       for k, v in dims.items()},
        "exemptions": list(EXEMPTIONS),
    }


def judge(report=None, root=ROOT):
    """Binary aggregate verdict over a score_live() report.

    FAIL    if any dimension FAILs.
    UNKNOWN if any dimension is UNKNOWN and none FAIL
            (gates MUST treat UNKNOWN as not-pure — P-6).
    PURE    only if every dimension PASSes (or is explicitly exempted).

    The verdict logic is untouched by the clarity layer: grades are
    computed from the same scores and reported in "clarity", but no grade
    can change the verdict. (Tested: stripping grades from a report leaves
    the verdict identical.)
    """
    report = report or score_live(root)
    dims = report["dimensions"]
    exempted = {e["dimension"] for e in report.get("exemptions", [])}
    verdict = "PURE"
    reasons = []
    for dim_id in ("D1", "D2", "D3", "D4", "D5"):
        st = dims[dim_id]["status"]
        if st == "FAIL":
            verdict = "FAIL"
            reasons.append(f"{dim_id} FAIL")
        elif st == "UNKNOWN":
            if dim_id in exempted:
                reasons.append(f"{dim_id} UNKNOWN but explicitly exempted")
            elif verdict != "FAIL":
                verdict = "UNKNOWN"
                reasons.append(f"{dim_id} UNKNOWN (never PASS)")
    if verdict == "PURE":
        reasons.append("all five dimensions PASS; nothing exempted" if not exempted
                       else "all non-exempt dimensions PASS")
    return {"verdict": verdict, "reasons": reasons,
            "clarity": aggregate_clarity(report, verdict),
            "report": report, "judged_at": _now_iso()}


def _fmt(report, verdict):
    lines = [f"purity index — measured {report['measured_at']}", ""]
    for dim_id in ("D1", "D2", "D3", "D4", "D5"):
        d = report["dimensions"][dim_id]
        s = "n/a" if d["score"] is None else f"{d['score']:.3f}"
        g = d.get("grade") or "ungraded"
        cov = "" if d["coverage"] is None else f" (coverage {d['coverage']:.2f})"
        lines.append(f"  {dim_id} {d['name']:<22} score={s:<6} {d['status']:<7} grade={g}{cov}")
    lines += ["", f"aggregate verdict: {verdict['verdict']}",
              f"aggregate clarity: {verdict.get('clarity') or 'ungraded'}",
              f"reasons: {'; '.join(verdict['reasons'])}"]
    return "\n".join(lines)


if __name__ == "__main__":
    rep = score_live()
    v = judge(rep)
    print(_fmt(rep, v))
    if "--json" in sys.argv:
        print(json.dumps({"verdict": v["verdict"], "clarity": v["clarity"],
                          "reasons": v["reasons"], "report": rep}, indent=1))
    # Exit codes for gate scripting: 0 = PURE (may pass), 1 = FAIL,
    # 2 = UNKNOWN (never PASS — the gate must treat this as not-pure).
    sys.exit({"PURE": 0, "FAIL": 1, "UNKNOWN": 2}[v["verdict"]])
