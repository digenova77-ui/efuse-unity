"""Tests for the pricing re-derivation fix (2026-10-06).

Reinvestigation verdict: the old model priced the object being measured,
not the act of deciding (F1), in USD instead of test-keys (F2), via a
second meter (F3) — and fused the false USD billable into the SIGNED
EconomicState with pays=true (F4, a live billing bug).

The re-derived law under test here:
  * Every decision bills exactly the canon meter's flat COMPUTE price:
    5 test-keys (SET in dclm/meter.py — imported, never re-hardcoded).
  * No USD value appears in any billable field. USD surface figures
    remain as labeled data (REPORTED/MODELED/DERIVED), billable 0.
  * The signed EconomicState carries the 5-test-key price and the labeled
    surface figures separately. Nothing that was pays=true on false USD
    remains.
  * The friction-kill rebate hook exists but is inert (HELD for David).

Testnet only.
"""
import copy
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import pricing  # noqa: E402
from pricing import (  # noqa: E402
    INDEX,
    PRICE_COMPUTE,
    PRICE_CURRENCY,
    REBATE_PENDING_DAVID,
    friction_kill_rebate,
    per_decision_meter,
    price_decision,
)
from meter import PRICE_COMPUTE as METER_PRICE_COMPUTE  # noqa: E402
import economic_state  # noqa: E402
from economic_state import (  # noqa: E402
    compute_economic_state,
    sign_economic_state,
    verify_economic_envelope,
)


class TestFlatFiveTestKeys(unittest.TestCase):
    def test_price_constant_is_the_meter_constant_not_a_copy(self):
        # The canon meter owns pricing. One owner, no second meter (F3).
        self.assertIs(pricing.PRICE_COMPUTE, METER_PRICE_COMPUTE)
        self.assertEqual(PRICE_COMPUTE, 5)
        self.assertEqual(PRICE_CURRENCY, "test-keys")

    def test_every_indexed_decision_bills_exactly_five_test_keys(self):
        ids = [r["decision_id"] for r in INDEX]
        self.assertEqual(len(ids), 53)
        for r in per_decision_meter(ids):
            self.assertEqual(r["billable_amount"], 5,
                             f"{r['decision_id']} does not bill 5 test-keys")
            self.assertEqual(r["currency"], "test-keys",
                             f"{r['decision_id']} not denominated in test-keys")
            self.assertEqual(r["price_provenance"], "SET",
                             f"{r['decision_id']} price is not SET")
            self.assertTrue(r["pass"])

    def test_no_size_scaling_no_tiers(self):
        # Amazon ($637,959M surface) and Tyson ($8,830M surface) billed the
        # same atomic decision price — the F6 de-facto tiering is dead.
        amazon = price_decision("factory-2")
        tyson = price_decision("factory-31")
        self.assertEqual(amazon["billable_amount"], tyson["billable_amount"])
        self.assertEqual(amazon["billable_amount"], 5)

    def test_unknown_decision_still_never_pays(self):
        # UNKNOWN is never PASS — standing canon law, kept under the new model.
        row = {
            "row_number": 999,
            "decision_id": "factory-999",
            "class": "factory",
            "company": "testco",
            "vector": "V1. Test vector with no figure on record",
            "figures": [
                {"name": "cost surface", "amount_m": None, "custody": "UNKNOWN"},
            ],
            "claim_hash": "test",
            "source": "test",
        }
        backup = copy.deepcopy(pricing.INDEX)
        try:
            pricing.INDEX.append(row)
            p = price_decision("factory-999")
            self.assertEqual(p["label"], "UNKNOWN")
            self.assertFalse(p["pass"])
            self.assertEqual(p["billable_amount"], 0)
            self.assertEqual(p["currency"], "test-keys")
        finally:
            pricing.INDEX[:] = backup


class TestNoUSDBillable(unittest.TestCase):
    def test_no_usd_billable_field_exists(self):
        # The false billable field is retired — it must not exist at all.
        for decision_id in [r["decision_id"] for r in INDEX]:
            p = price_decision(decision_id)
            self.assertNotIn("billable_amount_m", p,
                             f"{decision_id} still carries the USD billable")
            self.assertNotIn("USD", str(p["billable_amount"]))
            self.assertNotIn("USD", p["currency"])

    def test_price_provenance_is_set_not_reported(self):
        # F5: the old billable wore label=REPORTED as if someone reported a
        # price. Nobody did. The price's provenance is SET (canon constant);
        # REPORTED lives only on the surface figures.
        for decision_id in ("factory-2", "factory-14", "rte-edu",
                            "factory-101", "factory-102"):
            p = price_decision(decision_id)
            self.assertEqual(p["price_provenance"], "SET")
            self.assertNotEqual(p["billable_amount"], 637959.0)

    def test_surface_figures_are_labels_billable_zero(self):
        for decision_id in ("factory-2", "rte-edu"):
            surface = price_decision(decision_id)["price_surface"]
            self.assertIn("figures", surface)
            for fig in surface["figures"]:
                self.assertEqual(fig["billable"], 0,
                                 f"{decision_id} figure billed: {fig['name']}")
                self.assertIn(fig["label"],
                              {"REPORTED", "VERIFIED", "MODELED", "DERIVED",
                               "UNKNOWN"})

    def test_surface_data_unchanged_spot_checks(self):
        # The 53 decisions' surface data is untouched — only what is billed.
        p2 = price_decision("factory-2")
        self.assertEqual(p2["price_surface"]["figures"][0]["amount_m"],
                         637959.0)
        self.assertEqual(p2["price_surface"]["figures"][0]["label"],
                         "REPORTED")
        edu = price_decision("rte-edu")
        self.assertEqual(edu["price_surface"]["figures"][0]["amount_m"],
                         1273.5)
        self.assertEqual(edu["price_surface"]["figures"][0]["label"],
                         "REPORTED")
        c1 = price_decision("claims-C1")
        self.assertEqual(c1["price_surface"]["verdict"], "KEEP")
        self.assertEqual(c1["price_surface"]["dollar_cost"], "N/A")
        self.assertEqual(c1["billable_amount"], 5)  # wallet-surface compute

    def test_rte_health_unit_error_fixed(self):
        # F8: cost-per-ED-visit figures were amount_m (millions) with a USD
        # unit. They are $215 / $340 per visit — dollars, not millions.
        surface = price_decision("rte-health")["price_surface"]
        by_name = {f["name"]: f for f in surface["figures"]}
        qhc = by_name["QHC cost per ED visit"]
        khsc = by_name["KHSC (KGH) cost per ED visit"]
        self.assertNotIn("amount_m", qhc)
        self.assertNotIn("amount_m", khsc)
        self.assertEqual(qhc["amount_usd"], 215.0)
        self.assertEqual(khsc["amount_usd"], 340.0)
        self.assertEqual(qhc["unit"], "USD/visit")
        self.assertEqual(qhc["label"], "REPORTED")
        self.assertEqual(qhc["billable"], 0)


