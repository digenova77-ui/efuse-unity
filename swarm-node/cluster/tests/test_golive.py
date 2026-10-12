#!/usr/bin/env python3
"""Tests for the go-live pipeline.

Gates under test: a failed stage halts, rolls back, and writes a trace
naming the failure. Dry-run never touches cutover. No live infrastructure
needed — all I/O is fixture-backed.
"""
import json
import os
import sys
import tempfile
import time
import unittest

CLUSTER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CLUSTER)
sys.path.insert(0, os.path.dirname(CLUSTER))  # swarm-node/ for signing
import golive
import balancer
from signing import backend as _bend
from signing import intent as _gintent
from signing.keys import fingerprint as _fp


def write(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class GoLiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        golive.STATE_DIR = self.tmp
        golive.RENDEZVOUS = os.path.join(self.tmp, "rendezvous")
        balancer.STATE_DIR = self.tmp
        balancer.TRACE_LOG = os.path.join(self.tmp, "traces.jsonl")
        balancer.TABLE_FILE = os.path.join(self.tmp, "routing-table.json")
        os.environ["DUALIS_ZONE_DIR"] = os.path.join(self.tmp, "bind")
        # Manifest fixture: bundle_url points at a real local file.
        self.bundle = os.path.join(self.tmp, "node.tar.gz")
        with open(self.bundle, "wb") as f:
            f.write(b"fake-bundle-bytes")
        self.manifest = os.path.join(self.tmp, "manifest.json")
        write(self.manifest, {
            "desired_version": "v9.9.9",
            "versions": {"v9.9.9": {"bundle_url": "file://" + self.bundle,
                                    "sha256": "x" * 64}}})
        self.health = os.path.join(self.tmp, "health.json")
        # Patch curl_ok to accept file:// URLs honestly.
        self._curl = golive.curl_ok
        golive.curl_ok = lambda u: u.startswith("file://") and os.path.exists(u[7:])
        # Signing regime: throwaway offline key for the tests (never real).
        self._seed, self._pub = _bend.generate()
        self.pubkey_file = os.path.join(self.tmp, "david-pubkey")
        with open(self.pubkey_file, "w") as f:
            f.write(self._pub.hex() + "\n")
        # A valid signed intent for EUROPE v9.9.9.
        payload = _gintent.build_intent("EUROPE", "v9.9.9", "x" * 64, ttl_s=600)
        self.intent_file = os.path.join(self.tmp, "intent.json")
        write(self.intent_file, _gintent.seal_intent(payload, self._seed))
        golive.STATE_DIR = self.tmp  # nonce store lands here per-run

    def _fresh_intent(self, lane="EUROPE", version="v9.9.9", bundle_hash=None):
        # Every run needs a fresh nonce — intents are single-use by design.
        payload = _gintent.build_intent(lane, version, bundle_hash or "x" * 64,
                                        ttl_s=600)
        p = os.path.join(self.tmp, "intent-%d.json" % time.time_ns())
        write(p, _gintent.seal_intent(payload, self._seed))
        return p

    def test_dry_run_stops_before_cutover(self):
        # Dry-run is preparation: no word needed, no intent published.
        write(self.health, {"EUROPE": {"state": "UP"}})
        rec = golive.run("EUROPE", "v9.9.9", self.manifest, self.health,
                         os.path.join(self.tmp, "bind"), dry_run=True)
        self.assertTrue(rec["dry_run"])
        stages = [s["stage"] for s in rec["stages"]]
        self.assertIn("PREFLIGHT", stages)
        self.assertNotIn("INTENT", stages)  # no word, no intent
        self.assertNotIn("CUTOVER", stages)
        self.assertFalse(os.path.exists(
            os.path.join(golive.RENDEZVOUS, "golive", "intent", "EUROPE.json")))

    def test_real_run_without_intent_halts(self):
        # The word must be proven: no signed intent -> HALT at INTENT.
        write(self.health, {"EUROPE": {"state": "UP"}})
        with self.assertRaises(golive.GateFailed) as c:
            golive.run("EUROPE", "v9.9.9", self.manifest, self.health,
                       os.path.join(self.tmp, "bind"), dry_run=False,
                       intent_path=None, david_pubkey_path=self.pubkey_file,
                       timeout=1)
        self.assertEqual(c.exception.stage, "INTENT")

    def test_tampered_intent_halts(self):
        # An intent for the WRONG version is not the word for this cutover.
        write(self.health, {"EUROPE": {"state": "UP"}})
        bad_payload = _gintent.build_intent("EUROPE", "v0.0.1", "y" * 64, ttl_s=600)
        bad_intent = os.path.join(self.tmp, "bad-intent.json")
        write(bad_intent, _gintent.seal_intent(bad_payload, self._seed))
        with self.assertRaises(golive.GateFailed) as c:
            golive.run("EUROPE", "v9.9.9", self.manifest, self.health,
                       os.path.join(self.tmp, "bind"), dry_run=False,
                       intent_path=bad_intent,
                       david_pubkey_path=self.pubkey_file, timeout=1)
        self.assertEqual(c.exception.stage, "INTENT")
        self.assertIn("mismatch", c.exception.reason)

    def test_wait_staged_timeout_halts_and_traces(self):
        write(self.health, {"EUROPE": {"state": "UP"}})
        with self.assertRaises(golive.GateFailed) as c:
            golive.run("EUROPE", "v9.9.9", self.manifest, self.health,
                       os.path.join(self.tmp, "bind"), dry_run=False,
                       intent_path=self._fresh_intent(),
                       david_pubkey_path=self.pubkey_file, timeout=1)
        self.assertEqual(c.exception.stage, "WAIT-STAGED")
        traces = balancer.read_traces()
        self.assertEqual(len(traces), 1)  # exactly one gap trace
        self.assertEqual(traces[0]["kind"], "gap")
        self.assertIn("WAIT-STAGED", traces[0]["outcome"])

    def tearDown(self):
        golive.curl_ok = self._curl

    def test_preflight_rejects_unknown_lane(self):
        write(self.health, {"EUROPE": {"state": "UNKNOWN"}})
        with self.assertRaises(golive.GateFailed) as c:
            golive.stage_preflight("EUROPE", "v9.9.9", self.manifest,
                                   golive.read_json(self.health))
        self.assertEqual(c.exception.stage, "PREFLIGHT")
        self.assertIn("one hand", c.exception.reason)

    def test_preflight_rejects_missing_version(self):
        write(self.health, {"EUROPE": {"state": "UP"}})
        with self.assertRaises(golive.GateFailed):
            golive.stage_preflight("EUROPE", "v0.0.0", self.manifest,
                                   golive.read_json(self.health))

    def test_rollback_restores_prior_answers(self):
        zd = os.path.join(self.tmp, "bind")
        os.makedirs(zd, exist_ok=True)
        with open(os.path.join(zd, "answers.europe"), "w") as f:
            f.write("OLD ANSWERS")
        write(os.path.join(golive.STATE_DIR, "cutover-prior.json"),
              {"answers": {"answers.europe": "OLD ANSWERS"}})
        with open(os.path.join(zd, "answers.europe"), "w") as f:
            f.write("NEW ANSWERS")
        restored = golive.rollback("test")
        self.assertIn("answers.europe", restored["restored"])
        self.assertFalse(restored["rndc_present"])  # no BIND here — honest
        with open(os.path.join(zd, "answers.europe")) as f:
            self.assertEqual(f.read(), "OLD ANSWERS")

    def test_full_path_to_confirm_failure_rolls_back(self):
        # Stage the lane so WAIT-STAGED passes, then CONFIRM fails on version.
        write(self.health, {"EUROPE": {"state": "UP"}})
        staged = {"status": "staged", "version": "v9.9.9", "lane": "EUROPE"}
        write(os.path.join(golive.RENDEZVOUS, "golive", "staged", "EUROPE.json"),
              staged)
        zd = os.path.join(self.tmp, "bind")
        os.makedirs(zd, exist_ok=True)
        for v in ("default", "europe", "apac", "mea", "oceania"):
            with open(os.path.join(zd, "answers." + v), "w") as f:
                f.write("PRIOR")
        health_stuck = os.path.join(self.tmp, "health2.json")
        write(health_stuck, {"EUROPE": {"state": "UP", "version": "v1.0.0"}})
        # Point the run at the stuck health for CONFIRM via health_fn.
        orig_run = golive.run
        with self.assertRaises(golive.GateFailed) as c:
            golive.run("EUROPE", "v9.9.9", self.manifest, self.health, zd,
                       dry_run=False,
                       intent_path=self._fresh_intent(),
                       david_pubkey_path=self.pubkey_file,
                       health_fn=lambda: golive.read_json(health_stuck),
                       timeout=1)
        self.assertEqual(c.exception.stage, "CONFIRM")
        # Rollback restored prior answers.
        with open(os.path.join(zd, "answers.europe")) as f:
            self.assertEqual(f.read(), "PRIOR")
        # A dispute trace names the failure.
        kinds = [t["kind"] for t in balancer.read_traces()]
        self.assertIn("dispute", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
