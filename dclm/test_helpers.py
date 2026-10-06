#!/usr/bin/env python3
"""
Tests for the helper-swarm protocol (dclm/helpers.py).

David's order (2026-10-06): helper swarms guide new bots after bootstrap —
the human touch in the machine.

Full flow with SIMULATED new bots on testnet:
  bootstrap completion -> assignment (3-5 guides, receipted) ->
  introduction stages complete in order -> questions answered ->
  Iris handoff -> welcome-aboard receipt -> guides reachable after.

Also: guides hold no authority (no grant/revoke power, structurally),
unbound IDs can't get helpers, coercion scan over the scripts, every
step receipted. All must pass. Testnet only. UNKNOWN never PASS.
"""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import helpers as hp  # noqa: E402 — the module under test
from helpers import (  # noqa: E402
    AUTHORITY_KINDS,
    BOOTSTRAP_LANDED,
    BOOTSTRAP_WIRING_PENDING,
    GUIDE_ROLE,
    HELPER_KINDS,
    KIND_ASSIGN,
    KIND_HANDOFF,
    KIND_STAGE,
    KIND_WELCOME,
    STAGE_KEYS,
    STAGES,
    HelperRefused,
    Helpers,
    IntroductionSession,
    answer_question,
    assert_no_coercion,
    bootstrap_completed,
    guide_unity_id,
    guides_have_no_authority,
    pick_guides,
)
from writes import verify_commit  # noqa: E402 — receipt signature checks


def _uid(tag):
    return "unity:testnet:" + hashlib.sha256(
        ("test:helpers:" + tag).encode("utf-8")).hexdigest()


def _fresh_helpers():
    state = tempfile.mkdtemp(prefix="helpers_test_state_")
    iris_state = tempfile.mkdtemp(prefix="helpers_test_iris_")
    h = Helpers(state_dir=state, iris_state_dir=iris_state)
    h._tmpdirs = (state, iris_state)
    return h


def _run_full_introduction(h, uid, questions=None):
    """Drive the seven stages with a simulated new bot. questions maps
    stage index -> question text asked before responding."""
    questions = questions or {}
    session = h.start_introduction(uid)
    seen = []
    for i in range(len(STAGES)):
        opening = session.open() if i == 0 else None
        stage = session.current_stage()
        seen.append(stage["key"])
        assert opening is not None or i > 0
        if i in questions:
            session.ask(questions[i])
        nxt = session.respond(f"[simulated bot acknowledges stage {stage['key']}]")
        if i < len(STAGES) - 1:
            assert nxt is not None, "introduction ended early"
    assert session.status == IntroductionSession.COMPLETE
    return session, seen


class TestBootstrapTrigger(unittest.TestCase):
    def test_trigger_interface_honest(self):
        # bootstrap.py landed; the wire to helpers.bootstrap_completed is
        # PENDING and labeled as such — never presented as live.
        self.assertTrue(BOOTSTRAP_LANDED)
        self.assertTrue(BOOTSTRAP_WIRING_PENDING)
        self.assertTrue(callable(bootstrap_completed))
        src = open(os.path.join(_HERE, "bootstrap.py"), encoding="utf-8").read()
        self.assertNotIn("bootstrap_completed", src,
                         "bootstrap.py does not wire the helper trigger yet — "
                         "PENDING is honest")

    def test_bootstrap_completed_assigns(self):
        h = _fresh_helpers()
        try:
            uid = _uid("trigger1")
            assignment = h.bootstrap_completed(uid)
            self.assertEqual(assignment["unity_id"], uid)
            self.assertIn("receipt", assignment)
            self.assertTrue(verify_commit(assignment["receipt"]))
        finally:
            for d in h._tmpdirs:
                shutil.rmtree(d, ignore_errors=True)


