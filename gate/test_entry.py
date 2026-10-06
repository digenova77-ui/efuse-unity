#!/usr/bin/env python3
"""
Tests for the ENTRY GATE (gate/entry.py) — the doorway, not the world.

The full flow, on testnet, in temp state dirs: covenant -> derive ->
request_bind -> confirm_bind -> issue_seed -> gate envelope -> ignition.

The happy path injects a clearly-labeled TEST STUB verifier simulating
the device ceremony (same pattern as test_gate.py). The stub is a
simulation for exercising the ceremony — never presented as real
WebAuthn. The default verifier (UNKNOWN/unwired) is tested too: UNKNOWN
is never PASS.

Run: python3 test_entry.py  (from this directory)
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


entry = _load("unity_entry_under_test", os.path.join(_HERE, "entry.py"))
gate_mod = _load("unity_gate_under_test", os.path.join(_HERE, "gate.py"))


def verified_stub(identity, proof):
    """TEST STUB — simulates the device WebAuthn ceremony for the entry
    exercise only. NOT real WebAuthn. Never claim otherwise."""
    return gate_mod.VerificationResult(
        status="VERIFIED", detail="test stub: simulated device ceremony")


def make_proof(seed_hex="aabbccddeeff00112233445566778899"):
    """A testnet ceremony-stub proof. EXPLICITLY a stub."""
    return {
        "kind": "testnet-stub",
        "testnet_ceremony": True,
        "stub_seed": seed_hex,
    }


class EntryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="unity-entry-test-")
        self.gate = gate_mod.UnityGate(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        entry._SEEDERS.pop(self.tmp, None)

    def _enter(self, **kw):
        args = {"covenant_accepted": True, "proof": make_proof(),
                "verifier": verified_stub, "gate": self.gate}
        args.update(kw)
        return entry.perform_entry(**args)

    # 1. The full happy path --------------------------------------------
    def test_happy_path(self):
        res = self._enter()
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["schema"], "unity.gate.entry.v1.testnet")
        self.assertTrue(res["testnet"])

        identity = res["identity"]
        self.assertTrue(identity.startswith("unity:testnet:"))
        self.assertEqual(len(identity), len("unity:testnet:") + 16)
        self.assertEqual(res["obfuscated_display"], identity[14:])

        # the covenant traveled with the entry
        self.assertTrue(res["covenant"]["accepted"])
        self.assertEqual(res["covenant"]["version"], "covenant.v1")
        self.assertEqual(len(res["covenant"]["lines"]), 3)

        # bind: DCLM performed, server-side
        self.assertEqual(res["bind"]["state"], "BOUND")
        self.assertEqual(self.gate.status(identity), "BOUND")

        # seed: one, free
        self.assertEqual(res["seed"]["price"], 0.0)
        self.assertEqual(res["seed"]["cost"], 0.0)
        self.assertTrue(res["seed"]["seed_id"])

        # envelope authorizes metered intent
        self.assertEqual(res["envelope"]["type"], "GATE")

        # ignition: signed, receipted
        self.assertTrue(res["ignition"]["ignition_id"])
        self.assertTrue(res["ignition"]["signature"])
        self.assertEqual(len(res["receipts"]), 3)

        # the ignition log holds the spark
        found = entry._find_ignition(self.tmp, identity)
        self.assertIsNotNone(found)
        receipt = found.get("receipt", found)
        self.assertEqual(receipt["type"], "IGNITION")
        self.assertTrue(receipt["ceremony"]["testnet_ceremony_stub"])

    # 2. No covenant, no bind --------------------------------------------
    def test_covenant_not_accepted(self):
        for no in (False, None, 0, ""):
            res = self._enter(covenant_accepted=no)
            self.assertFalse(res["ok"])
            self.assertEqual(res["refused"]["reason"],
                             "COVENANT_NOT_ACCEPTED")
            self.assertEqual(res["refused"]["at_step"], "covenant")
        # nothing bound, nothing seeded, no ignition log
        self.assertEqual(os.listdir(self.tmp), [])

    # 3. No credential material -> no identity -> no entry ----------------
    def test_no_credential_material(self):
        for bad in ({}, {"kind": "testnet-stub"},
                    {"kind": "webauthn", "credential_id": ""},
                    {"kind": "mystery", "stub_seed": "aa"},
                    "not-a-dict"):
            res = self._enter(proof=bad)
            self.assertFalse(res["ok"], bad)
            self.assertEqual(res["refused"]["reason"],
                             "NO_CREDENTIAL_MATERIAL")
        self.assertEqual(self.gate.status(
            "unity:testnet:0000000000000000"), "UNBOUND")

    # 4. UNKNOWN verifier is never PASS -----------------------------------
    def test_unknown_verifier_refuses(self):
        res = entry.perform_entry(
            covenant_accepted=True, proof=make_proof(),
            gate=self.gate)  # default verifier: UNKNOWN/unwired
        self.assertFalse(res["ok"])
        self.assertEqual(res["refused"]["reason"], "PROOF_UNKNOWN")
        self.assertEqual(res["refused"]["at_step"], "confirm_bind")
        # the ceremony started (BINDING) but nothing was granted
        identity = entry.derive_entry_identity(make_proof())
        self.assertEqual(self.gate.status(identity), "BINDING")
        self.assertIsNone(entry._find_ignition(self.tmp, identity))

    # 5. Idempotent replay: no duplicate seed, no duplicate spark ---------
    def test_idempotent_replay(self):
        first = self._enter()
        self.assertTrue(first["ok"])
        identity = first["identity"]
        with open(os.path.join(self.tmp, "ignitions.jsonl")) as fh:
            lines_before = len(fh.readlines())

        second = self._enter()
        self.assertTrue(second["ok"])
        self.assertTrue(second["already"])
        self.assertEqual(second["identity"], identity)

        with open(os.path.join(self.tmp, "ignitions.jsonl")) as fh:
            self.assertEqual(len(fh.readlines()), lines_before)

        seeder = entry._SEEDERS[self.tmp]
        self.assertEqual(seeder.seeds_issued(), 1)
        self.assertTrue(seeder.has_seed(identity))

    # 6. Resume: BINDING + valid proof completes --------------------------
    def test_resume_from_binding(self):
        refused = entry.perform_entry(
            covenant_accepted=True, proof=make_proof(), gate=self.gate)
        self.assertFalse(refused["ok"])  # UNKNOWN verifier
        done = self._enter()             # stub verifier resumes
        self.assertTrue(done["ok"])
        self.assertFalse(done["already"])
        self.assertEqual(done["bind"]["transition"], "BOUND")
        self.assertEqual(done["seed"]["price"], 0.0)

    # 7. Derivation is DCLM-side and deterministic -------------------------
    def test_derivation(self):
        a = entry.derive_entry_identity(make_proof("aa"))
        b = entry.derive_entry_identity(make_proof("aa"))
        c = entry.derive_entry_identity(make_proof("bb"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        for ident in (a, c):
            self.assertTrue(ident.startswith("unity:testnet:"))
            # the client can pick stub bytes but can never pick its ID:
            # the ID is the hash, derived server-side
            self.assertNotIn("aa", ident)

    # 8. Refusals are envelopes, never bare exceptions --------------------
    def test_refusal_shape(self):
        res = self._enter(covenant_accepted=False)
        self.assertIn("schema", res)
        self.assertIn("refused", res)
        self.assertIn("reason", res["refused"])
        self.assertIn("detail", res["refused"])
        self.assertIn("at_step", res["refused"])
        self.assertTrue(res["testnet"])

    # 9. Ignition echoes the genesis --------------------------------------
    def test_ignition_echoes_genesis(self):
        res = self._enter()
        found = entry._find_ignition(self.tmp, res["identity"])
        receipt = found.get("receipt", found)
        self.assertIn("genesis", receipt["echoes"])
        self.assertEqual(receipt["bind_receipt_id"],
                         res["bind"]["receipt_id"])
        self.assertEqual(receipt["seed_id"], res["seed"]["seed_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
