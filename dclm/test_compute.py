"""
Tests for the DCLM compute pipeline.

Pragmatism narrows. It does not seat a third ring.
Testnet only.
"""
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from rings import (  # noqa: E402
    DecisionWave,
    Parliament,
    Point,
    Ring,
    RING_DCLM,
    RING_IRIS,
    STALEMATE,
    VICTORY,
)
from compute import (  # noqa: E402
    PROVENANCE_LABELS,
    VERDICT_DECIDED,
    VERDICT_STALEMATE,
    FEED_LIVE,
    FEED_PENDING,
    compute_world_state,
    sign_state,
    verify_envelope,
)

# Four candidates, every axis positive. No constraint at the default
# minimum can remove one without removing the question of who remains.
# The old balance rule crowned (0.7, 0.7, 0.7). That crown is gone.
UNSPLIT = [
    Point(0.9, 0.8, 0.2),
    Point(0.3, 0.4, 0.9),
    Point(0.7, 0.7, 0.7),
    Point(0.1, 0.1, 0.1),
]


class TestNarrowing(unittest.TestCase):
    def test_equal_survivors_are_a_stalemate_not_a_balance_pick(self):
        wave = DecisionWave(question="which path?", candidates=list(UNSPLIT))
        state = compute_world_state([wave])
        verdict = state["verdicts"][0]

        self.assertIsNone(Parliament().decide("which path?", list(UNSPLIT)))
        self.assertEqual(verdict["status"], STALEMATE)
        self.assertEqual(verdict["status"], VERDICT_STALEMATE)
        self.assertIsNone(verdict["decision"])
        self.assertEqual(verdict["reason"], "NO_CONSTRAINT_SPLITS")
        self.assertEqual(len(verdict["remaining"]), 4)
        self.assertEqual(verdict["provenance"], "DERIVED")
        self.assertNotIn("z", verdict["candidates"][0])

    def test_one_candidate_that_satisfies_both_is_victory(self):
        strict = Parliament(rings=(
            Ring("DCLM", RING_DCLM.dimension, binding=0.5),
            Ring("Iris", RING_IRIS.dimension, binding=0.5),
        ))
        candidates = [Point(0.9, 0.8), Point(0.2, 0.1)]
        wave = DecisionWave(question="which path?", candidates=list(candidates))
        state = compute_world_state([wave], parliament=strict)
        verdict = state["verdicts"][0]

        self.assertEqual(verdict["status"], VICTORY)
        self.assertEqual(verdict["status"], VERDICT_DECIDED)
        self.assertEqual(verdict["decision"], {"x": 0.9, "y": 0.8})
        self.assertEqual(verdict["reason"], "ONE_REMAINS")
        self.assertEqual(verdict["applied"], ["DCLM", "Iris"])
        self.assertTrue(wave.is_collapsed())

    def test_constraints_that_disagree_do_not_pick(self):
        strict = Parliament(rings=(
            Ring("DCLM", RING_DCLM.dimension, binding=0.5),
            Ring("Iris", RING_IRIS.dimension, binding=0.5),
        ))
        candidates = [Point(0.9, 0.1), Point(0.1, 0.9)]
        wave = DecisionWave(question="which way?", candidates=list(candidates))
        state = compute_world_state([wave], parliament=strict)
        verdict = state["verdicts"][0]

        self.assertEqual(verdict["status"], STALEMATE)
        self.assertEqual(verdict["reason"], "CONSTRAINTS_DISAGREE")
        self.assertIsNone(verdict["decision"])
        self.assertEqual(len(verdict["remaining"]), 2)
        self.assertIn(wave, strict.stalemates)
        self.assertFalse(wave.is_collapsed())

    def test_a_candidate_that_fails_a_constraint_is_not_crowned(self):
        strict = Parliament(rings=(
            Ring("DCLM", RING_DCLM.dimension, binding=0.5),
            Ring("Iris", RING_IRIS.dimension, binding=0.5),
        ))
        wave = DecisionWave(question="too weak?", candidates=[Point(0.1, 0.1, 0.1)])
        state = compute_world_state([wave], parliament=strict)
        verdict = state["verdicts"][0]

        self.assertEqual(verdict["status"], STALEMATE)
        self.assertEqual(verdict["reason"], "NONE_SATISFIES")
        self.assertIsNone(verdict["decision"])
        self.assertEqual(verdict["remaining"], [])
        self.assertEqual(verdict["provenance"], "DERIVED")
        self.assertNotEqual(verdict["provenance"], "UNKNOWN")

    def test_empty_candidate_list_is_a_determined_stalemate(self):
        wave = DecisionWave(question="nothing?", candidates=[])
        state = compute_world_state([wave])
        verdict = state["verdicts"][0]
        self.assertEqual(verdict["status"], STALEMATE)
        self.assertEqual(verdict["reason"], "NO_CANDIDATES")
        self.assertEqual(verdict["provenance"], "DERIVED")

    def test_a_third_dimension_is_not_a_ring(self):
        offered = (
            RING_DCLM,
            RING_IRIS,
            Ring("former", 2, binding=0.99),
        )
        parliament = Parliament(rings=offered)
        self.assertEqual(tuple(ring.dimension for ring in parliament.rings), (0, 1))
        # z would have failed the dropped ring. It must not decide.
        wave = DecisionWave(question="z?", candidates=[Point(1.0, 1.0, 0.0)])
        self.assertEqual(parliament.collapse(wave), Point(1.0, 1.0, 0.0))
        self.assertEqual(wave.status, VICTORY)


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
            [DecisionWave(question="q", candidates=list(UNSPLIT))],
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
            [DecisionWave(question="q", candidates=list(UNSPLIT))],
            feeds=[{"name": "f1", "reading": b"r", "reading_hash": "h"}],
        )
        envelope = sign_state(state)
        self.assertTrue(verify_envelope(envelope))
        self.assertEqual(envelope["algorithm"], "Ed25519")

    def test_tampered_state_fails_verification(self):
        state = compute_world_state(
            [DecisionWave(question="q", candidates=list(UNSPLIT))],
        )
        envelope = sign_state(state)
        tampered = json.loads(json.dumps(envelope))
        tampered["state"]["verdicts"][0]["status"] = "FORCED"
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
                {"name": "a"},
                {"name": "b", "reading": b"data", "reading_hash": None},
                {"name": "c", "reading": None, "reading_hash": "deadbeef"},
                {"name": "d", "reading": b"data", "reading_hash": "deadbeef"},
            ],
        )
        status = state["feed_status"]
        self.assertEqual(status["a"]["status"], FEED_PENDING)
        self.assertEqual(status["b"]["status"], FEED_PENDING)
        self.assertEqual(status["c"]["status"], FEED_PENDING)
        self.assertEqual(status["d"]["status"], FEED_LIVE)
        self.assertEqual(status["d"]["reading_hash"], "deadbeef")
        for name in ("a", "b", "c"):
            self.assertNotEqual(status[name]["status"], FEED_LIVE)
            self.assertEqual(status[name]["provenance"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