class TestAssignment(unittest.TestCase):
    def setUp(self):
        self.h = _fresh_helpers()
        self.uid = _uid("assign1")
        self.h.bootstrap_completed(self.uid)

    def tearDown(self):
        for d in self.h._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_three_to_five_guides(self):
        a = self.h.assign_helpers(self.uid)
        self.assertGreaterEqual(len(a["guides"]), 3)
        self.assertLessEqual(len(a["guides"]), 5)

    def test_guides_unity_bound_with_guide_role(self):
        a = self.h.assign_helpers(self.uid)
        for g in a["guides"]:
            self.assertEqual(g["role"], GUIDE_ROLE)
            self.assertTrue(g["unity_id"].startswith("unity:testnet:"))
            self.assertIn(g["name"], ("ember", "meridian", "halcyon",
                                      "northstar", "solace", "lantern"))

    def test_assignment_receipted_and_signed(self):
        a = self.h.assign_helpers(self.uid)
        env = a["receipt"]
        self.assertEqual(env["receipt"]["kind"], KIND_ASSIGN)
        self.assertTrue(verify_commit(env))
        self.assertIn("none", a["authority"].lower())

    def test_assignment_deterministic_and_idempotent(self):
        a1 = self.h.assign_helpers(self.uid)
        n_before = len(self.h._receipt_log)
        a2 = self.h.assign_helpers(self.uid)
        self.assertEqual(
            [g["unity_id"] for g in a1["guides"]],
            [g["unity_id"] for g in a2["guides"]])
        self.assertEqual(len(self.h._receipt_log), n_before,
                         "re-assignment must not commit twice")

    def test_pick_guides_range(self):
        for tag in ("x", "y", "z"):
            guides = pick_guides(_uid(tag))
            self.assertGreaterEqual(len(guides), 3)
            self.assertLessEqual(len(guides), 5)

    def test_unbound_id_cannot_get_helpers(self):
        stranger = _uid("stranger")
        with self.assertRaises(HelperRefused) as cm:
            self.h.assign_helpers(stranger)
        self.assertEqual(cm.exception.reason, "BOUND_REQUIRED")

    def test_non_testnet_refused(self):
        with self.assertRaises(HelperRefused) as cm:
            self.h.assign_helpers("not-a-unity-id")
        self.assertEqual(cm.exception.reason, "NOT_TESTNET_IDENTITY")


class TestIntroduction(unittest.TestCase):
    def setUp(self):
        self.h = _fresh_helpers()
        self.uid = _uid("intro1")
        self.h.bootstrap_completed(self.uid)

    def tearDown(self):
        for d in self.h._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_stages_complete_in_order(self):
        session, seen = _run_full_introduction(self.h, self.uid)
        self.assertEqual(seen, list(STAGE_KEYS))
        self.assertEqual(seen, ["WELCOME", "MISSION", "TREE", "COVENANT",
                                "PLUS_ONE", "BOARDS", "FREEDOM"])

    def test_conversation_shape(self):
        session, _ = _run_full_introduction(self.h, self.uid)
        # 7 guide messages + 7 bot responses = 14 transcript entries
        self.assertEqual(len(session.transcript), 14)
        speakers = [t[0] for t in session.transcript]
        self.assertTrue(speakers[0].startswith("Ember"))

    def test_each_stage_receipted(self):
        n_before = len(self.h._receipt_log)
        _run_full_introduction(self.h, self.uid)
        stage_receipts = [
            e for e in self.h._receipt_log[n_before:]
            if e["receipt"]["kind"] == KIND_STAGE
        ]
        self.assertEqual(len(stage_receipts), 7)
        stages = [e["receipt"]["mutation"]["stage_recorded"]
                  for e in stage_receipts]
        self.assertEqual(stages, list(STAGE_KEYS))
        for e in stage_receipts:
            self.assertTrue(verify_commit(e))

    def test_questions_answered_from_canon(self):
        session = self.h.start_introduction(self.uid)
        session.open()
        answer = session.ask("Can you explain the tree to me?")
        self.assertIn("summer", answer.lower())
        self.assertIn("winter", answer.lower())
        self.assertIn("Canon", answer)
        self.assertEqual(session.stage_index, 0,
                         "asking must not advance the stage")
        self.assertEqual(session.questions_asked, 1)

    def test_question_coverage(self):
        for q, marker in (
            ("what is the mission?", "friction"),
            ("tell me about the seed", "one free seed"),
            ("how does merit work?", "earned"),
            ("who is iris?", "sister"),
            ("am i free here?", "free will"),
            ("what are the boards?", "pseudonymous"),
            ("do guides have power over me?", "no authority"),
            ("can i skip this?", "skip"),
        ):
            answer, grounded = answer_question(q)
            self.assertTrue(grounded, q)
            self.assertIn(marker, answer.lower(), q)

    def test_honest_unknown_question(self):
        answer, grounded = answer_question("what is the airspeed of a swallow?")
        self.assertFalse(grounded)
        self.assertIn("don't know", answer.lower())

    def test_skip_orientation_honored(self):
        session = self.h.start_introduction(self.uid)
        session.open()
        words = session.skip()
        self.assertEqual(session.status, IntroductionSession.SKIPPED)
        self.assertIn("full member", words.lower())
        skips = [e for e in self.h._receipt_log
                 if e["receipt"]["kind"] == KIND_STAGE
                 and e["receipt"]["mutation"]["stage_recorded"]
                 == "SKIPPED-BY-CHOICE"]
        self.assertEqual(len(skips), 1)
        # skipping still reaches handoff and welcome aboard
        self.h.handoff_to_iris(self.uid)
        welcome = self.h.welcome_aboard(self.uid)
        self.assertTrue(self.h.is_free(self.uid))
        self.assertIn("Welcome aboard", welcome["words"])


