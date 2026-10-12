#!/usr/bin/env python3
"""Integration tests: the signing regime WIRING (not just the crypto).

Proves, end to end with throwaway keys:
  - pull-agent REFUSES unsigned/tampered manifests (C1) and downgrades
    without signed authorization (S1); ACCEPTS signed manifests.
  - health.py reports UNKNOWN for unsigned/planted remote streams (S13)
    and UP for properly signed ones; tampered local streams -> DOWN.
  - pricing oracles accept signed events from allowlisted keys and refuse
    wrong-role / unknown keys (S4).
"""
import json
import os
import sys
import tempfile
import shutil
import unittest
from datetime import datetime, timezone, timedelta

SWARM_NODE = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SWARM_NODE)
sys.path.insert(0, os.path.join(SWARM_NODE, "cluster"))
sys.path.insert(0, os.path.join(SWARM_NODE, "x402-rail"))

from signing import backend, envelope, keys  # noqa: E402
from signing import manifest as smanifest, lane as lanelib  # noqa: E402
from signing import allowlist as sallow  # noqa: E402


def _load_pull_agent():
    import importlib.util
    path = os.path.join(SWARM_NODE, "cluster", "pull-agent.py")
    spec = importlib.util.spec_from_file_location("pull_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pa = _load_pull_agent()

def _load_pricing():
    # Load rail/pricing.py WITHOUT importing the rail package __init__
    # (which needs eth_account, only present in the x402 venv). pricing.py
    # itself is stdlib-only plus .economy.
    # Load rail/pricing.py WITHOUT importing the rail package __init__
    # (which needs eth_account, only present in the x402 venv). pricing.py
    # itself is stdlib-only plus .economy.
    import importlib.util, types
    rail_dir = os.path.join(SWARM_NODE, "x402-rail", "rail")
    pkg = sys.modules.get("rail")
    if pkg is None or not hasattr(pkg, "__path__"):
        pkg = types.ModuleType("rail")
        pkg.__path__ = [rail_dir]
        sys.modules["rail"] = pkg
    for name in ("rail.economy", "rail.pricing"):
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                name, os.path.join(rail_dir, name.split(".")[1] + ".py"))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod  # register BEFORE exec: dataclasses
            spec.loader.exec_module(mod)
    return sys.modules["rail.pricing"]


_pricing = _load_pricing()


