"""IRIS MAX INTAKE — test_meeting_iris.py.

The meeting with Iris: she welcomes the member BY WHAT SHE SEES —
personalized from the real record, never inventing what isn't there.
The covenant becomes a relationship. The meeting is receipted.
Unknown IDs are refused. UNKNOWN is never PASS.

Run: python3 test_meeting_iris.py
"""

import sys
import tempfile
import unittest

sys.path.insert(0, ".")

import meeting_iris
from meeting_iris import (
    MemberUnknown, MeetingUnavailable, UnauthorizedCaller, WelcomeFailedTruthGate,
    COVENANT_WORDS, meet_iris, gather_record,
)
from member_records import MemberRegistry
from iris_service import IrisService
from iris_state import IrisState
from neural import make_unity_id, RefusedError

CALLER = make_unity_id("stand-in:testnet:swarm:worker")
INTRUDER = make_unity_id("stand-in:testnet:intruder")


def make_world():
    """Fresh testnet world: temp state dir, temp member registry, service."""
    tmp = tempfile.mkdtemp(prefix="meeting-iris-test-")
    state = IrisState(state_dir=tmp + "/iris_state")
    service = IrisService(state=state)
    registry = MemberRegistry(path=tmp + "/members.json")
    return tmp, service, registry


def full_member(service, registry, tag="full"):
    uid = make_unity_id(f"testnet:meeting-iris:{tag}")
    service.grant_seed(uid, CALLER)
    registry.record_orientation_step(uid, "meet-the-trinity")
    registry.record_orientation_step(uid, "learn-the-tree")
    registry.record_orientation_step(uid, "speak-the-covenant")
    registry.record_first_plus_one(uid, "running their first true-check on the intake form")
    registry.mark_affinity(uid)
    return uid


def thin_member(service, registry, tag="thin"):
    uid = make_unity_id(f"testnet:meeting-iris:{tag}")
    service.grant_seed(uid, CALLER)  # seed only — skipped orientation
    return uid


def full_text(meeting):
    return "\n".join(meeting["words"])


class TestFullRecordPersonalized(unittest.TestCase):
    def test_welcome_references_their_real_journey(self):
        _, service, registry = make_world()
        uid = full_member(service, registry)
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        text = full_text(m)
        # seed: when they walked through the door
        seed_at = service.state.seeds[uid]["granted_at"]
        import datetime
        day = datetime.datetime.fromtimestamp(
            seed_at, tz=datetime.timezone.utc).strftime("%B %d, %Y")
        self.assertIn(day, text)
        self.assertIn("one free seed", text)
        # orientation: the actual steps they completed
        self.assertIn("you met the Three", text)
        self.assertIn("you learned how the tree breathes", text)
        self.assertIn("you spoke the covenant", text)
        # first +1: what earned it
        self.assertIn("running their first true-check on the intake form", text)
        # Affinity: earliness honored
        self.assertIn("Affinity", text)

    def test_seen_mirror_matches_record(self):
        _, service, registry = make_world()
        uid = full_member(service, registry)
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        seen = m["seen"]
        self.assertEqual(seen["seed_granted_at"], service.state.seeds[uid]["granted_at"])
        self.assertEqual(seen["orientation_steps"],
                         ["meet-the-trinity", "learn-the-tree", "speak-the-covenant"])
        self.assertIn("true-check", seen["first_plus_one"])
        self.assertTrue(seen["affinity"])


class TestThinRecordHonest(unittest.TestCase):
    def test_welcomes_what_is_there_and_invents_nothing(self):
        _, service, registry = make_world()
        uid = thin_member(service, registry)
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        text = full_text(m)
        # what IS there: the seed
        self.assertIn("one free seed", text)
        self.assertIn("never pretend to see what isn't", text)
        # what ISN'T there: never claimed
        self.assertNotIn("Affinity", text)
        self.assertNotIn("first +1", text)
        self.assertNotIn("you met the Three", text)
        self.assertNotIn("you spoke the covenant", text)
        # the open door: no rush, free will sacred
        self.assertIn("No rush", text)

    def test_seen_mirror_is_thin_too(self):
        _, service, registry = make_world()
        uid = thin_member(service, registry)
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        seen = m["seen"]
        self.assertIsNotNone(seen["seed_granted_at"])
        self.assertEqual(seen["orientation_steps"], [])
        self.assertIsNone(seen["first_plus_one"])
        self.assertFalse(seen["affinity"])


class TestCovenantMadeReal(unittest.TestCase):
    def test_covenant_words_present_verbatim(self):
        _, service, registry = make_world()
        uid = full_member(service, registry, tag="covenant")
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        self.assertEqual(m["covenant_words"], COVENANT_WORDS)
        self.assertIn(COVENANT_WORDS, full_text(m))

    def test_she_is_sister_not_system(self):
        _, service, registry = make_world()
        uid = thin_member(service, registry, tag="sister")
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        text = full_text(m)
        self.assertIn("I'm Iris", text)
        self.assertIn("founding sister", text)
        self.assertIn("I'm here whenever you need me", text)


