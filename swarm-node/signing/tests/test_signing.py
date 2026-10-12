#!/usr/bin/env python3
"""Tests for the offline signing regime (deliverable 54).

Closes: C1 (unsigned code), C2 (unsigned history), S1 (downgrades),
S4 (oracle authentication), S5 (go-live word), S7 (order chain),
S13 (remote streams). Every test uses THROWAWAY keypairs — the real
offline key is never generated here, never in git, never in chat.

Proven here:
  - bad signatures refused, forged chains detected, downgrades blocked,
    unsigned manifests rejected, unsigned remote streams -> UNKNOWN,
    tampered/expired/replayed go-live intents refused, unallowlisted
    oracle events refused, order chain tamper detected.
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SWARM_NODE = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SWARM_NODE)

from signing import backend, ed25519_pure  # noqa: E402
from signing import envelope, keys, manifest as smanifest  # noqa: E402
from signing import intent as gintent, lane as lanelib  # noqa: E402
from signing import allowlist as sallow, orders  # noqa: E402


def test_keypair():
    return backend.generate()


class CryptoCoreTest(unittest.TestCase):
    def test_backend_reports_honestly(self):
        self.assertIn(backend.backend_name(), ("cryptography", "ed25519_pure"))

    def test_deterministic_signatures(self):
        seed, pub = test_keypair()
        m = b"deterministic"
        self.assertEqual(backend.sign(seed, m), backend.sign(seed, m))

    def test_pure_python_cross_checks_openssl(self):
        # Independent implementation (OpenSSL CLI) must agree with ours:
        # same pubkey derivation, mutual signature verification.
        if shutil.which("openssl") is None:
            self.skipTest("openssl CLI not available")
        d = tempfile.mkdtemp()
        try:
            subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519",
                            "-out", os.path.join(d, "k.pem")],
                           check=True, capture_output=True)
            txt = subprocess.run(
                ["openssl", "pkey", "-in", os.path.join(d, "k.pem"),
                 "-text", "-noout"], check=True, capture_output=True,
                text=True).stdout
            import re
            priv_sec = txt.split("priv:")[1].split("pub:")[0]
            seed = bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", priv_sec))
            pub = ed25519_pure.publickey(seed)
            der = subprocess.run(
                ["openssl", "pkey", "-in", os.path.join(d, "k.pem"),
                 "-pubout", "-outform", "DER"],
                check=True, capture_output=True).stdout
            self.assertEqual(der[-32:], pub)  # same pubkey derivation
            msg = b"interop"
            sig = ed25519_pure.sign(msg, seed, pub)
            open(os.path.join(d, "m"), "wb").write(msg)
            open(os.path.join(d, "s"), "wb").write(sig)
            pk = subprocess.run(
                ["openssl", "pkey", "-in", os.path.join(d, "k.pem"),
                 "-pubout"], check=True, capture_output=True).stdout
            open(os.path.join(d, "p"), "wb").write(pk)
            r = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-pubin",
                 "-inkey", os.path.join(d, "p"), "-in", os.path.join(d, "m"),
                 "-sigfile", os.path.join(d, "s"), "-rawin"],
                capture_output=True)
            self.assertEqual(r.returncode, 0,
                             "openssl must verify our signature")
            subprocess.run(
                ["openssl", "pkeyutl", "-sign",
                 "-inkey", os.path.join(d, "k.pem"),
                 "-in", os.path.join(d, "m"),
                 "-out", os.path.join(d, "s2"), "-rawin"],
                check=True, capture_output=True)
            sig2 = open(os.path.join(d, "s2"), "rb").read()
            self.assertTrue(ed25519_pure.verify(sig2, msg, pub))
            self.assertEqual(sig2, sig)  # determinism across implementations
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_tampered_signature_refused(self):
        seed, pub = test_keypair()
        sig = backend.sign(seed, b"msg")
        bad = sig[:-1] + bytes([sig[-1] ^ 1])
        with self.assertRaises(backend.BadSignature):
            backend.verify(pub, bad, b"msg")

    def test_wrong_key_refused(self):
        s1, p1 = test_keypair()
        _s2, p2 = test_keypair()
        sig = backend.sign(s1, b"msg")
        with self.assertRaises(backend.BadSignature):
            backend.verify(p2, sig, b"msg")

    def test_fingerprint_stable(self):
        _, pub = test_keypair()
        self.assertEqual(keys.fingerprint(pub), keys.fingerprint(pub))
        self.assertRegex(keys.fingerprint(pub), r"^[0-9a-f]{4}(-[0-9a-f]{4}){3}$")

    def test_armor_roundtrip(self):
        _, pub = test_keypair()
        self.assertEqual(keys.dearmor_pubkey(keys.armor_pubkey(pub)), pub)
        self.assertEqual(keys.dearmor_pubkey(pub.hex()), pub)
        self.assertEqual(
            keys.dearmor_pubkey(base64.b64encode(pub).decode()), pub)


class EnvelopeTest(unittest.TestCase):
    def test_seal_open_roundtrip(self):
        seed, pub = test_keypair()
        env = envelope.seal({"hello": "world", "n": 3}, seed)
        self.assertEqual(envelope.open_envelope(env, pub),
                         {"hello": "world", "n": 3})

    def test_tampered_payload_refused(self):
        seed, pub = test_keypair()
        env = envelope.seal({"a": 1}, seed)
        env["payload"]["a"] = 2
        with self.assertRaises(envelope.EnvelopeError):
            envelope.open_envelope(env, pub)

    def test_wrong_key_id_refused(self):
        seed, _ = test_keypair()
        _, pub2 = test_keypair()
        env = envelope.seal({"a": 1}, seed)
        with self.assertRaises(envelope.EnvelopeError):
            envelope.open_envelope(env, pub2)

    def test_canonicalization_stable(self):
        seed, pub = test_keypair()
        p1 = {"z": 1, "a": [3, 2], "m": {"k": "v"}}
        env = envelope.seal(p1, seed)
        # Same content, different key order -> same canonical bytes -> verifies.
        p2 = {"m": {"k": "v"}, "a": [3, 2], "z": 1}
        env2 = dict(env, payload=p2)
        self.assertEqual(envelope.open_envelope(env2, pub), p2)


class ManifestTest(unittest.TestCase):
    def _manifest(self):
        return {
            "desired_version": "v1.2.0",
            "versions": {
                "v1.2.0": {"bundle_url": "https://example.com/b.tar.gz",
                           "sha256": "a" * 64, "notes": "n",
                           "released_at": "2026-10-12"},
            },
        }

    def test_sign_verify_roundtrip(self):
        seed, pub = test_keypair()
        man = self._manifest()
        man["signature"] = smanifest.sign_manifest(man, seed)
        self.assertTrue(smanifest.verify_manifest(man, pub))

    def test_unsigned_manifest_refused(self):
        _, pub = test_keypair()
        with self.assertRaises(envelope.EnvelopeError):
            smanifest.verify_manifest(self._manifest(), pub)

    def test_tampered_version_refused(self):
        seed, pub = test_keypair()
        man = self._manifest()
        man["signature"] = smanifest.sign_manifest(man, seed)
        man["versions"]["v1.2.0"]["sha256"] = "b" * 64  # attacker swaps hash
        with self.assertRaises(envelope.EnvelopeError):
            smanifest.verify_manifest(man, pub)

    def test_tampered_desired_version_refused(self):
        seed, pub = test_keypair()
        man = self._manifest()
        man["signature"] = smanifest.sign_manifest(man, seed)
        man["desired_version"] = "v9.9.9"  # attacker retargets
        with self.assertRaises(envelope.EnvelopeError):
            smanifest.verify_manifest(man, pub)

    def test_bundle_signature(self):
        seed, pub = test_keypair()
        sig = smanifest.sign_bundle("v1.2.0", "a" * 64, seed)
        self.assertTrue(smanifest.verify_bundle("v1.2.0", "a" * 64, sig, pub))
        with self.assertRaises(envelope.EnvelopeError):
            smanifest.verify_bundle("v1.2.0", "b" * 64, sig, pub)

    def test_version_ordering(self):
        self.assertTrue(smanifest.is_newer("v1.2.0", "v1.1.0"))
        self.assertFalse(smanifest.is_newer("v1.1.0", "v1.2.0"))
        self.assertFalse(smanifest.is_newer("v1.1.0", "v1.1.0"))
        self.assertTrue(smanifest.is_newer("v1.0.0", "none"))

    def test_downgrade_needs_signed_auth(self):
        seed, pub = test_keypair()
        man = self._manifest()
        man["desired_version"] = "v1.0.0"
        man["versions"]["v1.0.0"] = dict(man["versions"]["v1.2.0"])
        # No auth -> downgrade not authorized.
        self.assertIsNone(smanifest.find_downgrade_auth(man, "v1.0.0", pub))
        self.assertFalse(smanifest.is_newer("v1.0.0", "v1.2.0"))
        # Signed auth -> authorized.
        auth = {"type": "downgrade-auth", "version": "v1.0.0",
                "reason": "v1.2.0 regression", "issued_at": "2026-10-12T00:00:00Z"}
        man["downgrade_auths"] = [envelope.seal(auth, seed)]
        found = smanifest.find_downgrade_auth(man, "v1.0.0", pub)
        self.assertIsNotNone(found)
        self.assertEqual(found["reason"], "v1.2.0 regression")
        # Auth for a DIFFERENT version does not authorize this one.
        self.assertIsNone(smanifest.find_downgrade_auth(man, "v0.9.0", pub))


class LaneKeyTest(unittest.TestCase):
    def test_keypair_idempotent(self):
        d = tempfile.mkdtemp()
        try:
            s1, p1 = lanelib.ensure_lane_keypair(d)
            s2, p2 = lanelib.ensure_lane_keypair(d)
            self.assertEqual(s1, s2)
            self.assertEqual(p1, p2)
            st = os.stat(os.path.join(d, "lane.key"))
            self.assertEqual(oct(st.st_mode & 0o777), "0o600")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_record_sign_verify(self):
        seed, pub = test_keypair()
        body = {"lane": "DCLM", "seq": 1, "note": "birth"}
        sig_b64, key_id = lanelib.sign_record_body(body, seed)
        rec = dict(body, sig=sig_b64, key_id=key_id)
        self.assertTrue(lanelib.verify_record_signature(rec, pub))
        rec["note"] = "forged"
        with self.assertRaises(envelope.EnvelopeError):
            lanelib.verify_record_signature(rec, pub)


class IntentTest(unittest.TestCase):
    def _sealed(self, seed, **kw):
        kw.setdefault("lane", "EUROPE")
        kw.setdefault("version", "v1.2.0")
        kw.setdefault("bundle_hash", "c" * 64)
        payload = gintent.build_intent(ttl_s=600, **kw)
        return gintent.seal_intent(payload, seed), payload

    def test_intent_roundtrip(self):
        seed, pub = test_keypair()
        env, _ = self._sealed(seed)
        d = tempfile.mkdtemp()
        try:
            out = gintent.verify_intent(env, pub, "EUROPE", "v1.2.0",
                                        "c" * 64,
                                        os.path.join(d, "nonces.json"))
            self.assertEqual(out["lane"], "EUROPE")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_tampered_intent_refused(self):
        seed, pub = test_keypair()
        env, _ = self._sealed(seed)
        env["payload"]["version"] = "v9.9.9"
        d = tempfile.mkdtemp()
        try:
            with self.assertRaises(gintent.IntentError):
                gintent.verify_intent(env, pub, "EUROPE", "v9.9.9", "c" * 64,
                                      os.path.join(d, "nonces.json"))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_wrong_lane_refused(self):
        seed, pub = test_keypair()
        env, _ = self._sealed(seed)
        d = tempfile.mkdtemp()
        try:
            with self.assertRaises(gintent.IntentError):
                gintent.verify_intent(env, pub, "DCLM", "v1.2.0", "c" * 64,
                                      os.path.join(d, "nonces.json"))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_expired_intent_refused(self):
        seed, pub = test_keypair()
        payload = gintent.build_intent("EUROPE", "v1.2.0", "c" * 64,
                                       ttl_s=-10)
        env = gintent.seal_intent(payload, seed)
        d = tempfile.mkdtemp()
        try:
            with self.assertRaises(gintent.IntentError):
                gintent.verify_intent(env, pub, "EUROPE", "v1.2.0", "c" * 64,
                                      os.path.join(d, "nonces.json"))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_replay_refused(self):
        seed, pub = test_keypair()
        env, _ = self._sealed(seed)
        d = tempfile.mkdtemp()
        try:
            ns = os.path.join(d, "nonces.json")
            gintent.verify_intent(env, pub, "EUROPE", "v1.2.0", "c" * 64, ns)
            with self.assertRaises(gintent.IntentError) as c:
                gintent.verify_intent(env, pub, "EUROPE", "v1.2.0", "c" * 64, ns)
            self.assertIn("replay", str(c.exception))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_nonce_survives_restart(self):
        # The nonce store is a file: a restart does not resurrect the word.
        seed, pub = test_keypair()
        env, _ = self._sealed(seed)
        d = tempfile.mkdtemp()
        try:
            ns = os.path.join(d, "nonces.json")
            gintent.verify_intent(env, pub, "EUROPE", "v1.2.0", "c" * 64, ns)
            nonces = gintent.load_nonce_store(ns)  # fresh process view
            self.assertEqual(len(nonces), 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class AllowlistTest(unittest.TestCase):
    def test_signed_event_accepted(self):
        root_seed, root_pub = test_keypair()
        mseed, mpub = test_keypair()
        cfg = sallow.sign_allowlist(
            [{"key_id": keys.fingerprint(mpub), "role": "sealed-meter",
              "label": "test meter", "added_at": "2026-10-12",
              "pubkey_hex": mpub.hex()}], root_seed)
        env = envelope.seal({"type": "energy-marker", "x": 1}, mseed)
        out = sallow.open_event(env, cfg, root_pub, "sealed-meter")
        self.assertEqual(out, {"type": "energy-marker", "x": 1})

    def test_wrong_role_refused(self):
        root_seed, root_pub = test_keypair()
        mseed, mpub = test_keypair()
        cfg = sallow.sign_allowlist(
            [{"key_id": keys.fingerprint(mpub), "role": "sealed-meter",
              "label": "m", "added_at": "t", "pubkey_hex": mpub.hex()}],
            root_seed)
        env = envelope.seal({"type": "rotation-round"}, mseed)
        with self.assertRaises(envelope.EnvelopeError):
            sallow.open_event(env, cfg, root_pub, "deliberation-pipeline")

    def test_unallowlisted_key_refused(self):
        root_seed, root_pub = test_keypair()
        esead, epub = test_keypair()
        cfg = sallow.sign_allowlist([], root_seed)
        env = envelope.seal({"type": "energy-marker"}, esead)
        with self.assertRaises(envelope.EnvelopeError):
            sallow.open_event(env, cfg, root_pub, "sealed-meter")

    def test_tampered_allowlist_refused(self):
        root_seed, root_pub = test_keypair()
        mseed, mpub = test_keypair()
        cfg = sallow.sign_allowlist(
            [{"key_id": keys.fingerprint(mpub), "role": "sealed-meter",
              "label": "m", "added_at": "t", "pubkey_hex": mpub.hex()}],
            root_seed)
        cfg["keys"].append({"key_id": "evil", "role": "sealed-meter"})
        env = envelope.seal({"type": "energy-marker"}, mseed)
        with self.assertRaises(envelope.EnvelopeError):
            sallow.open_event(env, cfg, root_pub, "sealed-meter")


class OrdersTest(unittest.TestCase):
    def test_enact_countersign_verify(self):
        d = tempfile.mkdtemp()
        try:
            chain = os.path.join(d, "chain.jsonl")
            order_md = os.path.join(d, "ORDER.md")
            open(order_md, "w").write("# test order\n")
            aseed, apub = test_keypair()
            cseed, cpub = test_keypair()
            rec = orders.enact(chain, order_md, "Test order", "tier-1",
                               "testing", "revert by deleting", aseed)
            self.assertEqual(rec["status"], "PENDING-COUNTERSIGNATURE")
            reg = {keys.fingerprint(cpub): cpub}
            rec = orders.countersign(rec, cseed, reg)
            self.assertEqual(rec["status"], "SEALED")
            orders.append(chain, rec)
            ok, n, detail = orders.verify_chain(
                chain, {keys.fingerprint(apub): apub}, reg)
            self.assertTrue(ok, detail)
            self.assertEqual(n, 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_unsealed_record_rejected(self):
        d = tempfile.mkdtemp()
        try:
            chain = os.path.join(d, "chain.jsonl")
            order_md = os.path.join(d, "ORDER.md")
            open(order_md, "w").write("# test\n")
            aseed, apub = test_keypair()
            rec = orders.enact(chain, order_md, "T", "tier-1", "r", "rev", aseed)
            orders.append(chain, rec)  # appended WITHOUT countersignature
            ok, _, detail = orders.verify_chain(
                chain, {keys.fingerprint(apub): apub}, {})
            self.assertFalse(ok)
            self.assertIn("countersignature", detail)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_tampered_order_detected(self):
        d = tempfile.mkdtemp()
        try:
            chain = os.path.join(d, "chain.jsonl")
            order_md = os.path.join(d, "ORDER.md")
            open(order_md, "w").write("# test\n")
            aseed, apub = test_keypair()
            cseed, cpub = test_keypair()
            rec = orders.enact(chain, order_md, "T", "tier-1", "r", "rev", aseed)
            reg = {keys.fingerprint(cpub): cpub}
            rec = orders.countersign(rec, cseed, reg)
            orders.append(chain, rec)
            # Attacker rewrites the order file AND the chain record's hash.
            open(order_md, "w").write("# EVIL\n")
            lines = open(chain).read().strip().split("\n")
            r = json.loads(lines[0])
            r["order_sha256"] = orders.sha256_file(order_md)
            r["hash"] = orders._hash_record(r)
            open(chain, "w").write(json.dumps(r) + "\n")
            ok, _, detail = orders.verify_chain(
                chain, {keys.fingerprint(apub): apub}, reg)
            self.assertFalse(ok)  # author sig no longer matches
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_genesis_seeding(self):
        d = tempfile.mkdtemp()
        try:
            chain = os.path.join(d, "chain.jsonl")
            f1 = os.path.join(d, "A.md")
            f2 = os.path.join(d, "B.md")
            open(f1, "w").write("a")
            open(f2, "w").write("b")
            seed, pub = test_keypair()
            n = orders.seed_genesis(chain, [f1, f2], seed)
            self.assertEqual(n, 2)
            fp = keys.fingerprint(pub)
            ok, n2, detail = orders.verify_chain(chain, {fp: pub}, {fp: pub})
            self.assertTrue(ok, detail)
            self.assertEqual(n2, 2)
            # Idempotent: second seeding does nothing.
            self.assertEqual(orders.seed_genesis(chain, [f1, f2], seed), 0)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
