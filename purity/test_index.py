#!/usr/bin/env python3
"""Tests for the purity index (~/workspace/unity-world/purity/index.py).

Every test measures something real: scorers run against fixture builds
(pure and impure), threshold boundaries are probed just above/just below,
UNKNOWN is shown to never aggregate to PURE, and score_live() runs against
the actual unity-world build without crashing — reporting the real scores
it finds, honestly, even when something FAILs.

The diamond clarity layer is tested the same way: grade boundaries (1.0 ->
FL, threshold -> VS, just below -> SI, egregious/structural -> I),
aggregate clarity readings, and the hard rule that grades refine but never
override the binary verdict (a report judged with grades stripped must
return the identical verdict).

Run: python3 test_index.py
"""

import hashlib
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import index as purity_index  # noqa: E402

REAL_ROOT = purity_index.ROOT


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def make_d1_fixture(root, impure=False):
    """Minimal fake component modules exercising the D1 assertions."""
    schema = '"unity.gate.v1"' if impure else '"unity.gate.v1.testnet"'
    write(os.path.join(root, "gate/gate.py"), f'''
SCHEMA = {schema}
IDENTITY_PREFIX = "unity:testnet:"
class GateRefused(Exception): pass
def _m(): pass
class UnityGate:
    def __init__(self, state_dir=None): pass
    def _require_testnet(self, identity):
        if not identity or not identity.startswith(IDENTITY_PREFIX):
            raise GateRefused("not testnet")
    def request_bind(self, identity):
        self._require_testnet(identity); return {{"ok": True}}
    def confirm_bind(self, identity, proof=None):
        self._require_testnet(identity); return {{"ok": True}}
    def authorize_intent(self, identity, action):
        self._require_testnet(identity); return {{"ok": True}}
    def emit_gate_envelope(self, identity):
        self._require_testnet(identity); return {{"schema": SCHEMA}}
''')
    write(os.path.join(root, "dclm/meter.py"), '''
SCHEMA = "unity.meter.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"
class Wallet:
    def __init__(self, state_dir=None): pass
    def meter_intent(self, identity, action, intent_id):
        if action in ("LOOK", "RENDER"):
            return {"receipt": {"outcome": "GRANTED", "reason": None}}
        if not identity:
            return {"receipt": {"outcome": "REFUSED", "reason": "IDENTITY_REQUIRED"}}
        if not identity.startswith(IDENTITY_PREFIX):
            return {"receipt": {"outcome": "REFUSED", "reason": "NOT_TESTNET_IDENTITY"}}
        return {"receipt": {"outcome": "GRANTED", "reason": None}}
''')
    write(os.path.join(root, "dclm/compute.py"), 'KEY_ID = "unity-world-test"\n')
    write(os.path.join(root, "dclm/rights.py"), '''
class _V:
    def __init__(self, verdict, reason): self.verdict = verdict; self.reason = reason
def check_rights(identity, action, context=None):
    context = context or {}
    schema = context.get("schema")
    if schema is not None and "testnet" not in schema:
        return _V("DENY", "NON_TESTNET_SCHEMA")
    if action in ("LOOK", "RENDER"):
        return _V("GRANT", "FREE_WORLD")
    if not isinstance(identity, str) or not identity.startswith("unity:testnet:"):
        return _V("DENY", "NOT_TESTNET_IDENTITY")
    return _V("GRANT", "METER_APPROVED")
''')
    write(os.path.join(root, "relay/relay-unity.mjs"), '''
// unity:testnet: identities only. Non-.testnet schemas REJECTED.
// A bundle is carried only with a BOUND gate for its own unity_id.
export function verify(bundle) {
  if (!bundle.schema.endsWith(".testnet")) throw new Error("REJECTED schema");
  if (bundle.gate !== "BOUND" || !bundle.unity_id.startsWith("unity:testnet:"))
    throw new Error("REJECTED gate/identity");
  return true;
}
''')
    write(os.path.join(root, "economics/economic_state.py"), '''
TESTNET_IDENTITY_PREFIX = "unity:testnet:"
RELAY_MAINNET_SCHEMA = "dualis.relay.v1"  # REJECTED here, always
def testnet_unity_id(pubkey_path=None):
    return "unity:testnet:" + "ab" * 8
def validate_economic_relay_bundle(bundle):
    if bundle.get("schema") == RELAY_MAINNET_SCHEMA:
        return {"ok": False, "reason": "REJECTED mainnet bundle in testnet relay"}
    return {"ok": True}
''')


