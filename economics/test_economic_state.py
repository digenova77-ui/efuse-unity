"""
Tests for the unified EconomicState (~/workspace/unity-world/economics/).

All must pass. Testnet only.

Laws under test:
  * EVERY field carries a valid provenance label (REPORTED/VERIFIED/
    MODELED/DERIVED/UNKNOWN).
  * UNKNOWN never PASS and never pays. MODELED informs but never pays.
  * The signed envelope verifies; tampering breaks verification.
  * The relay bundle is well-formed, manifest-hashed, idempotent, and
    fail-closed (mainnet schema rejected, tampered hash rejected,
    non-testnet identity rejected).
  * Every mutation is receipted.
"""
import copy
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from economic_state import (  # noqa: E402
    PROVENANCE_LABELS,
    RELAY_SCHEMA,
    TESTNET_IDENTITY_PREFIX,
    compute_economic_state,
    sign_economic_state,
    verify_economic_envelope,
    testnet_unity_id,
    to_economic_relay_bundle,
    validate_economic_relay_bundle,
    dedupe_bundles,
    worker_modules_present,
    _label,
)
import economic_state as _econ_mod  # noqa: E402

_METER_AVAILABLE = _econ_mod._W1_METER is not None

SAMPLE_PRICES = [
    {"decision_id": "rtev-edu",
     "price": 1273.5,
     "provenance": "REPORTED",
     "source_label": "REAL",
     "source": "Drive paperwork (RTE-EDU)"},
    {"decision_id": "abbvie-v1",
     "price": 56160,
     "provenance": "REPORTED",
     "source_label": "REPORTED-via-secondary",
     "source": "corp-helpers-abbvie-improvement-map"},
    {"decision_id": "mystery-v9",
     "price": None,
     "provenance": "UNKNOWN",
     "source": None},
    {"decision_id": "guess-v1",
     "price": 42.0,
     "provenance": "MODELED",
     "source_label": "MODELED",
     "source": "analyst estimate"},
]

SAMPLE_EMISSIONS = [
    {"pool": "human", "emitted": 120.5, "held": 3.0,
     "provenance": "REPORTED", "merit_receipts": ["r1"]},
    {"pool": "machine", "emitted": None, "held": None,
     "provenance": "UNKNOWN"},
]

SAMPLE_WALLETS = [
    {"unity_id": "unity:testnet:aaaa", "balance": 10.0, "merit": 5,
     "honor": 0, "provenance": "VERIFIED"},
    {"unity_id": "unity:testnet:bbbb", "balance": 10.0, "merit": 0,
     "honor": 0, "provenance": "UNKNOWN"},
    {"unity_id": "unity:testnet:cccc", "balance": 10.0, "merit": 0,
     "honor": 0, "provenance": "MODELED"},
    {"unity_id": "unity:testnet:dddd", "balance": -3.0, "merit": 0,
     "honor": 0, "provenance": "VERIFIED"},
]

SAMPLE_DONATIONS = [
    {"donor_unity_id": "unity:testnet:aaaa", "amount": 5.0,
     "kind": "efuse", "provenance": "REPORTED", "donation_receipt": "d1"},
    {"donor_unity_id": "unity:testnet:bbbb", "amount": 100.0,
     "kind": "fiat", "provenance": "REPORTED", "donation_receipt": "d2"},
]


def sample_state():
    return compute_economic_state(
        prices=SAMPLE_PRICES,
        emissions=SAMPLE_EMISSIONS,
        wallets=SAMPLE_WALLETS,
        donations=SAMPLE_DONATIONS,
    )


