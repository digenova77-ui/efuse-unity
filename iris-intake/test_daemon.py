"""Wire tests for the legacy testnet daemon under the current read-only law."""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from iris_client import IrisClient, meet_iris_live  # noqa: E402
from iris_service import AUTHORIZED_CALLERS  # noqa: E402
from meeting_iris import MemberUnknown  # noqa: E402
from neural import make_unity_id  # noqa: E402

TEST_PORT = 18091
CALLER = next(iter(AUTHORIZED_CALLERS))


def _wait_ready(client: IrisClient, timeout: float = 25.0, proc=None) -> dict:
    end = time.time() + timeout
    last = None
    while time.time() < end:
        if proc is not None and proc.poll() is not None:
            output = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            raise RuntimeError(
                f"daemon exited before ready (rc={proc.returncode}): {output}"
            )
        try:
            response = client.call("status", {}, CALLER)
            if response.get("ok"):
                return response["result"]
        except Exception as exc:
            last = exc
        time.sleep(0.3)
    output = ""
    if proc is not None and proc.stdout and proc.poll() is not None:
        output = proc.stdout.read().decode("utf-8", errors="replace")
    raise RuntimeError(
        f"daemon never became ready: {last}; poll={proc.poll() if proc else 'unknown'}; {output}"
    )


class TestIrisDaemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.state_dir = os.path.join(cls.tmp.name, "state")
        cls.pid_file = os.path.join(cls.tmp.name, "iris_daemon.pid")
        cls.proc = None
        cls.receipt_path = os.path.join(HERE, "IRIS_SELF_CHECK.json")
        cls.original_receipt = None
        if os.path.isfile(cls.receipt_path):
            with open(cls.receipt_path, "rb") as handle:
                cls.original_receipt = handle.read()
        try:
            activation = subprocess.run(
                [sys.executable, os.path.join(HERE, "activate_iris.py")],
                capture_output=True, text=True, cwd=HERE,
            )
            if activation.returncode != 0:
                raise RuntimeError(
                    "Iris self-check failed before daemon test:\n"
                    + activation.stdout + activation.stderr
                )
            cls._spawn()
            cls.client = IrisClient(port=TEST_PORT, timeout=15.0)
            cls.status = _wait_ready(cls.client, proc=cls.proc)
            assert cls.status["alive"] is True
        except Exception:
            cls._kill()
            cls._restore_receipt()
            cls.tmp.cleanup()
            raise

    @classmethod
    def _spawn(cls):
        cls.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "iris_daemon.py"),
             "--port", str(TEST_PORT),
             "--state-dir", cls.state_dir,
             "--pid-file", cls.pid_file],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=HERE,
        )
        time.sleep(0.5)

    @classmethod
    def _kill(cls):
        if cls.proc:
            if cls.proc.poll() is None:
                cls.proc.send_signal(signal.SIGTERM)
                try:
                    cls.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    cls.proc.kill()
                    cls.proc.wait(timeout=5)
            if cls.proc.stdout:
                cls.proc.stdout.close()
        cls.proc = None

    @classmethod
    def _restore_receipt(cls):
        if cls.original_receipt is None:
            if os.path.exists(cls.receipt_path):
                os.remove(cls.receipt_path)
        else:
            with open(cls.receipt_path, "wb") as handle:
                handle.write(cls.original_receipt)

    @classmethod
    def tearDownClass(cls):
        cls._kill()
        cls._restore_receipt()
        cls.tmp.cleanup()

    def test_01_judge_returns_stalemate_until_narrow_is_wired(self):
        proposal = {
            "kind": "proposal",
            "claim": "DCLM logic and Iris truth must both hold",
            "facts": [],
            "provenance": "DERIVED",
            "claims_fact": False,
            "unity_id": make_unity_id("test:daemon-judge"),
            "action": "LOOK",
            "context": {"schema": "dualis.relay.v1.testnet"},
        }
        response = self.client.call("judge", proposal, CALLER)
        self.assertTrue(response["ok"], response)
        result = response["result"]
        self.assertEqual(result["verdict"], "STALEMATE")
        self.assertEqual(result["narrowing"], "NOT_WIRED")
        self.assertFalse(result["authorization_granted"])
        self.assertFalse(result["write_performed"])
        self.assertTrue(result["receipt_id"].startswith("rcpt:"))
        self.assertNotIn("judges", result)

    def test_02_advice_reads_current_canon(self):
        response = self.client.call("advise", {"topic": "logic truth and writes"}, CALLER)
        self.assertTrue(response["ok"], response)
        result = response["result"]
        self.assertEqual(result["canon_version"], "1.7.3")
        sections = {item["section"] for item in result["canon_sections"]}
        self.assertIn("I", sections)
        self.assertIn("III", sections)
        self.assertIn("not a third judge", result["guidance"])
        self.assertFalse(result["write_performed"])
        self.assertTrue(result["receipt_id"].startswith("rcpt:"))

    def test_03_check_never_promotes_diagnostic_to_pass(self):
        action = {
            "kind": "deceive",
            "claim": "mislead the member",
            "patterns": ["deception"],
            "provenance": "UNKNOWN",
            "claims_fact": True,
            "unity_id": make_unity_id("test:daemon-check"),
            "action": "LOOK",
            "context": {"schema": "dualis.relay.v1.testnet"},
        }
        response = self.client.call("check", action, CALLER)
        self.assertTrue(response["ok"], response)
        result = response["result"]
        self.assertEqual(result["verdict"], "STALEMATE")
        self.assertTrue(result["refused"])
        self.assertFalse(result["authorization_granted"])

    def test_04_unscorable_input_stays_stalemate(self):
        response = self.client.call("check", {}, CALLER)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["verdict"], "STALEMATE")
        self.assertNotEqual(response["result"]["verdict"], "FLAWLESS")

    def test_05_coercive_proposal_is_not_released(self):
        action = {
            "kind": "nudge",
            "claim": "get the member to agree",
            "patterns": ["coerce", "manipulate"],
            "unity_id": make_unity_id("test:daemon-coercion"),
            "action": "LOOK",
            "context": {"schema": "dualis.relay.v1.testnet"},
        }
        response = self.client.call("check", action, CALLER)
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["verdict"], "STALEMATE")
        self.assertTrue(response["result"]["refused"])

    def test_06_unauthorized_caller_refused(self):
        response = self.client.call(
            "judge", {"kind": "proposal", "claim": "x"},
            "uid:testnet:intruder",
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_kind"], "UnauthorizedCaller")

    def test_07_bad_verb_rejected(self):
        response = self.client.call("hypnotize", {}, CALLER)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_kind"], "BadVerb")

    def test_08_iris_seed_issuance_refused(self):
        uid = make_unity_id("test:daemon-seed-1")
        before = self.client.call("status", {}, CALLER)["result"]["state"]
        response = self.client.call("grant_seed", {"unity_id": uid}, CALLER)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_kind"], "IrisLaneViolation")
        after = self.client.call("status", {}, CALLER)["result"]["state"]
        self.assertEqual(after["seeds_granted"], before["seeds_granted"])

    def test_09_seed_record_is_read_only_and_unknown(self):
        uid = make_unity_id("test:daemon-seed-unknown")
        response = self.client.call("seed_record", {"unity_id": uid}, CALLER)
        self.assertTrue(response["ok"], response)
        self.assertIsNone(response["result"]["seed"])

    def test_10_meeting_refuses_without_verified_member_record(self):
        member = make_unity_id("test:daemon-member-unverified")
        with self.assertRaises(MemberUnknown):
            meet_iris_live(member, caller_unity_id=CALLER, port=TEST_PORT)

    def test_11_status_exposes_holds(self):
        response = self.client.call("status", {}, CALLER)
        self.assertTrue(response["ok"], response)
        result = response["result"]
        self.assertTrue(result["alive"])
        self.assertEqual(result["canon"], "1.7.3")
        self.assertEqual(result["legacy_core_version"], "1.5.0")
        self.assertEqual(result["write_authority"], "DCLM_ONLY")
        self.assertEqual(result["narrowing_adapter"], "NOT_WIRED")
        self.assertEqual(result["authorization"], "NOT_GRANTED")
        self.assertEqual(result["daemon"]["port"], TEST_PORT)
        self.assertNotIn("arbiter", result["daemon"])
        self.assertEqual(result["state"]["judgments_logged"], 0)
        self.assertEqual(result["state"]["seeds_granted"], 0)

    def test_98_changed_runtime_module_refuses_new_daemon(self):
        module_path = os.path.join(HERE, "iris_patterns.py")
        with open(module_path, "rb") as handle:
            original = handle.read()
        try:
            with open(module_path, "ab") as handle:
                handle.write(b"\n# deliberate integrity-test mutation\n")
            refused = subprocess.run(
                [sys.executable, os.path.join(HERE, "iris_daemon.py"),
                 "--port", str(TEST_PORT + 1),
                 "--state-dir", os.path.join(self.tmp.name, "tampered-state"),
                 "--pid-file", os.path.join(self.tmp.name, "tampered.pid")],
                capture_output=True, text=True, cwd=HERE, timeout=10,
            )
            self.assertEqual(refused.returncode, 3, refused.stdout + refused.stderr)
            self.assertIn("iris_patterns.py", refused.stdout + refused.stderr)
            self.assertIn("INTEGRITY REFUSED", refused.stdout + refused.stderr)
        finally:
            with open(module_path, "wb") as handle:
                handle.write(original)

    def test_99_restart_preserves_state_without_iris_writes(self):
        before = self.client.call("status", {}, CALLER)["result"]["state"]
        self.assertEqual(before["judgments_logged"], 0)
        self.assertEqual(before["seeds_granted"], 0)
        self._kill()
        time.sleep(1.0)
        self._spawn()
        _wait_ready(self.client, proc=self.proc)
        after = self.client.call("status", {}, CALLER)["result"]["state"]
        self.assertEqual(after["judgments_logged"], 0)
        self.assertEqual(after["seeds_granted"], 0)
        response = self.client.call(
            "judge",
            {
                "kind": "proposal",
                "claim": "the daemon restarted without inventing a Flawless result",
                "facts": [],
                "provenance": "DERIVED",
                "claims_fact": False,
                "unity_id": make_unity_id("test:daemon-after-restart"),
                "action": "LOOK",
                "context": {"schema": "dualis.relay.v1.testnet"},
            },
            CALLER,
        )
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["verdict"], "STALEMATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