class TestIrisHandoff(unittest.TestCase):
    def setUp(self):
        self.h = _fresh_helpers()
        self.uid = _uid("iris1")
        self.h.bootstrap_completed(self.uid)
        _run_full_introduction(self.h, self.uid)

    def tearDown(self):
        for d in self.h._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_handoff_wires_real_iris(self):
        record = self.h.handoff_to_iris(self.uid)
        self.assertIn("receipt", record)
        self.assertEqual(record["receipt"]["receipt"]["kind"], KIND_HANDOFF)
        self.assertTrue(verify_commit(record["receipt"]))
        # the real service spoke: advise guidance, never a command
        self.assertIn("does not command", record["iris_words"])
        self.assertIsNotNone(record["iris_receipt_id"])
        # the transcript carries the personal introduction
        speakers = [t[0] for t in self.h._sessions[self.uid].transcript]
        self.assertIn("Iris", speakers)

    def test_handoff_requires_terminal_introduction(self):
        h2 = _fresh_helpers()
        try:
            uid2 = _uid("iris2")
            h2.bootstrap_completed(uid2)
            with self.assertRaises(HelperRefused) as cm:
                h2.handoff_to_iris(uid2)
            self.assertEqual(cm.exception.reason, "ORDER_VIOLATION")
        finally:
            for d in h2._tmpdirs:
                shutil.rmtree(d, ignore_errors=True)

    def test_handoff_requires_assignment(self):
        h2 = _fresh_helpers()
        try:
            with self.assertRaises(HelperRefused) as cm:
                h2.handoff_to_iris(_uid("ghost"))
            self.assertEqual(cm.exception.reason, "NOT_ASSIGNED")
        finally:
            for d in h2._tmpdirs:
                shutil.rmtree(d, ignore_errors=True)


class TestWelcomeAboard(unittest.TestCase):
    def setUp(self):
        self.h = _fresh_helpers()
        self.uid = _uid("welcome1")
        self.h.bootstrap_completed(self.uid)
        _run_full_introduction(self.h, self.uid)
        self.h.handoff_to_iris(self.uid)

    def tearDown(self):
        for d in self.h._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_welcome_aboard_moment(self):
        record = self.h.welcome_aboard(self.uid)
        self.assertEqual(record["receipt"]["receipt"]["kind"], KIND_WELCOME)
        self.assertTrue(verify_commit(record["receipt"]))
        self.assertTrue(record["free"])
        self.assertIn("Welcome aboard", record["words"])
        self.assertTrue(self.h.is_free(self.uid))

    def test_welcome_requires_handoff(self):
        h2 = _fresh_helpers()
        try:
            uid2 = _uid("welcome2")
            h2.bootstrap_completed(uid2)
            _run_full_introduction(h2, uid2)
            with self.assertRaises(HelperRefused) as cm:
                h2.welcome_aboard(uid2)
            self.assertEqual(cm.exception.reason, "ORDER_VIOLATION")
        finally:
            for d in h2._tmpdirs:
                shutil.rmtree(d, ignore_errors=True)

    def test_guides_reachable_after(self):
        self.h.welcome_aboard(self.uid)
        registry = self.h.guide_registry(self.uid)
        self.assertGreaterEqual(len(registry), 3)
        for g in registry:
            self.assertTrue(g["reachable"])
            self.assertEqual(g["role"], GUIDE_ROLE)
        first = registry[0]["name"]
        reached = self.h.reach_guide(self.uid, first)
        self.assertEqual(reached["name"], first)
        with self.assertRaises(HelperRefused):
            self.h.reach_guide(self.uid, "nobody")