class TestProvenance(unittest.TestCase):
    def _collect(self, node, found):
        if isinstance(node, dict):
            self.assertIn("provenance", node,
                          f"dict missing provenance: {str(node)[:80]}")
            self.assertIn(node["provenance"], PROVENANCE_LABELS)
            found.append(node["provenance"])
            for v in node.values():
                self._collect(v, found)
        elif isinstance(node, list):
            for v in node:
                self._collect(v, found)

    def test_every_field_carries_valid_provenance(self):
        state = sample_state()
        labels = []
        self._collect(state, labels)
        self.assertTrue(labels, "no provenance labels found at all")

    def test_four_sections_present(self):
        state = sample_state()
        for field in ("price_index", "emission_state", "wallet_states",
                      "donation_lock"):
            self.assertIn(field, state)

    def test_default_state_is_all_unknown(self):
        state = compute_economic_state()
        self.assertEqual(state["price_index"]["provenance"], "DERIVED")
        self.assertEqual(
            state["emission_state"]["human_pool"]["emitted"], None)
        self.assertEqual(
            state["emission_state"]["human_pool"]["provenance"], "UNKNOWN")
        self.assertEqual(state["donation_lock"]["address"]["value"],
                         "UNKNOWN")
        self.assertEqual(state["donation_lock"]["address"]["provenance"],
                         "UNKNOWN")

    def test_invalid_input_provenance_downgrades_to_unknown(self):
        state = compute_economic_state(
            prices=[{"decision_id": "x", "price": 1.0,
                     "provenance": "DEFINITELY_REAL"}],
        )
        self.assertEqual(state["price_index"]["x"]["provenance"], "UNKNOWN")
        self.assertFalse(state["price_index"]["x"]["pays"])

    def test_missing_input_provenance_becomes_unknown(self):
        state = compute_economic_state(
            wallets=[{"unity_id": "unity:testnet:zzz", "balance": 99.0}],
        )
        w = state["wallet_states"]["unity:testnet:zzz"]
        self.assertEqual(w["provenance"], "UNKNOWN")
        self.assertFalse(w["payable"])

    def test_label_stamp_covers_unlabeled_dicts(self):
        node = {"a": {"b": 1}, "list": [{"c": 2}]}
        _label(node)
        self.assertEqual(node["provenance"], "UNKNOWN")
        self.assertEqual(node["a"]["provenance"], "UNKNOWN")
        self.assertEqual(node["list"][0]["provenance"], "UNKNOWN")


class TestUnknownNeverPays(unittest.TestCase):
    def test_unknown_balance_never_pays(self):
        state = sample_state()
        w = state["wallet_states"]["unity:testnet:bbbb"]
        self.assertEqual(w["provenance"], "UNKNOWN")
        self.assertFalse(w["payable"])

    def test_verified_positive_balance_pays(self):
        state = sample_state()
        w = state["wallet_states"]["unity:testnet:aaaa"]
        self.assertTrue(w["payable"])

    def test_negative_verified_balance_does_not_pay(self):
        state = sample_state()
        w = state["wallet_states"]["unity:testnet:dddd"]
        self.assertFalse(w["payable"])

    def test_modeled_balance_never_pays(self):
        # MODELED informs; it does not authorize payment.
        state = sample_state()
        w = state["wallet_states"]["unity:testnet:cccc"]
        self.assertEqual(w["provenance"], "MODELED")
        self.assertFalse(w["payable"])

    def test_unknown_price_never_pays(self):
        state = sample_state()
        p = state["price_index"]["mystery-v9"]
        self.assertEqual(p["provenance"], "UNKNOWN")
        self.assertFalse(p["pays"])

    def test_modeled_price_never_pays(self):
        state = sample_state()
        p = state["price_index"]["guess-v1"]
        self.assertEqual(p["provenance"], "MODELED")
        self.assertFalse(p["pays"])

    def test_reported_price_pays(self):
        state = sample_state()
        p = state["price_index"]["rtev-edu"]
        self.assertTrue(p["pays"])

    def test_source_labels_preserved_verbatim(self):
        # PRICES.md's finer labels (REAL, REPORTED-via-secondary, ...) are
        # kept in source_label — never laundered into the 5-label system.
        state = sample_state()
        self.assertEqual(state["price_index"]["rtev-edu"]["source_label"],
                         "REAL")
        self.assertEqual(
            state["price_index"]["abbvie-v1"]["source_label"],
            "REPORTED-via-secondary")


class TestEmissionState(unittest.TestCase):
    def test_pools_carry_50m_caps(self):
        state = sample_state()
        self.assertEqual(state["emission_state"]["human_pool"]
                         ["lifetime_cap"], 50_000_000)
        self.assertEqual(state["emission_state"]["machine_pool"]
                         ["lifetime_cap"], 50_000_000)
        self.assertEqual(state["emission_state"]["mesh_clearing"]
                         ["emission_authority"], 0)

    def test_remaining_is_derived_from_emitted(self):
        state = sample_state()
        human = state["emission_state"]["human_pool"]
        self.assertEqual(human["emitted"], 120.5)
        self.assertAlmostEqual(human["remaining"], 50_000_000 - 120.5)
        machine = state["emission_state"]["machine_pool"]
        self.assertIsNone(machine["emitted"])
        self.assertIsNone(machine["remaining"])

    def test_peg_ratio_is_unknown_held_for_david(self):
        state = sample_state()
        peg = state["emission_state"]["peg_ratio_e_per_efuse"]
        self.assertIsNone(peg["value"])
        self.assertEqual(peg["provenance"], "UNKNOWN")

    def test_emission_mutations_receipted(self):
        state = sample_state()
        receipts = state["emission_state"]["epoch_receipts"]
        self.assertEqual(len(receipts), 1)  # only the human pool had emitted
        r = receipts[0]
        self.assertEqual(r["movement"], "emission")
        self.assertEqual(r["pool"], "human")
        self.assertEqual(len(r["receipt_id"]), 64)


