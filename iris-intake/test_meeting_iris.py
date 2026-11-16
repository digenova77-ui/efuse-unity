"""Tests for the current Iris read-only boundary and fail-closed welcome gate."""
import tempfile
import unittest

import meeting_iris
from meeting_iris import MemberUnknown, WelcomeFailedTruthGate, gather_record, meet_iris
from member_records import MemberRegistry
from iris_service import (
    AUTHORIZED_CALLERS,
    IrisLaneViolation,
    IrisService,
)
from iris_state import IrisState
from neural import make_unity_id

CALLER = make_unity_id("stand-in:testnet:swarm:worker")


def make_world():
    tmp = tempfile.mkdtemp(prefix="meeting-iris-readonly-")
    state = IrisState(state_dir=tmp + "/iris_state")
    service = IrisService(state=state)
    registry = MemberRegistry(path=tmp + "/members.json")
    return tmp, service, registry


def add_legacy_seed_mirror(service, uid):
    """Fixture only: an old IrisState seed record without DCLM proof."""
    service.state.seed_granted(uid, {
        "seed_id": "seed:legacy-fixture",
        "unity_id": uid,
        "granted_at": 1791274253,
        "transferable": False,
        "price": 0,
    })


class TestCurrentCanonAdvice(unittest.TestCase):
    def test_advice_quotes_current_canon_not_legacy_directives(self):
        _, service, _ = make_world()
        before = service.state.summary()
        advice = service.advise({"topic": "logic truth and writes"}, CALLER)
        self.assertEqual(advice["canon_version"], "1.7.3")
        cited = {section["section"] for section in advice["canon_sections"]}
        self.assertIn("I", cited)
        self.assertIn("III", cited)
        self.assertNotIn("Twain²", str(advice))
        self.assertFalse(advice["authorization_granted"])
        self.assertFalse(advice["write_performed"])
        self.assertEqual(service.state.summary(), before)

    def test_withdrawn_twain2_standin_is_not_authorized(self):
        withdrawn = make_unity_id("stand-in:testnet:twain2")
        self.assertNotIn(withdrawn, AUTHORIZED_CALLERS)


class TestReadOnlyService(unittest.TestCase):
    def test_judge_and_check_are_provisional_and_do_not_write(self):
        _, service, _ = make_world()
        before = service.state.summary()
        proposal = {
            "kind": "proposal",
            "claim": "logic and truth must both hold",
            "facts": [],
            "provenance": "DERIVED",
            "claims_fact": False,
            "unity_id": make_unity_id("test:iris-provisional"),
            "action": "LOOK",
            "context": {"schema": "dualis.relay.v1.testnet"},
        }
        judged = service.judge(proposal, CALLER)
        checked = service.check(proposal, CALLER)
        for result in (judged, checked):
            self.assertEqual(result["verdict"], "STALEMATE")
            self.assertEqual(result["narrowing"], "NOT_WIRED")
            self.assertFalse(result["authorization_granted"])
            self.assertFalse(result["write_performed"])
            self.assertTrue(result["receipt_id"].startswith("rcpt:"))
        self.assertEqual(service.state.summary(), before)

    def test_iris_cannot_issue_seed(self):
        _, service, _ = make_world()
        before = dict(service.state.seeds)
        with self.assertRaises(IrisLaneViolation):
            service.grant_seed(make_unity_id("test:iris-seed"), CALLER)
        self.assertEqual(service.state.seeds, before)


class TestSeedEvidence(unittest.TestCase):
    def test_legacy_seed_mirror_is_not_membership_evidence(self):
        _, service, registry = make_world()
        uid = make_unity_id("test:legacy-seed-only")
        add_legacy_seed_mirror(service, uid)
        with self.assertRaises(MemberUnknown):
            gather_record(uid, service.state, registry)

    def test_unverified_seed_does_not_override_real_journey(self):
        _, service, registry = make_world()
        uid = make_unity_id("test:journey-with-legacy-seed")
        add_legacy_seed_mirror(service, uid)
        registry.record_orientation_step(uid, "learn-the-tree")
        record = gather_record(uid, service.state, registry)
        self.assertIsNone(record["seed"])
        self.assertEqual(record["seed_evidence"], "NOT_VERIFIED")
        self.assertEqual(record["orientation_steps"][0]["step"], "learn-the-tree")


class TestWelcomeGate(unittest.TestCase):
    def test_welcome_stays_held_until_canonical_narrow_is_flawless(self):
        _, service, registry = make_world()
        uid = make_unity_id("test:welcome-held")
        registry.record_orientation_step(uid, "learn-the-tree")
        before = service.state.summary()
        with self.assertRaises(WelcomeFailedTruthGate):
            meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        self.assertEqual(service.state.summary(), before)

    def test_no_legacy_three_seat_fallback(self):
        _, service, registry = make_world()
        uid = make_unity_id("test:no-legacy-fallback")
        registry.record_orientation_step(uid, "learn-the-tree")
        original = service.judge

        def raise_contract_error(*args, **kwargs):
            raise TypeError("deliberate integration failure")

        service.judge = raise_contract_error
        try:
            with self.assertRaises(WelcomeFailedTruthGate):
                meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        finally:
            service.judge = original
        self.assertNotIn("twain2_judge", meeting_iris.__dict__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