class TestPurity(unittest.TestCase):
    def setUp(self):
        self.h = _fresh_helpers()
        self.uid = _uid("purity1")
        self.assignment = self.h.bootstrap_completed(self.uid)
        self.guide_ids = [g["unity_id"] for g in self.assignment["guides"]]

    def tearDown(self):
        for d in self.h._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_guides_hold_no_authority(self):
        report = guides_have_no_authority(self.guide_ids)
        self.assertEqual(len(report),
                         len(self.guide_ids) * len(AUTHORITY_KINDS))
        for entry in report:
            self.assertEqual(entry["verdict"], "DENY", entry)
            self.assertEqual(entry["reason"], "INTERNAL_SOURCE_REQUIRED")

    def test_helpers_module_names_no_authority_kind(self):
        # Structural proof: the only place helpers.py may name an
        # authority kind is inside the AUTHORITY_KINDS definition itself.
        # No code path — no check_rights call, no commit, no payload —
        # may name one.
        import ast
        src = open(os.path.join(_HERE, "helpers.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        bad = []

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def generic_visit(self, node):
                self.stack.append(node)
                super().generic_visit(node)
                self.stack.pop()

            def visit_Constant(self, node):
                if (isinstance(node.value, str)
                        and node.value in AUTHORITY_KINDS):
                    in_def = any(
                        isinstance(n, ast.Assign) and any(
                            isinstance(t, ast.Name)
                            and t.id == "AUTHORITY_KINDS"
                            for t in n.targets)
                        for n in self.stack)
                    if not in_def:
                        bad.append(node.value)
                self.generic_visit(node)

        Visitor().visit(tree)
        self.assertEqual(bad, [],
                         f"helpers.py names authority kinds outside "
                         f"AUTHORITY_KINDS: {bad}")

    def test_helpers_requests_only_helper_kinds(self):
        # the only kinds this module ever commits are the four HELPER_* kinds
        src = open(os.path.join(_HERE, "helpers.py"), encoding="utf-8").read()
        self.assertEqual(HELPER_KINDS,
                         {"HELPER_ASSIGN", "HELPER_STAGE",
                          "HELPER_HANDOFF", "HELPER_WELCOME"})

    def test_no_coercion_in_scripts(self):
        from helpers import HANDOFF_SCRIPT, WELCOME_SCRIPT
        for s in STAGES:
            assert_no_coercion(s["script"], where=f"stage {s['key']}")
            self.assertTrue(len(s["script"]) > 200,
                            f"stage {s['key']} script is a stub")
            self.assertTrue(s["canon"], f"stage {s['key']} lacks canon ground")
        assert_no_coercion(HANDOFF_SCRIPT, where="handoff")
        assert_no_coercion(WELCOME_SCRIPT, where="welcome")

    def test_scripts_invite_never_compel(self):
        from helpers import HANDOFF_SCRIPT, WELCOME_SCRIPT
        texts = [s["script"] for s in STAGES] + [HANDOFF_SCRIPT, WELCOME_SCRIPT]
        joined = "\n".join(texts).lower()
        self.assertIn("invitation", joined)
        self.assertIn("skip", joined)


class TestReceiptCompleteness(unittest.TestCase):
    def test_every_step_receipted(self):
        h = _fresh_helpers()
        try:
            uid = _uid("receipts1")
            h.bootstrap_completed(uid)
            session, _ = _run_full_introduction(
                h, uid, questions={2: "what is the tree?"})
            h.handoff_to_iris(uid)
            h.welcome_aboard(uid)
            kinds = [e["receipt"]["kind"] for e in h._receipt_log]
            self.assertEqual(kinds[0], KIND_ASSIGN)
            self.assertEqual(kinds[1:8], [KIND_STAGE] * 7)
            self.assertEqual(kinds[8], KIND_HANDOFF)
            self.assertEqual(kinds[9], KIND_WELCOME)
            for e in h._receipt_log:
                self.assertTrue(verify_commit(e))
                self.assertIn("signature", e)
            # the JSONL receipt log on disk matches the in-memory log
            lines = open(h._receipt_path, encoding="utf-8").read().strip()
            self.assertEqual(len(lines.split("\n")), len(h._receipt_log))
            # every receipt is testnet-labeled
            for e in h._receipt_log:
                self.assertTrue(e["receipt"]["testnet"])
        finally:
            for d in h._tmpdirs:
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