class TestDonationLock(unittest.TestCase):
    def test_donations_receipted(self):
        state = sample_state()
        inflow = state["donation_lock"]["inflow"]
        self.assertEqual(len(inflow), 2)
        for entry in inflow:
            self.assertEqual(len(entry["receipt_id"]), 64)
            self.assertEqual(entry["accrues"], "HONOR")
            self.assertEqual(entry["never_accrues"], "MERIT")

    def test_donations_accrue_honor_not_merit(self):
        state = sample_state()
        honor = state["donation_lock"]["honor_accrued"]["per_unity_id"]
        self.assertEqual(honor["unity:testnet:aaaa"], 1)
        self.assertEqual(honor["unity:testnet:bbbb"], 1)

    def test_donor_exclusion_rule_present(self):
        state = sample_state()
        rule = state["donation_lock"]["donor_exclusion"]["rule"]
        self.assertIn("never re-emitted", rule)

    def test_address_never_invented(self):
        state = sample_state()
        self.assertEqual(state["donation_lock"]["address"]["value"],
                         "UNKNOWN")


class TestSigning(unittest.TestCase):
    def test_sign_verify_round_trip(self):
        state = sample_state()
        envelope = sign_economic_state(state)
        self.assertTrue(verify_economic_envelope(envelope))
        self.assertEqual(envelope["algorithm"], "Ed25519")
        self.assertEqual(envelope["key_id"], "unity-world-test")
        self.assertEqual(envelope["provenance"], "VERIFIED")
        self.assertEqual(len(envelope["canonical_sha256"]), 64)

    def test_tampered_state_fails_verification(self):
        state = sample_state()
        envelope = sign_economic_state(state)
        tampered = copy.deepcopy(envelope)
        tampered["state"]["wallet_states"]["unity:testnet:aaaa"]["balance"] = 99999.0
        self.assertFalse(verify_economic_envelope(tampered))

    def test_tampered_signature_fails_verification(self):
        state = sample_state()
        envelope = sign_economic_state(state)
        tampered = copy.deepcopy(envelope)
        sig = tampered["signature"]
        tampered["signature"] = ("A" if sig[0] != "A" else "B") + sig[1:]
        self.assertFalse(verify_economic_envelope(tampered))

    def test_verify_never_raises_on_garbage(self):
        self.assertFalse(verify_economic_envelope({}))
        self.assertFalse(verify_economic_envelope({"state": {}}))


class TestRelayIntegration(unittest.TestCase):
    def test_unity_id_is_testnet_bound(self):
        uid = testnet_unity_id()
        self.assertTrue(uid.startswith(TESTNET_IDENTITY_PREFIX))
        self.assertEqual(len(uid), len(TESTNET_IDENTITY_PREFIX) + 64)

    def test_bundle_is_well_formed(self):
        envelope = sign_economic_state(sample_state())
        bundle = to_economic_relay_bundle(
            envelope, kind="VERDICT", reason="epoch economic verdict")
        self.assertEqual(bundle["schema"], RELAY_SCHEMA)
        self.assertEqual(bundle["kind"], "VERDICT")
        self.assertEqual(len(bundle["manifest_hash"]), 64)
        self.assertTrue(bundle["unity_id"].startswith(TESTNET_IDENTITY_PREFIX))
        parsed = validate_economic_relay_bundle(bundle)
        self.assertTrue(parsed["ok"])

    def test_manifest_hash_is_content_determined(self):
        envelope = sign_economic_state(sample_state())
        b1 = to_economic_relay_bundle(envelope, kind="VERDICT",
                                      relayed_at="2026-10-06T00:00:00Z",
                                      reason="r")
        b2 = to_economic_relay_bundle(envelope, kind="VERDICT",
                                      relayed_at="2026-10-06T00:00:00Z",
                                      reason="r")
        self.assertEqual(b1["manifest_hash"], b2["manifest_hash"])
        # Any content change changes the manifest hash.
        b3 = to_economic_relay_bundle(envelope, kind="EVIDENCE",
                                      relayed_at="2026-10-06T00:00:00Z",
                                      reason="r")
        self.assertNotEqual(b1["manifest_hash"], b3["manifest_hash"])

    def test_verdict_requires_signed_envelope(self):
        with self.assertRaises(ValueError):
            to_economic_relay_bundle({"state": sample_state()},
                                     kind="VERDICT", reason="r")

    def test_unknown_kind_rejected(self):
        envelope = sign_economic_state(sample_state())
        with self.assertRaises(ValueError):
            to_economic_relay_bundle(envelope, kind="OPINION", reason="r")

    def test_non_testnet_identity_rejected(self):
        envelope = sign_economic_state(sample_state())
        with self.assertRaises(ValueError):
            to_economic_relay_bundle(envelope, kind="VERDICT", reason="r",
                                     unity_id="unity:mainnet:abc")

    def test_missing_reason_rejected(self):
        envelope = sign_economic_state(sample_state())
        with self.assertRaises(ValueError):
            to_economic_relay_bundle(envelope, kind="VERDICT", reason="")

    def test_mainnet_schema_rejected(self):
        envelope = sign_economic_state(sample_state())
        bundle = to_economic_relay_bundle(envelope, kind="VERDICT",
                                          reason="r")
        # A mainnet-schema bundle arriving at the testnet parser is refused.
        mainnet_bundle = copy.deepcopy(bundle)
        mainnet_bundle["schema"] = "dualis.relay.v1"
        parsed = validate_economic_relay_bundle(mainnet_bundle)
        self.assertFalse(parsed["ok"])
        # And this builder cannot even mint a mainnet-schema bundle —
        # the testnet build path is isolated by construction.
        with self.assertRaises(ValueError):
            to_economic_relay_bundle(envelope, kind="VERDICT", reason="r",
                                     schema="dualis.relay.v1")

    def test_tampered_bundle_rejected(self):
        envelope = sign_economic_state(sample_state())
        bundle = to_economic_relay_bundle(envelope, kind="VERDICT",
                                          reason="r")
        tampered = copy.deepcopy(bundle)
        tampered["envelope"] = {"state": sample_state(), "signature": "x"}
        parsed = validate_economic_relay_bundle(tampered)
        self.assertFalse(parsed["ok"])

    def test_dedupe_by_manifest_hash(self):
        envelope = sign_economic_state(sample_state())
        b = to_economic_relay_bundle(envelope, kind="VERDICT",
                                     relayed_at="2026-10-06T00:00:00Z",
                                     reason="r")
        self.assertEqual(len(dedupe_bundles([b, b])), 1)