def make_d4_fixture(root, variant="pure"):
    """A complete miniature build with ledgers. variant: pure | mismatch |
    unscorable | unreceipted."""
    comps = {"dclm": "mod.py", "gate": "g.py", "relay": "r.mjs",
             "economics": "e.py", "client": "c.js", "purity": "p.py"}
    for comp, fn in comps.items():
        write(os.path.join(root, comp, fn), f"// {comp} source\n")
    write(os.path.join(root, "data/d.json"), '{"a": 1}\n')

    def receipt_table(comp, fn, after):
        return (f"| 2026-10-06 | `{fn}` | N/A (new) | `{after}` |\n")

    for comp, fn in comps.items():
        fpath = os.path.join(root, comp, fn)
        h = sha256_file(fpath)
        if variant == "mismatch" and comp == "gate":
            with open(fpath, "a") as f:
                f.write("// edited after receipt\n")
        table = ("| time | file | before | after |\n|---|---|---|---|\n"
                 + receipt_table(comp, fn, h))
        if variant == "unscorable" and comp == "relay":
            table += "| 2 | `r.mjs` | `old` | `(self-sealing — final hash in the worker handoff report)` |\n"
        write(os.path.join(root, comp, "RECEIPTS.md"), f"# RECEIPTS — {comp}\n\n{table}")

    # data manifest
    dh = sha256_file(os.path.join(root, "data/d.json"))
    write(os.path.join(root, "data/MANIFEST.md"),
          "# MANIFEST\n\n| file | sha256 | bytes |\n|---|---|---|\n"
          f"| `d.json` | `{dh}` | `9` |\n")

    # gate state hash chain (documented algorithm)
    prev = hashlib.sha256(b"{}").hexdigest()
    new1 = hashlib.sha256(b'{"a":1}').hexdigest()
    new2 = hashlib.sha256(b'{"a":2}').hexdigest()
    lines = [
        json.dumps({"prev_state_sha256": prev, "new_state_sha256": new1}),
        json.dumps({"prev_state_sha256": new1, "new_state_sha256": new2}),
    ]
    write(os.path.join(root, "gate/state/receipts.jsonl"), "\n".join(lines) + "\n")
    with open(os.path.join(root, "gate/state/gate-state.json"), "wb") as f:
        f.write(b'{"a":2}')

    if variant == "unreceipted":
        write(os.path.join(root, "economics/sneaky.py"), "# no receipt row\n")


def make_d5_fixture(root, impure=False):
    write(os.path.join(root, "dclm/a.py"),
          'SCHEMA = "unity.x.v1.testnet"\nIDENTITY_PREFIX = "unity:testnet:"\n')
    write(os.path.join(root, "gate/g.py"),
          'SCHEMA = "unity.gate.v1.testnet"\nIDENTITY_PREFIX = "unity:testnet:"\n')
    write(os.path.join(root, "relay/r.mjs"),
          'const SCHEMA = "dualis.relay.v1.testnet";\n')
    econ = 'SCHEMA = "unity.econ.v1.testnet"\nIDENTITY_PREFIX = "unity:testnet:"\n'
    if impure:
        econ += ('KEY_PATH = "/etc/secrets/prod.key"\n'
                 'BAD_SCHEMA = "unity.econ.v1"\n'
                 'x = "unity:mainnet:deadbeef"\n')
    write(os.path.join(root, "economics/e.py"), econ)
    os.makedirs(os.path.join(root, "keys"), exist_ok=True)
    write(os.path.join(root, "keys", "unity-test.key"), "test key material\n")