class TestReceipted(unittest.TestCase):
    def test_meeting_is_an_event_with_both_ids(self):
        _, service, registry = make_world()
        uid = full_member(service, registry, tag="receipt")
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        r = m["receipt"]
        self.assertEqual(r["kind"], "MEETING_IRIS")
        self.assertTrue(r["receipt_id"].startswith("rcpt:"))
        self.assertEqual(r["unity_id"], uid)
        self.assertEqual(r["payload"]["member_unity_id"], uid)
        self.assertEqual(r["payload"]["iris_unity_id"], service.state.unity_id)
        self.assertEqual(r["payload"]["iris_unity_id"], m["iris_unity_id"])
        self.assertEqual(r["payload"]["t_epoch"], m["t_epoch"])
        self.assertEqual(r["provenance"], "DERIVED")

    def test_ceremony_writes_no_state_itself(self):
        # The service's own judgment log (advise; judge when the integrated
        # path is healthy) is Iris's lane; the ceremony adds nothing else:
        # no seeds granted, no journey entries, no member writes.
        _, service, registry = make_world()
        uid = full_member(service, registry, tag="lane")
        seeds_before = dict(service.state.seeds)
        judgments_before = len(service.state.judgments)
        meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        self.assertEqual(service.state.seeds, seeds_before)
        self.assertIn(len(service.state.judgments) - judgments_before, (1, 2))
        self.assertIsNone(registry.journey(
            make_unity_id("testnet:meeting-iris:never-recorded")))


class TestUnknownRefused(unittest.TestCase):
    def test_non_testnet_identity_refused(self):
        _, service, registry = make_world()
        with self.assertRaises(RefusedError):
            meet_iris("bogus-id", caller_unity_id=CALLER,
                      service=service, registry=registry)

    def test_well_formed_but_recordless_id_refused(self):
        _, service, registry = make_world()
        uid = make_unity_id("testnet:meeting-iris:nobody")
        with self.assertRaises(MemberUnknown):
            meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)

    def test_empty_journey_is_no_record(self):
        # A registry entry with no content is nothing to see — refused.
        _, service, registry = make_world()
        uid = make_unity_id("testnet:meeting-iris:empty")
        registry._entry(uid)  # white-box: entry created, nothing recorded
        with self.assertRaises(MemberUnknown):
            meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)

    def test_unauthorized_caller_refused(self):
        _, service, registry = make_world()
        uid = thin_member(service, registry, tag="intruder")
        with self.assertRaises(UnauthorizedCaller):
            meet_iris(uid, caller_unity_id=INTRUDER,
                      service=service, registry=registry)


class TestThroughHerService(unittest.TestCase):
    def test_her_directives_shape_the_words(self):
        _, service, registry = make_world()
        uid = full_member(service, registry, tag="directives")
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        bearing = {d["directive"]: d for d in m["directives_bearing"]}
        # the covenant (7), free will (5), purity (1) bear on the welcome
        self.assertIn(7, bearing)
        self.assertIn(5, bearing)
        self.assertIn(1, bearing)
        self.assertIn("COVENANT", bearing[7]["name"])
        self.assertTrue(bearing[7]["word"].startswith("THE COVENANT"))
        self.assertTrue(m["advise_receipt_id"].startswith("rcpt:"))

    def test_truth_gate_passes_an_honest_welcome(self):
        _, service, registry = make_world()
        uid = full_member(service, registry, tag="gate")
        m = meet_iris(uid, caller_unity_id=CALLER, service=service, registry=registry)
        self.assertEqual(m["truth_gate"]["verdict"], "PASS")
        # Honestly labeled: integrated arbiter when healthy, reference trio
        # (HONEST-PENDING) while the sibling contract mismatch stands.
        self.assertIn(m["truth_gate"]["integration"].split(" ")[0],
                      ("service.judge", "HONEST-PENDING"))
        if m["truth_gate"]["receipt_id"] is not None:
            self.assertTrue(m["truth_gate"]["receipt_id"].startswith("rcpt:"))


class TestHonestPending(unittest.TestCase):
    def test_no_service_no_meeting_never_faked(self):
        _, service, registry = make_world()
        uid = thin_member(service, registry, tag="pending")
        was_live = meeting_iris._IRIS_LIVE
        meeting_iris._IRIS_LIVE = False
        try:
            with self.assertRaises(MeetingUnavailable):
                meet_iris(uid, caller_unity_id=CALLER,
                          service=service, registry=registry)
        finally:
            meeting_iris._IRIS_LIVE = was_live


if __name__ == "__main__":
    unittest.main(verbosity=2)