class TestWorkerCoordination(unittest.TestCase):
    def test_worker_modules_absent_does_not_block(self):
        # tokenomics/wallet/fuse have not landed with the documented
        # contract; the build must not block on their absence.
        presence = worker_modules_present()
        self.assertIsInstance(presence, dict)
        state = compute_economic_state(prices=SAMPLE_PRICES)
        self.assertIn("price_index", state)
        self.assertEqual(state["price_index"]["rtev-edu"]["price"], 1273.5)


@unittest.skipUnless(_METER_AVAILABLE,
                     "Worker 1 pricing engine not importable in this env")
class TestWorker1Adapter(unittest.TestCase):
    """The real Worker-1 pricing engine landed mid-build (per_decision_meter).
    The fusion layer prefers it per-decision and falls back to raw labeled
    inputs for decisions the engine cannot price (fail closed, never invent).
    """

    def test_engine_priced_decision_uses_engine(self):
        state = compute_economic_state(prices=[{"decision_id": "factory-1"}])
        e = state["price_index"]["factory-1"]
        self.assertEqual(e["source_module"], "pricing")
        self.assertEqual(e["provenance"], "REPORTED")
        # Re-derived: the price is the canon meter's flat 5 test-keys, not
        # the USD surface figure.
        self.assertEqual(e["price"], 5)
        self.assertEqual(e["currency"], "test-keys")
        self.assertTrue(e["pays"])

    def test_derived_surface_bills_flat_five(self):
        # Re-derived: factory-4's surface is DERIVED, and the old model
        # fused the USD price with pays=false for non-REPORTED surfaces.
        # The price is now the SET meter constant — independent of the
        # surface's provenance; the surface's labels stay for honesty.
        state = compute_economic_state(prices=[{"decision_id": "factory-4"}])
        e = state["price_index"]["factory-4"]
        self.assertEqual(e["source_module"], "pricing")
        self.assertEqual(e["provenance"], "DERIVED")
        self.assertEqual(e["price"], 5)
        self.assertEqual(e["currency"], "test-keys")
        self.assertTrue(e["pays"])

    def test_decision_unknown_to_engine_falls_back_to_input(self):
        state = compute_economic_state(prices=[
            {"decision_id": "not-in-index", "price": 5.0,
             "provenance": "REPORTED"},
        ])
        e = state["price_index"]["not-in-index"]
        self.assertEqual(e["source_module"], "input")
        self.assertEqual(e["price"], 5.0)
        self.assertTrue(e["pays"])

    def test_decision_unknown_everywhere_is_unknown(self):
        state = compute_economic_state(prices=[{"decision_id": "ghost"}])
        e = state["price_index"]["ghost"]
        self.assertEqual(e["provenance"], "UNKNOWN")
        self.assertIsNone(e["price"])
        self.assertFalse(e["pays"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