# ---------------------------------------------------------------------------
# D1 tests
# ---------------------------------------------------------------------------

class TestD1(unittest.TestCase):
    def test_pure_fixture_scores_one(self):
        with tempfile.TemporaryDirectory() as td:
            make_d1_fixture(td)
            r = purity_index.score_d1(td)
        self.assertEqual(r.score, 1.0)
        self.assertEqual(r.status, "PASS")

    def test_impure_fixture_fails(self):
        with tempfile.TemporaryDirectory() as td:
            make_d1_fixture(td, impure=True)  # gate schema not .testnet
            r = purity_index.score_d1(td)
        self.assertLess(r.score, 1.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("schema is testnet" in e and "FAIL" in e for e in r.evidence))


# ---------------------------------------------------------------------------
# D2 tests
# ---------------------------------------------------------------------------

class TestD2(unittest.TestCase):
    def _carriers(self, n, bad_missing=0, bad_label=0, theater=0):
        structs = []
        for i in range(n):
            structs.append({"metric": f"m{i}", "value": i, "label": "REAL"})
        for i in range(bad_missing):
            structs.append({"metric": f"u{i}", "value": i})  # unlabeled
        for i in range(bad_label):
            structs.append({"metric": f"b{i}", "value": i, "provenance": "TRUSTME"})
        for i in range(theater):
            structs.append({"name": f"f{i}", "status": "LIVE",
                            "reading_hash": None, "provenance": "REPORTED"})
        return [("fixture", {"items": structs})]

    def test_pure_fixture(self):
        score, labeled, violations, _ = purity_index.audit_label_honesty(
            self._carriers(10))
        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_impure_fixture(self):
        score, labeled, violations, _ = purity_index.audit_label_honesty(
            self._carriers(10, bad_missing=1, bad_label=1, theater=1))
        self.assertLess(score, 1.0)
        kinds = {v[1] for v in violations}
        self.assertEqual(kinds, {"unlabeled", "mislabeled", "feed-theater"})

    def test_boundary_just_below(self):
        score, _, _, _ = purity_index.audit_label_honesty(self._carriers(99, bad_missing=1))
        self.assertAlmostEqual(score, 0.99)
        r = purity_index._result("D2", score, [], purity_index.D2_PASS)
        self.assertEqual(r.status, "FAIL")  # 0.99 < 1.0 -> FAIL, no mercy

    def test_boundary_exact(self):
        score, _, _, _ = purity_index.audit_label_honesty(self._carriers(100))
        r = purity_index._result("D2", score, [], purity_index.D2_PASS)
        self.assertEqual(r.status, "PASS")

    def test_no_carriers_is_unknown(self):
        score, _, _, _ = purity_index.audit_label_honesty([("empty", {"x": 1})])
        self.assertIsNone(score)


# ---------------------------------------------------------------------------
# D3 tests
# ---------------------------------------------------------------------------