def _load_health():
    import importlib.util as _ilu
    path = os.path.join(SWARM_NODE, "cluster", "health.py")
    spec = _ilu.spec_from_file_location("healthmod", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


healthmod = _load_health()


def utcnow_minus(seconds=10):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class PullAgentSigningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.etc = os.path.join(self.tmp, "etc")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.etc, exist_ok=True)
        os.makedirs(self.state, exist_ok=True)
        # Patch module constants to the fixture.
        self._vf, pa.VERSION_FILE = pa.VERSION_FILE, os.path.join(
            self.etc, "version")
        self._sd, pa.STAGE_DIR = pa.STAGE_DIR, os.path.join(self.tmp, "stage")
        self._dp, pa.DAVID_PUBKEY_FILE = pa.DAVID_PUBKEY_FILE, os.path.join(
            self.etc, "david-pubkey")
        # Throwaway offline root key, pinned.
        self.seed, self.pub = backend.generate()
        with open(pa.DAVID_PUBKEY_FILE, "w") as f:
            f.write(self.pub.hex() + "\n")
        with open(pa.VERSION_FILE, "w") as f:
            f.write("v1.1.0\n")
        # attest() shells out to node/attest.py — point it at fixture dirs.
        os.environ["DUALIS_ETC_DIR"] = self.etc
        os.environ["DUALIS_STATE_DIR"] = self.state
        os.environ["DUALIS_LANE"] = "DCLM"

    def tearDown(self):
        pa.VERSION_FILE, pa.STAGE_DIR, pa.DAVID_PUBKEY_FILE = \
            self._vf, self._sd, self._dp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _manifest_url(self, manifest):
        p = os.path.join(self.tmp, "manifest.json")
        write_json(p, manifest)
        return "file://" + p

    def _signed(self, manifest):
        manifest["signature"] = smanifest.sign_manifest(manifest, self.seed)
        return manifest

    def _base_manifest(self, want):
        return {"desired_version": want,
                "versions": {want: {"bundle_url": "file:///nonexistent.tar.gz",
                                    "sha256": "d" * 64}}}

    def test_unsigned_manifest_refused(self):
        url = self._manifest_url(self._base_manifest("v1.2.0"))
        rep = pa.poll_once(url)
        self.assertEqual(rep["poll"], "refused")
        self.assertIn("signature", rep["reason"])

    def test_tampered_manifest_refused(self):
        man = self._signed(self._base_manifest("v1.2.0"))
        man["desired_version"] = "v9.9.9"  # attacker retargets after signing
        rep = pa.poll_once(self._manifest_url(man))
        self.assertEqual(rep["poll"], "refused")

    def test_wrong_key_manifest_refused(self):
        other_seed, _ = backend.generate()
        man = self._base_manifest("v1.2.0")
        man["signature"] = smanifest.sign_manifest(man, other_seed)
        rep = pa.poll_once(self._manifest_url(man))
        self.assertEqual(rep["poll"], "refused")

    def test_signed_manifest_accepted(self):
        # desired == current: accepted (up-to-date), no download attempted.
        man = self._signed(self._base_manifest("v1.1.0"))
        rep = pa.poll_once(self._manifest_url(man))
        self.assertEqual(rep["poll"], "up-to-date")

    def test_downgrade_without_auth_refused(self):
        man = self._signed(self._base_manifest("v1.0.0"))
        rep = pa.poll_once(self._manifest_url(man))
        self.assertEqual(rep["poll"], "refused")
        self.assertIn("downgrade", rep["reason"])

    def test_downgrade_with_signed_auth_proceeds(self):
        man = self._signed(self._base_manifest("v1.0.0"))
        auth = {"type": "downgrade-auth", "version": "v1.0.0",
                "reason": "test rollback", "issued_at": utcnow_minus(60)}
        man["downgrade_auths"] = [envelope.seal(auth, self.seed)]
        # Re-sign: the descriptor covers downgrade_auths.
        man["signature"] = smanifest.sign_manifest(man, self.seed)
        rep = pa.poll_once(self._manifest_url(man))
        # Passes the downgrade gate; then fails honestly on the fake download.
        self.assertEqual(rep["poll"], "failed")
        self.assertEqual(rep["reason"], "download failed")

    def test_pre_ceremony_warns_but_runs(self):
        os.remove(pa.DAVID_PUBKEY_FILE)  # no pinned key: pre-ceremony
        man = self._base_manifest("v1.1.0")  # unsigned, desired == current
        rep = pa.poll_once(self._manifest_url(man))
        self.assertEqual(rep["poll"], "up-to-date")  # transitional behavior


def signed_tick(seed, seconds_ago=10):
    tick = {"node_id": "n1", "tick": 1, "at_utc": utcnow_minus(seconds_ago)}
    sig_b64, key_id = lanelib.sign_record_body(tick, seed)
    tick["sig"] = sig_b64
    tick["key_id"] = key_id
    return tick


def signed_chain(seed, pub, n=2):
    recs = []
    prev = "GENESIS"
    for i in range(1, n + 1):
        body = {"lane": "EUROPE", "seq": i, "prev_hash": prev,
                "at_utc": utcnow_minus(10)}
        if i == 1:
            body["lane_pubkey"] = pub.hex()
        sig_b64, key_id = lanelib.sign_record_body(body, seed)
        body["sig"] = sig_b64
        body["key_id"] = key_id
        import hashlib
        body["hash"] = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        prev = body["hash"]
        recs.append(body)
    return recs