class TestSignedStateCorrected(unittest.TestCase):
    def _priced_state(self):
        return compute_economic_state(
            prices=[{"decision_id": d}
                    for d in ("factory-1", "factory-2", "factory-4",
                              "factory-14", "factory-31", "rte-edu",
                              "rte-health", "factory-101", "factory-102",
                              "claims-C1")]
        )

    def _walk(self, node, found):
        if isinstance(node, dict):
            for k, v in node.items():
                found.append(k)
                self._walk(v, found)
        elif isinstance(node, list):
            for v in node:
                self._walk(v, found)

    def test_signed_envelope_verifies_with_corrected_price(self):
        state = self._priced_state()
        envelope = sign_economic_state(state)
        self.assertTrue(verify_economic_envelope(envelope))

    def test_engine_entries_carry_five_test_keys_not_usd(self):
        state = self._priced_state()
        for decision_id in ("factory-1", "factory-2", "factory-14",
                            "factory-31", "rte-edu", "factory-101"):
            e = state["price_index"][decision_id]
            self.assertEqual(e["source_module"], "pricing")
            self.assertEqual(e["price"], 5)
            self.assertEqual(e["currency"], "test-keys")
            self.assertTrue(e["pays"])
            self.assertNotIn("billable_amount_m", e)
            # The surface figures ride along as labeled data, never billed.
            self.assertIn("price_surface", e)
            for fig in e["price_surface"].get("figures", []):
                self.assertEqual(fig["billable"], 0)

    def test_no_usd_value_in_any_billable_field_signed_state(self):
        state = self._priced_state()
        keys = []
        self._walk(state["price_index"], keys)
        self.assertNotIn("billable_amount_m", keys)
        # No pays=true entry prices USD: every pays entry's price is 5
        # test-keys.
        for decision_id, e in state["price_index"].items():
            if decision_id == "provenance":
                continue
            if e.get("source_module") == "pricing" and e.get("pays"):
                self.assertEqual(e["price"], 5,
                                 f"{decision_id} pays on a non-flat price")
                self.assertEqual(e["currency"], "test-keys",
                                 f"{decision_id} pays in a non-test-key unit")

    def test_derived_surface_still_bills_flat_five(self):
        # F4's old rule (MODELED/DERIVED surface -> pays=false) governed the
        # false USD price. The price is now the SET meter constant —
        # independent of the surface's provenance.
        state = self._priced_state()
        e = state["price_index"]["factory-4"]
        self.assertEqual(e["provenance"], "DERIVED")  # surface honesty kept
        self.assertEqual(e["price"], 5)
        self.assertTrue(e["pays"])


class TestRebateHookInert(unittest.TestCase):
    def test_hook_flag_present(self):
        self.assertTrue(REBATE_PENDING_DAVID)

    def test_hook_refuses_to_act(self):
        with self.assertRaises(NotImplementedError) as ctx:
            friction_kill_rebate("factory-2", kill_receipt="kr-1")
        self.assertIn("DAVID", str(ctx.exception).upper())

    def test_signed_entries_carry_inert_marker(self):
        state = compute_economic_state(
            prices=[{"decision_id": "factory-2"}])
        e = state["price_index"]["factory-2"]
        self.assertEqual(e["rebate"], "REBATE_PENDING_DAVID")
        # The marker does not move value: pays still follows the flat price.
        self.assertTrue(e["pays"])
        self.assertEqual(e["price"], 5)


class TestSurfaceFiguresStillPresentAndLabeled(unittest.TestCase):
    def test_index_row_count_and_claim_hashes(self):
        self.assertEqual(len(INDEX), 53)
        uber = price_decision("factory-101")
        self.assertEqual(uber["price_surface"]["figures"][0]["label"],
                         "REPORTED")
        self.assertEqual(uber["billable_amount"], 5)

    def test_surface_is_valid_json_and_provenance_labeled(self):
        for r in per_decision_meter([r["decision_id"] for r in INDEX]):
            # JSON-serializable (it signs into the state) ...
            json.dumps(r["price_surface"])
            self.assertIn(r["provenance"],
                          {"REPORTED", "VERIFIED", "MODELED", "DERIVED",
                           "UNKNOWN"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