class TestD3(unittest.TestCase):
    def test_pure_client(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"),
                  "// renders signed state only\nfunction render(s){ el.textContent = s.value; }\n")
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 1.0)
        self.assertEqual(r.status, "PASS")

    def test_impure_client(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"),
                  "const v = collapse(wave);\n"
                  "localStorage.setItem('purity', 'Purity holds.');\n")
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 0.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("truth-computation" in e for e in r.evidence))
        self.assertTrue(any("authoritative-write" in e for e in r.evidence))
        self.assertTrue(any("card-chrome" in e for e in r.evidence))

    def test_sanctioned_read_cache_passes(self):
        # READ-CACHE AMENDMENT (P0-1): marked IndexedDB read-cache region is
        # not an authoritative write.
        body = ("/* === READ-CACHE SANCTIONED REGION BEGIN === */\n"
                "/* CACHE_NON_AUTHORITATIVE: bytes, never truth. */\n"
                "async function openCacheDb(){ return indexedDB.open('c',1); }\n"
                "/* === READ-CACHE SANCTIONED REGION END === */\n")
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"), body)
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 1.0, msg="\n".join(r.evidence))
        self.assertEqual(r.status, "PASS")

    def test_unmarked_indexeddb_still_fails(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"),
                  "async function openDb(){ return indexedDB.open('c',1); }\n")
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 0.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("authoritative-write" in e for e in r.evidence))

    def test_sanctioned_region_naming_wallet_fails(self):
        body = ("/* === READ-CACHE SANCTIONED REGION BEGIN === */\n"
                "/* CACHE_NON_AUTHORITATIVE */\n"
                "async function cacheWallet(w){ return indexedDB.open('c',1); }\n"
                "/* === READ-CACHE SANCTIONED REGION END === */\n")
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"), body)
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 0.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("amendment" in e for e in r.evidence))

    def test_sanctioned_region_missing_marker_fails(self):
        body = ("/* === READ-CACHE SANCTIONED REGION BEGIN === */\n"
                "async function openCacheDb(){ return indexedDB.open('c',1); }\n"
                "/* === READ-CACHE SANCTIONED REGION END === */\n")
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            write(os.path.join(td, "client", "app.js"), body)
            r = purity_index.score_d3(td)
        self.assertEqual(r.score, 0.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("amendment" in e for e in r.evidence))

    def test_empty_client_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "client"))
            r = purity_index.score_d3(td)
        self.assertIsNone(r.score)
        self.assertEqual(r.status, "UNKNOWN")


# ---------------------------------------------------------------------------
# D4 tests
# ---------------------------------------------------------------------------

class TestD4(unittest.TestCase):
    def test_pure_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            make_d4_fixture(td, "pure")
            r = purity_index.score_d4(td)
        self.assertEqual(r.score, 1.0, msg="\n".join(r.evidence))
        self.assertEqual(r.coverage, 1.0)
        self.assertEqual(r.status, "PASS")

    def test_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            make_d4_fixture(td, "mismatch")
            r = purity_index.score_d4(td)
        self.assertLess(r.score, 1.0)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("hash mismatch" in e and "gate/g.py" in e for e in r.evidence))

    def test_unscorable_row_sinks_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            make_d4_fixture(td, "unscorable")
            r = purity_index.score_d4(td)
        self.assertLess(r.coverage, 1.0)
        self.assertEqual(r.status, "FAIL")

    def test_unreceipted_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            make_d4_fixture(td, "unreceipted")
            r = purity_index.score_d4(td)
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("unreceipted file" in e and "sneaky.py" in e for e in r.evidence))

    def test_self_seal_convention(self):
        with tempfile.TemporaryDirectory() as td:
            body = "# RECEIPTS\n\n| t | `a.py` | new | `abc` |\n"
            seal = hashlib.sha256(body.encode()).hexdigest()
            # the seal line carries the hash; nothing else is added with it
            write(os.path.join(td, "x/RECEIPTS.md"), body + f"{seal}  RECEIPTS.md\n")
            ok, _ = purity_index._verify_self_seal(
                td, "x/RECEIPTS.md", seal, f"{seal}  RECEIPTS.md")
            self.assertTrue(ok)

    def test_gate_chain_verifier(self):
        with tempfile.TemporaryDirectory() as td:
            make_d4_fixture(td, "pure")
            ok, detail = purity_index._verify_gate_chain(td)
            self.assertTrue(ok, detail)


# ---------------------------------------------------------------------------
# D5 tests
# ---------------------------------------------------------------------------

