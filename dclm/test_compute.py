"""
Tests for the DCLM compute pipeline (~/workspace/unity-world/dclm/).

All must pass. Testnet only.
"""
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "core-rings")))
sys.path.insert(0, _HERE)

from rings import DecisionWave, Parliament, Point, Ring, RING_DCLM, RING_IRIS, RING_TWAIN  # noqa: E402
from compute import (  # noqa: E402
    PROVENANCE_LABELS,
    VERDICT_DECIDED,
    VERDICT_UNDECIDED,
    FEED_LIVE,
    FEED_PENDING,
    compute_world_state,
    sign_state,
    verify_envelope,
)

# The same candidate set as core-rings' own demonstration.
BALANCED_CANDIDATES = [
    Point(0.9, 0.8, 0.2),   # logical and true, but impractical
    Point(0.3, 0.4, 0.9),   # practical, but weak on logic and truth
    Point(0.7, 0.7, 0.7),   # balanced across all three
    Point(0.1, 0.1, 0.1),   # weak everywhere
]


class TestParliamentCollapse(unittest.TestCase):
    def test_collapse_picks_balanced_candidate(self):
        """Parliament collapse picks the balanced candidate, verified against
        core-rings behavior itself (not a reimplementation)."""
        wave = DecisionWave(question="which path?", candidates=list(BALANCED_CANDIDATES))
        state = compute_world_state([wave])
        verdict = state["verdicts"][0]

        # Ground truth from core-rings directly.
        expected = Parliament().decide("which path?", list(BALANCED_CANDIDATES))

        self.assertEqual(verdict["status"], VERDICT_DECIDED)
        self.assertEqual(verdict["decision"], {"x": expected.x, "y": expected.y, "z": expected.z})
        # And the balanced one is what core-rings chooses.
        self.assertEqual((expected.x, expected.y, expected.z), (0.7, 0.7, 0.7))
        self.assertAlmostEqual(verdict["balance"], Parliament.balance(expected), places=9)

    def test_balance_measure_agrees_with_rings(self):
        for p in BALANCED_CANDIDATES:
            self.assertGreaterEqual(Parliament.balance(p), 0.0)
            self.assertLessEqual(Parliament.balance(p), 1.0)
        self.assertAlmostEqual(Parliament.balance(Point(0.7, 0.7, 0.7)), 1.0, places=9)


class TestUndecidedBucket(unittest.TestCase):
    def test_no_survivors_means_undecided_not_forced(self):
        """Strict rings reject every candidate -> no forced collapse.
        The wave lands in the undecided bucket, the world goes on, and the
        verdict is marked UNKNOWN (never PASS)."""
        strict = Parliament(rings=(
            Ring("DCLM", RING_DCLM.dimension, binding=0.5),
            Ring("Iris", RING_IRIS.dimension, binding=0.5),
            Ring("Twain²", RING_TWAIN.dimension, binding=0.5),
        ))
        wave = DecisionWave(question="too weak?", candidates=[Point(0.1, 0.1, 0.1)])
        state = compute_world_state([wave], parliament=strict)
        verdict = state["verdicts"][0]

        self.assertEqual(verdict["status"], VERDICT_UNDECIDED)
        self.assertIsNone(verdict["decision"])
        self.assertIsNone(verdict["balance"])
        # UNKNOWN is never PASS: no positive claim is rendered.
        self.assertEqual(verdict["provenance"], "UNKNOWN")
        # The wave went to the undecided bucket; the world goes on.
        self.assertIn(wave, strict.undecided)
        self.assertFalse(wave.is_collapsed())

    def test_empty_candidate_list_is_undecided(self):
        wave = DecisionWave(question="nothing?", candidates=[])
        state = compute_world_state([wave])
        verdict = state["verdicts"][0]
        self.assertEqual(verdict["status"], VERDICT_UNDECIDED)
        self.assertEqual(verdict["provenance"], "UNKNOWN")


class TestProvenance(unittest.TestCase):
    def _collect_provenance(self, node, found):
        if isinstance(node, dict):
            if "provenance" in node:
                found.append(node["provenance"])
            for v in node.values():
                self._collect_provenance(v, found)
        elif isinstance(node, list):
            for v in node:
                self._collect_provenance(v, found)

    def test_every_field_carries_valid_provenance(self):
        state = compute_world_state(
            [DecisionWave(question="q", candidates=list(BALANCED_CANDIDATES))],
            feeds=[{"name": "f1", "reading": b"bytes", "reading_hash": "abc"},
                   {"name": "f2", "reading": None, "reading_hash": None}],
            registry_data=b"registry-blob",
            purity_pulse={"signed": True, "pulse_id": "pulse-1"},
        )
        labels = []
        self._collect_provenance(state, labels)
        self.assertTrue(labels, "no provenance labels found at all")
        for label in labels:
            self.assertIn(label, PROVENANCE_LABELS)

    def test_default_state_is_all_unknown(self):
        state = compute_world_state([])
        self.assertEqual(state["registry_digest"]["value"], "UNKNOWN")
        self.assertEqual(state["registry_digest"]["provenance"], "UNKNOWN")
        self.assertIsNone(state["purity_pulse"]["signed"])
        self.assertIsNone(state["purity_pulse"]["pulse_id"])
        self.assertEqual(state["purity_pulse"]["provenance"], "UNKNOWN")
        self.assertEqual(state["feed_status"], {})


class TestSigning(unittest.TestCase):
    def test_sign_verify_round_trip(self):
        state = compute_world_state(
            [DecisionWave(question="q", candidates=list(BALANCED_CANDIDATES))],
            feeds=[{"name": "f1", "reading": b"r", "reading_hash": "h"}],
        )
        envelope = sign_state(state)
        self.assertTrue(verify_envelope(envelope))
        self.assertEqual(envelope["algorithm"], "Ed25519")

    def test_tampered_state_fails_verification(self):
        state = compute_world_state(
            [DecisionWave(question="q", candidates=list(BALANCED_CANDIDATES))],
        )
        envelope = sign_state(state)
        tampered = json.loads(json.dumps(envelope))  # deep copy
        tampered["state"]["verdicts"][0]["status"] = VERDICT_UNDECIDED
        self.assertFalse(verify_envelope(tampered))

    def test_tampered_signature_fails_verification(self):
        state = compute_world_state([])
        envelope = sign_state(state)
        tampered = json.loads(json.dumps(envelope))
        tampered["signature"] = "AAAA" + tampered["signature"][4:]
        self.assertFalse(verify_envelope(tampered))


class TestFeedRule(unittest.TestCase):
    def test_pending_feeds_never_labeled_live(self):
        state = compute_world_state(
            [],
            feeds=[
                {"name": "a"},                                             # bare
                {"name": "b", "reading": b"data", "reading_hash": None},   # reading, no hash
                {"name": "c", "reading": None, "reading_hash": "deadbeef"},  # hash, no reading
                {"name": "d", "reading": b"data", "reading_hash": "deadbeef"},  # real reading+hash
            ],
        )
        status = state["feed_status"]
        self.assertEqual(status["a"]["status"], FEED_PENDING)
        self.assertEqual(status["b"]["status"], FEED_PENDING)
        self.assertEqual(status["c"]["status"], FEED_PENDING)
        self.assertEqual(status["d"]["status"], FEED_LIVE)
        self.assertEqual(status["d"]["reading_hash"], "deadbeef")
        # No PENDING feed may carry a LIVE label or a live-flavored provenance.
        for name in ("a", "b", "c"):
            self.assertNotEqual(status[name]["status"], FEED_LIVE)
            self.assertEqual(status[name]["provenance"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
