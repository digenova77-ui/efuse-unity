#!/usr/bin/env python3
"""Tests for the cluster balancer (the ingress diamond).

Run: python3 -m pytest tests/  — or: python3 tests/test_balancer.py
(stdlib only; no pytest required — uses unittest.)
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import balancer


def H(*up, **kw):
    """Build a health snapshot: H("DCLM", EUROPE="DOWN") etc."""
    h = {}
    for lane in balancer.live_lanes():
        h[lane] = {"state": "UP", "reason": "test"}
    for lane in up:
        h[lane] = {"state": "UP", "reason": "test"}
    for lane, state in kw.items():
        h[lane] = {"state": state, "reason": "test"}
    return h


class RoutingTest(unittest.TestCase):
    def test_both_up_europe_gets_amsterdam(self):
        t = balancer.compute_table(H("DCLM", "EUROPE"))
        self.assertEqual(t["europe"][0], "EUROPE")
        self.assertEqual(t["default"][0], "DCLM")

    def test_lane_down_fails_over(self):
        t = balancer.compute_table(H("DCLM", "EUROPE", EUROPE="DOWN"))
        self.assertEqual(t["europe"], ["DCLM"])
        self.assertNotIn("EUROPE", t["europe"])

    def test_unknown_is_fail_closed(self):
        t = balancer.compute_table(H("DCLM", EUROPE="UNKNOWN"))
        for view, lanes in t.items():
            self.assertNotIn("EUROPE", lanes)

    def test_both_down_empty_table(self):
        t = balancer.compute_table(H(DCLM="DOWN", EUROPE="DOWN"))
        self.assertTrue(all(v == [] for v in t.values()))

    def test_route_returns_none_when_empty(self):
        self.assertIsNone(balancer.route("europe", {"europe": []}))

    def test_route_prefers_first_healthy(self):
        t = balancer.compute_table(H("DCLM", "EUROPE"))
        self.assertEqual(balancer.route("apac", t), "DCLM")


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        balancer.STATE_DIR = self.tmp
        balancer.TRACE_LOG = os.path.join(self.tmp, "cluster-traces.jsonl")
        balancer.TABLE_FILE = os.path.join(self.tmp, "routing-table.json")

    def test_no_change_no_trace(self):
        changed, _, t1 = balancer.decide(H("DCLM", "EUROPE"))
        self.assertTrue(changed)  # first run: no prior table
        changed, _, t2 = balancer.decide(H("DCLM", "EUROPE"))
        self.assertFalse(changed)
        self.assertIsNone(t2)

    def test_change_emits_exactly_one_trace(self):
        balancer.decide(H("DCLM", "EUROPE"))
        changed, _, trace = balancer.decide(H("DCLM", EUROPE="DOWN"))
        self.assertTrue(changed)
        self.assertIsNotNone(trace)
        self.assertEqual(trace["kind"], "collapse")
        self.assertEqual(trace["node_id"], "qnode-cluster-ingress")
        self.assertIn("EUROPE", trace["outcome"])
        # second identical decide: silent
        changed, _, trace = balancer.decide(H("DCLM", EUROPE="DOWN"))
        self.assertFalse(changed)
        self.assertIsNone(trace)

    def test_trace_chain_verifies(self):
        balancer.decide(H("DCLM", "EUROPE"))
        balancer.decide(H("DCLM", EUROPE="DOWN"))
        balancer.decide(H("DCLM", EUROPE="UP"))
        ok, msg = balancer.verify_traces()
        self.assertTrue(ok, msg)

    def test_trace_chain_tamper_detected(self):
        balancer.decide(H("DCLM", "EUROPE"))
        balancer.decide(H("DCLM", EUROPE="DOWN"))
        recs = balancer.read_traces()
        recs[1]["outcome"] = "forged outcome"
        ok, _ = balancer.verify_traces(recs)
        self.assertFalse(ok)

    def test_trace_format_matches_standard(self):
        _, _, trace = balancer.decide(H("DCLM", "EUROPE"))
        for field in ("node_id", "interconnect", "lane", "kind",
                      "possibility_space", "possibility_space_hash",
                      "measurement_basis", "outcome", "measured_at",
                      "prev_trace_hash", "trace_hash"):
            self.assertIn(field, trace, "missing trace field: " + field)
        self.assertEqual(trace["possibility_space_hash"],
                         balancer.sha256(trace["possibility_space"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