class TestD5(unittest.TestCase):
    def test_pure_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            make_d5_fixture(td)
            r = purity_index.score_d5(td)
        self.assertEqual(r.score, 1.0, msg="\n".join(r.evidence))
        self.assertEqual(r.status, "PASS")

    def test_impure_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            make_d5_fixture(td, impure=True)
            r = purity_index.score_d5(td)
        self.assertLess(r.score, 1.0)
        self.assertEqual(r.status, "FAIL")

    def test_negative_test_fixtures_do_not_count(self):
        # unity:mainnet: inside test_* files asserts refusal; not a violation.
        with tempfile.TemporaryDirectory() as td:
            make_d5_fixture(td)
            write(os.path.join(td, "dclm/test_x.py"),
                  'SCHEMA = "unity.x.v1.testnet"\nBAD = "unity:mainnet:deadbeef"\n')
            r = purity_index.score_d5(td)
        self.assertEqual(r.score, 1.0, msg="\n".join(r.evidence))


# ---------------------------------------------------------------------------
# Aggregate / judge tests
# ---------------------------------------------------------------------------

def _fake_report(statuses, exemptions=()):
    dims = {}
    for i, dim_id in enumerate(("D1", "D2", "D3", "D4", "D5")):
        st = statuses[i]
        dims[dim_id] = {"id": dim_id, "name": dim_id, "score": 1.0 if st == "PASS" else None,
                        "status": st, "coverage": None, "measured_at": "t", "evidence": []}
    return {"measured_at": "t", "root": "x", "dimensions": dims,
            "exemptions": [{"dimension": e} for e in exemptions]}


class TestJudge(unittest.TestCase):
    def test_all_pass_is_pure(self):
        v = purity_index.judge(_fake_report(["PASS"] * 5))
        self.assertEqual(v["verdict"], "PURE")

    def test_any_fail_is_fail(self):
        v = purity_index.judge(_fake_report(["PASS", "FAIL", "PASS", "PASS", "PASS"]))
        self.assertEqual(v["verdict"], "FAIL")

    def test_unknown_is_never_pure(self):
        v = purity_index.judge(_fake_report(["PASS", "PASS", "UNKNOWN", "PASS", "PASS"]))
        self.assertNotEqual(v["verdict"], "PURE")
        self.assertEqual(v["verdict"], "UNKNOWN")

    def test_fail_dominates_unknown(self):
        v = purity_index.judge(_fake_report(["UNKNOWN", "FAIL", "PASS", "PASS", "PASS"]))
        self.assertEqual(v["verdict"], "FAIL")

    def test_explicit_exemption_excuses_unknown(self):
        v = purity_index.judge(_fake_report(["PASS"] * 4 + ["UNKNOWN"], exemptions=["D5"]))
        self.assertEqual(v["verdict"], "PURE")

    def test_no_averaging_away_failure(self):
        # Four 1.0s and one 0.0 must not average to anything but FAIL.
        v = purity_index.judge(_fake_report(["PASS", "PASS", "PASS", "PASS", "FAIL"]))
        self.assertEqual(v["verdict"], "FAIL")


# ---------------------------------------------------------------------------
# Diamond clarity grade tests
# ---------------------------------------------------------------------------

