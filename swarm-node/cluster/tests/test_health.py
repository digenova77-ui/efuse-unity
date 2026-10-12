#!/usr/bin/env python3
"""Tests for the cluster health consumer.

Honesty under test: UP only from fresh dated heartbeats; DOWN from stale
or broken chains; UNKNOWN from nothing — never invented.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import health as healthmod


def tick(seconds_ago=10):
    ts = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago))
    return {"node_id": "node-test", "tick": 1,
            "at_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}


def write_jsonl(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def lane(self, name="DCLM"):
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        return d

    def test_no_data_is_unknown(self):
        r = healthmod.assess_lane("DCLM", self.lane(), 300)
        self.assertEqual(r["state"], "UNKNOWN")

    def test_fresh_heartbeat_is_up(self):
        d = self.lane()
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), [tick(10)])
        r = healthmod.assess_lane("DCLM", d, 300)
        self.assertEqual(r["state"], "UP")

    def test_stale_heartbeat_is_down(self):
        d = self.lane()
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), [tick(3600)])
        r = healthmod.assess_lane("DCLM", d, 300)
        self.assertEqual(r["state"], "DOWN")
        self.assertIn("stale", r["reason"])

    def test_broken_chain_is_down(self):
        d = self.lane()
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), [tick(10)])
        bad = {"lane": "DCLM", "seq": 1, "prev_hash": "WRONG",
               "hash": "abc", "at_utc": tick()["at_utc"]}
        write_jsonl(os.path.join(d, "attestations.jsonl"), [bad])
        r = healthmod.assess_lane("DCLM", d, 300)
        self.assertEqual(r["state"], "DOWN")
        self.assertIn("chain", r["reason"])

    def test_valid_chain_stays_up(self):
        d = self.lane()
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), [tick(10)])
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import hashlib
        body = {"lane": "DCLM", "seq": 1, "prev_hash": "GENESIS",
                "at_utc": tick()["at_utc"]}
        body["hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        write_jsonl(os.path.join(d, "attestations.jsonl"), [body])
        r = healthmod.assess_lane("DCLM", d, 300)
        self.assertEqual(r["state"], "UP")

    def test_future_tick_is_unknown_not_up(self):
        d = self.lane()
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), [tick(-3600)])
        r = healthmod.assess_lane("DCLM", d, 300)
        self.assertEqual(r["state"], "UNKNOWN")

    def test_snapshot_remote_lane_without_dir_is_unknown(self):
        snap = healthmod.snapshot({"DCLM": {"local": True}, "EUROPE": {"local": False}},
                                  state_dir=self.tmp, remote_dir=None)
        self.assertEqual(snap["EUROPE"]["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
