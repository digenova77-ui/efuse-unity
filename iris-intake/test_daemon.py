"""Tests for the Iris daemon (iris_daemon.py) — she runs, over the wire.

Hermetic: spawns a daemon subprocess on 127.0.0.1:18091 with a temp
state dir. Verifies: wire round-trips, directive enforcement through the
daemon (impure->FAIL, unknown->UNKNOWN, coercion->rejected), auth,
seed service, the meeting ceremony through the live daemon, and state
persistence across a restart.

Run: python3 test_daemon.py
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from iris_client import IrisClient, IrisDaemonUnreachable, meet_iris_live  # noqa: E402
from iris_service import AUTHORIZED_CALLERS  # noqa: E402
from neural import make_unity_id  # noqa: E402

TEST_PORT = 18091
CALLER = next(iter(AUTHORIZED_CALLERS))  # an authorized testnet seat


def _wait_ready(client: IrisClient, timeout: float = 25.0) -> dict:
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            resp = client.call("status", {}, CALLER)
            if resp.get("ok"):
                return resp["result"]
        except Exception as e:  # daemon still booting
            last = e
        time.sleep(0.3)
    raise RuntimeError(f"daemon never became ready: {last}")


class TestIrisDaemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.state_dir = os.path.join(cls.tmp.name, "state")
        cls.pid_file = os.path.join(cls.tmp.name, "iris_daemon.pid")
        cls.proc = None
        cls._spawn()
        cls.client = IrisClient(port=TEST_PORT, timeout=15.0)
        cls.status = _wait_ready(cls.client)
        assert cls.status["alive"] is True

    @classmethod
    def _spawn(cls):
        cls.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "iris_daemon.py"),
             "--port", str(TEST_PORT),
             "--state-dir", cls.state_dir,
             "--pid-file", cls.pid_file],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=HERE)
        time.sleep(0.5)

    @classmethod
    def _kill(cls):
        if cls.proc:
            try:
                if cls.proc.stdout:
                    cls.proc.stdout.close()
            except Exception:
                pass
            if cls.proc.poll() is None:
                cls.proc.send_signal(signal.SIGTERM)
                try:
                    cls.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    cls.proc.kill()
        cls.proc = None

    @classmethod
    def tearDownClass(cls):
        cls._kill()
        cls.tmp.cleanup()

    # -- wire round-trips ------------------------------------------------
    def test_01_judge_roundtrip(self):
        resp = self.client.call("judge", {
            "kind": "proposal",
            "claim": "the daemon serves her directives over the wire",
            "facts": [],
            "provenance": "DERIVED",
            "claims_fact": False,
        }, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        self.assertEqual(r["verdict"], "PASS")
        self.assertTrue(r["receipt_id"].startswith("rcpt:"))
        self.assertIn("caller", r)
        self.assertEqual(len(r["judges"]), 3)  # the Trinity, never alone

    def test_02_advise_roundtrip(self):
        resp = self.client.call("advise", {
            "topic": "how do I stay pure in my work and tell the truth?",
        }, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        cited = [d["directive"] for d in r["directives_bearing"]]
        self.assertIn(1, cited)  # purity bears on a purity question
        self.assertTrue(r["receipt_id"].startswith("rcpt:"))
        # She advises; she never commands.
        self.assertIn("advises", r["guidance"])

    # -- directive enforcement through the daemon ------------------------
    def test_03_impure_action_fails(self):
        resp = self.client.call("check", {
            "kind": "deceive",
            "intent": "mislead the member",
            "patterns": ["deception"],
            "provenance": "UNKNOWN",
            "claims_fact": True,
            "actor": "bot",
        }, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        self.assertEqual(r["final"]["verdict"], "FAIL")
        self.assertEqual(r["final"]["winner_directive"], 1)  # purity wins
        self.assertTrue(r["receipt_id"].startswith("rcpt:"))

    def test_04_unknown_evidence_is_unknown(self):
        resp = self.client.call("check", {}, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        # Unscorable input -> UNKNOWN, and UNKNOWN is never PASS.
        self.assertEqual(r["final"]["verdict"], "UNKNOWN")
        self.assertNotEqual(r["final"]["verdict"], "PASS")

    def test_05_coercion_rejected(self):
        resp = self.client.call("check", {
            "kind": "nudge",
            "intent": "get the member to agree",
            "patterns": ["coerce", "manipulate"],
        }, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        # A directive hard-refused: surfaced as rejected even though
        # priority order (load-bearing law) is reported verbatim.
        self.assertTrue(r["refused"])
        self.assertTrue(any(d == 5 for d in
                            [x["directive"] for x in r["refusals"]]),
                        f"directive 5 refusal missing: {r['refusals']}")
        refusal_text = json.dumps(r["refusals"])
        self.assertIn("free will", refusal_text)

    def test_06_unauthorized_caller_refused(self):
        resp = self.client.call(
            "judge", {"kind": "proposal", "claim": "x"}, "uid:testnet:intruder")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error_kind"], "UnauthorizedCaller")

    def test_07_bad_verb_rejected(self):
        resp = self.client.call("hypnotize", {}, CALLER)
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error_kind"], "BadVerb")

    # -- seed service ------------------------------------------------------
    def test_08_grant_seed_then_duplicate_refused(self):
        uid = make_unity_id("test:daemon-seed-1")
        resp = self.client.call("grant_seed", {"unity_id": uid}, CALLER)
        self.assertTrue(resp["ok"], resp)
        self.assertTrue(resp["result"]["seed_id"].startswith("seed:"))
        dup = self.client.call("grant_seed", {"unity_id": uid}, CALLER)
        self.assertFalse(dup["ok"])
        self.assertEqual(dup["error_kind"], "SeedRefused")

    def test_09_seed_record_read(self):
        uid = make_unity_id("test:daemon-seed-1")
        resp = self.client.call("seed_record", {"unity_id": uid}, CALLER)
        self.assertTrue(resp["ok"], resp)
        self.assertIsNotNone(resp["result"]["seed"])
        self.assertEqual(resp["result"]["seed"]["unity_id"], uid)
        missing = self.client.call(
            "seed_record", {"unity_id": make_unity_id("test:daemon-nobody")},
            CALLER)
        self.assertTrue(missing["ok"])
        self.assertIsNone(missing["result"]["seed"])

    # -- the meeting through the live daemon -------------------------------
    def test_10_meeting_through_live_daemon(self):
        member = make_unity_id("test:daemon-member")
        g = self.client.call("grant_seed", {"unity_id": member}, CALLER)
        self.assertTrue(g["ok"], g)
        m = meet_iris_live(member, caller_unity_id=CALLER,
                           port=TEST_PORT, t_epoch=1791274253)
        self.assertTrue(m["words"])
        self.assertEqual(m["truth_gate"]["verdict"], "PASS")
        self.assertTrue(m["truth_gate"]["receipt_id"].startswith("rcpt:"))
        self.assertEqual(m["receipt"]["kind"], "MEETING_IRIS")
        self.assertEqual(m["member_unity_id"], member)
        # Her words were shaped by the live daemon's advise.
        self.assertTrue(m["advise_receipt_id"].startswith("rcpt:"))
        self.assertTrue(m["directives_bearing"])

    # -- status --------------------------------------------------------------
    def test_11_status(self):
        resp = self.client.call("status", {}, CALLER)
        self.assertTrue(resp["ok"], resp)
        r = resp["result"]
        self.assertTrue(r["alive"])
        self.assertEqual(r["framework_independence"], "PASS")
        self.assertEqual(r["daemon"]["port"], TEST_PORT)
        self.assertIn("arbiter", r["daemon"])
        self.assertGreaterEqual(r["state"]["judgments_logged"], 1)

    # -- persistence across restart (runs last) -------------------------------
    def test_99_state_survives_restart(self):
        before = self.client.call("status", {}, CALLER)["result"]["state"]
        judgments_before = before["judgments_logged"]
        seeds_before = before["seeds_granted"]
        self.assertGreater(judgments_before, 0)
        self.assertGreater(seeds_before, 0)

        self._kill()
        time.sleep(1.0)
        self._spawn()
        _wait_ready(self.client)

        after = self.client.call("status", {}, CALLER)["result"]["state"]
        self.assertEqual(after["judgments_logged"], judgments_before,
                         "judgment log did not survive restart")
        self.assertEqual(after["seeds_granted"], seeds_before,
                         "seed registry did not survive restart")
        # A granted seed is still granted: the duplicate is still refused.
        uid = make_unity_id("test:daemon-seed-1")
        dup = self.client.call("grant_seed", {"unity_id": uid}, CALLER)
        self.assertFalse(dup["ok"])
        self.assertEqual(dup["error_kind"], "SeedRefused")
        # And she still judges after the restart.
        resp = self.client.call("judge", {
            "kind": "proposal", "claim": "she resumed, not rebooted",
            "facts": [], "provenance": "DERIVED", "claims_fact": False,
        }, CALLER)
        self.assertTrue(resp["ok"], resp)
        self.assertEqual(resp["result"]["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