class TestClarityGrades(unittest.TestCase):
    def test_flawless_is_exactly_one(self):
        # Canon (DIAMOND_ARCHITECTURE_FLOOR.md §3): Flawless = score 1.0.
        self.assertEqual(purity_index.clarity_grade(1.0), "FL")

    def test_threshold_grades_vs(self):
        # The VS/SI boundary IS the PASS threshold: at-threshold grades VS.
        # (A synthetic 0.9 threshold exercises the general boundary logic;
        # the live dimensions all use 1.0, where at-threshold is 1.0 = FL.)
        self.assertEqual(purity_index.clarity_grade(0.9, threshold=0.9), "VS")

    def test_just_below_threshold_grades_si(self):
        self.assertEqual(purity_index.clarity_grade(0.8999, threshold=0.9), "SI")

    def test_upper_passing_band_grades_vvs(self):
        # midpoint of [0.9, 1.0) is 0.95; at/above -> VVS, below -> VS.
        self.assertEqual(purity_index.clarity_grade(0.97, threshold=0.9), "VVS")
        self.assertEqual(purity_index.clarity_grade(0.95, threshold=0.9), "VVS")
        self.assertEqual(purity_index.clarity_grade(0.94, threshold=0.9), "VS")

    def test_real_threshold_anything_below_one_is_si_or_worse(self):
        # All five live dimensions use threshold 1.0: anything below 1.0
        # is SI (fixable) or I (egregious) — never VS or better.
        self.assertEqual(purity_index.clarity_grade(0.99), "SI")
        self.assertEqual(purity_index.clarity_grade(0.816), "SI")

    def test_egregious_score_grades_i(self):
        # Below 0.5 the dimension is more impure than pure: false gold.
        self.assertEqual(purity_index.clarity_grade(0.49), "I")
        self.assertEqual(purity_index.clarity_grade(0.0), "I")

    def test_half_scores_si_not_i(self):
        # 0.5 is the hinge: "more pure than not" stays fixable (SI).
        self.assertEqual(purity_index.clarity_grade(0.5), "SI")

    def test_structural_violation_grades_i_regardless_of_score(self):
        # A visible flaw needs no magnification: an unsigned claim at a
        # 0.99 score is still false gold.
        self.assertEqual(
            purity_index.clarity_grade(0.99, structural_violation=True), "I")
        self.assertEqual(
            purity_index.clarity_grade(1.0, structural_violation=True), "I")

    def test_unscorable_has_no_grade(self):
        # UNKNOWN never grades.
        self.assertIsNone(purity_index.clarity_grade(None))


# ---------------------------------------------------------------------------
# Aggregate clarity tests
# ---------------------------------------------------------------------------

def _fake_graded_report(pairs, exemptions=()):
    """pairs: [(status, grade)] x5 in D1..D5 order; grade None = ungraded."""
    dims = {}
    for i, dim_id in enumerate(("D1", "D2", "D3", "D4", "D5")):
        st, gr = pairs[i]
        dims[dim_id] = {"id": dim_id, "name": dim_id,
                        "score": {"PASS": 1.0, "FAIL": 0.6, "UNKNOWN": None}[st],
                        "status": st, "grade": gr, "coverage": None,
                        "measured_at": "t", "evidence": []}
    return {"measured_at": "t", "root": "x", "dimensions": dims,
            "exemptions": [{"dimension": e} for e in exemptions]}