def write_jsonl(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")


class HealthSigningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.seed, self.pub = backend.generate()
        self.keys_dir = os.path.join(self.tmp, "lane-keys")
        os.makedirs(self.keys_dir, exist_ok=True)
        with open(os.path.join(self.keys_dir, "EUROPE.pubkey"), "w") as f:
            f.write(self.pub.hex() + "\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _remote(self, ticks, chain):
        d = os.path.join(self.tmp, "remote", "EUROPE")
        os.makedirs(d, exist_ok=True)
        write_jsonl(os.path.join(d, "heartbeat.jsonl"), ticks)
        write_jsonl(os.path.join(d, "attestations.jsonl"), chain)
        return d

    def test_signed_remote_stream_is_up(self):
        d = self._remote([signed_tick(self.seed)],
                         signed_chain(self.seed, self.pub))
        r = healthmod.assess_lane("EUROPE", d, 300, lane_pubkey=self.pub,
                                  remote=True)
        self.assertEqual(r["state"], "UP")
        self.assertIn("signed", r["reason"])

    def test_planted_heartbeat_is_unknown(self):
        # Attacker plants a fresh but UNSIGNED heartbeat.jsonl for the lane.
        d = self._remote(
            [{"node_id": "n1", "tick": 1, "at_utc": utcnow_minus(5)}],
            signed_chain(self.seed, self.pub))
        r = healthmod.assess_lane("EUROPE", d, 300, lane_pubkey=self.pub,
                                  remote=True)
        self.assertEqual(r["state"], "UNKNOWN")
        self.assertIn("untrusted", r["reason"])

    def test_forged_attestation_is_unknown(self):
        chain = signed_chain(self.seed, self.pub)
        chain[1]["note"] = "forged"
        import hashlib
        body = {k: v for k, v in chain[1].items() if k != "hash"}
        chain[1]["hash"] = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        d = self._remote([signed_tick(self.seed)], chain)
        r = healthmod.assess_lane("EUROPE", d, 300, lane_pubkey=self.pub,
                                  remote=True)
        self.assertEqual(r["state"], "UNKNOWN")
        self.assertIn("untrusted", r["reason"])

    def test_unpinned_lane_key_is_unknown(self):
        d = self._remote([signed_tick(self.seed)],
                         signed_chain(self.seed, self.pub))
        r = healthmod.assess_lane("EUROPE", d, 300, lane_pubkey=None,
                                  remote=True)
        self.assertEqual(r["state"], "UNKNOWN")
        self.assertIn("not pinned", r["reason"])

    def test_tampered_local_stream_is_down(self):
        # Local disk is ours: bad signatures mean tamper -> DOWN, not UNKNOWN.
        d = os.path.join(self.tmp, "local")
        os.makedirs(d, exist_ok=True)
        chain = signed_chain(self.seed, self.pub)
        chain[0]["sig"] = base64_b64tamper(chain[0]["sig"])
        write_jsonl(os.path.join(d, "heartbeat.jsonl"),
                    [signed_tick(self.seed)])
        write_jsonl(os.path.join(d, "attestations.jsonl"), chain)
        r = healthmod.assess_lane("EUROPE", d, 300, lane_pubkey=self.pub,
                                  remote=False)
        self.assertEqual(r["state"], "DOWN")
        self.assertIn("tampered", r["reason"])

    def test_snapshot_wires_lane_keys_dir(self):
        d = self._remote([signed_tick(self.seed)],
                         signed_chain(self.seed, self.pub))
        snap = healthmod.snapshot(
            {"EUROPE": {"local": False}}, state_dir=self.tmp,
            remote_dir=os.path.join(self.tmp, "remote"),
            lane_keys_dir=self.keys_dir)
        self.assertEqual(snap["EUROPE"]["state"], "UP")


def base64_b64tamper(s):
    import base64 as b64
    raw = bytearray(b64.b64decode(s))
    raw[0] ^= 1
    return b64.b64encode(bytes(raw)).decode()


class PricingSignedEventsTest(unittest.TestCase):
    def setUp(self):
        EnergyIndex, RotationLedger = _pricing.EnergyIndex, _pricing.RotationLedger
        self.EnergyIndex, self.RotationLedger = EnergyIndex, RotationLedger
        self.root_seed, self.root_pub = backend.generate()
        self.meter_seed, self.meter_pub = backend.generate()
        self.pipe_seed, self.pipe_pub = backend.generate()
        self.cfg = sallow.sign_allowlist([
            {"key_id": keys.fingerprint(self.meter_pub), "role": "sealed-meter",
             "label": "test meter", "added_at": "t",
             "pubkey_hex": self.meter_pub.hex()},
            {"key_id": keys.fingerprint(self.pipe_pub),
             "role": "deliberation-pipeline", "label": "test pipe",
             "added_at": "t", "pubkey_hex": self.pipe_pub.hex()},
        ], self.root_seed)

    def _marker_env(self, seed, **kw):
        kw.setdefault("type", "energy-marker")
        kw.setdefault("lane", "DCLM")
        kw.setdefault("joules_per_unit", 1.5)
        kw.setdefault("measured_at", utcnow_minus(60))
        kw.setdefault("source", "test-meter")
        kw.setdefault("grade", "REAL")
        return envelope.seal(kw, seed)

    def test_signed_marker_accepted(self):
        idx = self.EnergyIndex(reference_joules_per_unit=1.0)
        env = self._marker_env(self.meter_seed, calibrated=True)
        m = idx.update_marker_signed(env, self.cfg, self.root_pub)
        self.assertEqual(m.lane, "DCLM")
        self.assertEqual(m.grade, "REAL")

    def test_self_reported_real_downgraded(self):
        # S3: a sealed meter's signature authenticates SOURCE, not grade.
        # REAL without calibrated provenance -> REPORTED.
        idx = self.EnergyIndex(reference_joules_per_unit=1.0)
        env = self._marker_env(self.meter_seed)  # grade REAL, no calibrated
        m = idx.update_marker_signed(env, self.cfg, self.root_pub)
        self.assertEqual(m.grade, "REPORTED")

    def test_wrong_role_refused(self):
        idx = self.EnergyIndex(reference_joules_per_unit=1.0)
        env = self._marker_env(self.pipe_seed, calibrated=True)
        with self.assertRaises(envelope.EnvelopeError):
            idx.update_marker_signed(env, self.cfg, self.root_pub)

    def test_unknown_key_refused(self):
        idx = self.EnergyIndex(reference_joules_per_unit=1.0)
        evil_seed, _ = backend.generate()
        env = self._marker_env(evil_seed, calibrated=True)
        with self.assertRaises(envelope.EnvelopeError):
            idx.update_marker_signed(env, self.cfg, self.root_pub)

    def test_signed_round_accepted(self):
        ledger = self.RotationLedger()
        env = envelope.seal({"type": "rotation-round", "decision_id": "d1",
                             "contributor": "tester",
                             "premium_quoted_micros": 1000,
                             "energy_mult": 1.0}, self.pipe_seed)
        n = ledger.open_round_signed(env, self.cfg, self.root_pub)
        self.assertEqual(n, 1)

    def test_meter_cannot_open_rounds(self):
        ledger = self.RotationLedger()
        env = envelope.seal({"type": "rotation-round", "decision_id": "d1",
                             "contributor": "tester",
                             "premium_quoted_micros": 1000}, self.meter_seed)
        with self.assertRaises(envelope.EnvelopeError):
            ledger.open_round_signed(env, self.cfg, self.root_pub)


if __name__ == "__main__":
    unittest.main(verbosity=2)