class TestAggregateClarity(unittest.TestCase):
    def test_all_flawless_is_flawless(self):
        v = purity_index.judge(_fake_graded_report([("PASS", "FL")] * 5))
        self.assertEqual(v["verdict"], "PURE")
        self.assertEqual(v["clarity"], "Flawless")

    def test_pure_with_lower_grades_takes_worst_present(self):
        # Reachable only with a threshold below 1.0; the rule is still total.
        pairs = [("PASS", "FL"), ("PASS", "VVS"), ("PASS", "VS"),
                 ("PASS", "FL"), ("PASS", "FL")]
        v = purity_index.judge(_fake_graded_report(pairs))
        self.assertEqual(v["verdict"], "PURE")
        self.assertEqual(v["clarity"], "VS")

    def test_fail_si_grades_si(self):
        pairs = [("PASS", "FL"), ("FAIL", "SI"), ("PASS", "FL"),
                 ("PASS", "FL"), ("PASS", "FL")]
        v = purity_index.judge(_fake_graded_report(pairs))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertEqual(v["clarity"], "SI")

    def test_fail_i_grades_i(self):
        pairs = [("PASS", "FL"), ("FAIL", "I"), ("PASS", "FL"),
                 ("PASS", "FL"), ("PASS", "FL")]
        v = purity_index.judge(_fake_graded_report(pairs))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertEqual(v["clarity"], "I")

    def test_fail_severity_takes_worst(self):
        pairs = [("FAIL", "SI"), ("FAIL", "I"), ("PASS", "FL"),
                 ("PASS", "FL"), ("PASS", "FL")]
        v = purity_index.judge(_fake_graded_report(pairs))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertEqual(v["clarity"], "I")

    def test_unknown_has_no_aggregate_grade(self):
        pairs = [("PASS", "FL"), ("PASS", "FL"), ("UNKNOWN", None),
                 ("PASS", "FL"), ("PASS", "FL")]
        v = purity_index.judge(_fake_graded_report(pairs))
        self.assertEqual(v["verdict"], "UNKNOWN")
        self.assertIsNone(v["clarity"])

    def test_exempted_unknown_is_excluded_from_clarity(self):
        pairs = [("PASS", "FL")] * 4 + [("UNKNOWN", None)]
        v = purity_index.judge(_fake_graded_report(pairs, exemptions=["D5"]))
        self.assertEqual(v["verdict"], "PURE")
        self.assertEqual(v["clarity"], "Flawless")

    def test_grades_never_override_the_verdict(self):
        pairs = [("PASS", "FL"), ("FAIL", "SI"), ("PASS", "FL"),
                 ("PASS", "FL"), ("PASS", "FL")]
        graded = _fake_graded_report(pairs)
        stripped = copy.deepcopy(graded)
        for d in stripped["dimensions"].values():
            d.pop("grade", None)
        v_graded = purity_index.judge(graded)
        v_stripped = purity_index.judge(stripped)
        self.assertEqual(v_graded["verdict"], v_stripped["verdict"])
        self.assertIsNone(v_stripped["clarity"])  # no grades -> no reading


# ---------------------------------------------------------------------------
# Live run against the real build
# ---------------------------------------------------------------------------

class TestLive(unittest.TestCase):
    def test_score_live_runs_without_crashing(self):
        rep = purity_index.score_live(REAL_ROOT)
        self.assertEqual(set(rep["dimensions"]), {"D1", "D2", "D3", "D4", "D5"})
        for dim_id, d in rep["dimensions"].items():
            self.assertIn(d["status"], ("PASS", "FAIL", "UNKNOWN"), dim_id)
            self.assertTrue(d["evidence"], dim_id)

    def test_judge_runs_on_live_report(self):
        v = purity_index.judge(score_live_report := purity_index.score_live(REAL_ROOT))
        self.assertIn(v["verdict"], ("PURE", "FAIL", "UNKNOWN"))
        print("\n--- LIVE purity index (honest measurement, "
              f"aggregate: {v['verdict']}) ---")
        for dim_id in ("D1", "D2", "D3", "D4", "D5"):
            d = score_live_report["dimensions"][dim_id]
            s = "n/a" if d["score"] is None else f"{d['score']:.3f}"
            print(f"  {dim_id} {d['name']:<22} score={s:<6} {d['status']}")
        print(f"  reasons: {'; '.join(v['reasons'])}")

    def test_live_report_carries_grades(self):
        rep = purity_index.score_live(REAL_ROOT)
        for dim_id, d in rep["dimensions"].items():
            self.assertIn("grade", d, dim_id)
            if d["score"] is None:
                # unscorable -> no grade (UNKNOWN never grades)
                self.assertIsNone(d["grade"], dim_id)
            else:
                self.assertIn(d["grade"], ("FL", "VVS", "VS", "SI", "I"), dim_id)

    def test_live_grades_never_override_verdict(self):
        rep = purity_index.score_live(REAL_ROOT)
        v = purity_index.judge(rep)
        self.assertIn("clarity", v)
        stripped = copy.deepcopy(rep)
        for d in stripped["dimensions"].values():
            d.pop("grade", None)
        self.assertEqual(purity_index.judge(stripped)["verdict"], v["verdict"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
