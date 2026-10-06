"""Tests for the DCLM-side pricing engine (pricing.py).

David's laws under test: real data only; UNKNOWN is never PASS; every
mutation needs a receipt; no tiers possible by construction; benchmark /
reference / evolve; testnet isolation (no production state touched).
"""

import copy
import inspect
import json
import os
import unittest

import pricing
from pricing import (
    INDEX,
    PROVENANCE_LABELS,
    extend_index,
    index_hash,
    normalize_label,
    per_decision_meter,
    price_decision,
    read_receipts,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
ADDENDUM = os.path.join(_HERE, "PRICES_ADDENDUM.md")


def _unknown_row():
    return {
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


class PricingTest(unittest.TestCase):
    def setUp(self):
        self._index_backup = copy.deepcopy(pricing.INDEX)
        self._log_backup = None
        if os.path.exists(pricing.RECEIPTS_LOG):
            with open(pricing.RECEIPTS_LOG, encoding="utf-8") as fh:
                self._log_backup = fh.read()

    def tearDown(self):
        pricing.INDEX[:] = self._index_backup
        if self._log_backup is None:
            if os.path.exists(pricing.RECEIPTS_LOG):
                os.remove(pricing.RECEIPTS_LOG)
        else:
            with open(pricing.RECEIPTS_LOG, "w", encoding="utf-8") as fh:
                fh.write(self._log_backup)

    # --- index integrity ------------------------------------------------
    def test_old_index_intact(self):
        seed = [r for r in INDEX if r["decision_id"].startswith("factory-")
                and r.get("row_number") is not None and r["row_number"] <= 33]
        self.assertEqual(len(seed), 33)
        self.assertEqual(len(INDEX), 53)  # 33 + 2 RTE + 16 claims + 2 new

    def test_uber_row_present_with_provenance(self):
        p = price_decision("factory-101")
        self.assertEqual(p["label"], "REPORTED")
        self.assertEqual(p["provenance"], "REPORTED")
        self.assertIn("take-rate", p["vector"])
        # Re-derived: the flat canon-meter price, not the USD surface.
        self.assertEqual(p["billable_amount"], 5)
        self.assertEqual(p["currency"], "test-keys")
        row = next(r for r in INDEX if r["decision_id"] == "factory-101")
        self.assertEqual(
            row["claim_hash"],
            "e75e4302836047626360dbc4b8985e60b799b37e35605514cd6ae5d53690061a",
        )

    def test_massmutual_row_present_with_provenance(self):
        p = price_decision("factory-102")
        self.assertEqual(p["label"], "REPORTED")
        self.assertEqual(p["provenance"], "REPORTED")
        self.assertIn("whole-life", p["vector"])
        row = next(r for r in INDEX if r["decision_id"] == "factory-102")
        self.assertEqual(
            row["claim_hash"],
            "820275aaf5eaaf38ef14f62b84057c1f1f07022555a03c1b024a27e6c606d54c",
        )

    def test_rte_rows_real_figures(self):
        p = price_decision("rte-edu")
        self.assertEqual(p["label"], "REPORTED")
        # Re-derived: the $1.27B/yr stays as a REPORTED friction-target
        # ledger figure (billable 0); the decision bills 5 test-keys flat.
        self.assertEqual(p["billable_amount"], 5)
        self.assertEqual(p["currency"], "test-keys")
        surface = p["price_surface"]["figures"]
        self.assertEqual(surface[0]["amount_m"], 1273.5)
        self.assertEqual(surface[0]["label"], "REPORTED")
        self.assertEqual(surface[0]["billable"], 0)

    def test_claims_verdict_is_price(self):
        p = price_decision("claims-C1")
        self.assertEqual(p["price_surface"]["verdict"], "KEEP")
        self.assertEqual(p["price_surface"]["dollar_cost"], "N/A")
        # Re-derived: the verdict is the price (dollar cost N/A); the
        # wallet-surface compute is the flat 5 test-keys.
        self.assertEqual(p["billable_amount"], 5)
        self.assertEqual(p["label"], "REPORTED")  # reported verdict, not UNKNOWN

    # --- per-decision atomicity -----------------------------------------
    def test_atomicity_one_price_per_decision(self):
        ids = ["factory-1", "factory-101", "factory-102", "rte-edu",
               "rte-health", "claims-C1"]
        records = per_decision_meter(ids)
        self.assertEqual(len(records), len(ids))
        self.assertEqual([r["decision_id"] for r in records], ids)

    def test_records_are_independent(self):
        a = per_decision_meter(["factory-1"])
        b = per_decision_meter(["factory-1"])
        a[0]["price_surface"]["figures"][0]["amount_m"] = -1
        self.assertNotEqual(
            a[0]["price_surface"]["figures"][0]["amount_m"],
            b[0]["price_surface"]["figures"][0]["amount_m"],
        )

    def test_deterministic(self):
        ids = ["factory-2", "factory-101", "claims-R4"]
        self.assertEqual(per_decision_meter(ids), per_decision_meter(ids))

    # --- no tiers possible by construction -------------------------------
    def test_no_tiers_by_construction(self):
        self.assertIsNone(pricing.TIERS)
        params = inspect.signature(per_decision_meter).parameters
        self.assertEqual(list(params), ["decisions"])  # no tier parameter exists
        for r in per_decision_meter(["factory-1", "factory-101"]):
            self.assertNotIn("tier", r)
        with self.assertRaises(TypeError):
            per_decision_meter(["factory-1"], tier="gold")  # type: ignore[call-arg]

    # --- UNKNOWN is never PASS, pays nothing ------------------------------
    def test_unknown_never_pays(self):
        extend_index([_unknown_row()], actor="test")
        p = price_decision("factory-999")
        self.assertEqual(p["label"], "UNKNOWN")
        self.assertEqual(p["provenance"], "UNKNOWN")
        self.assertFalse(p["pass"])  # never a pass
        self.assertEqual(p["billable_amount"], 0)  # pays nothing

    def test_unknown_marked_explicitly_in_meter(self):
        extend_index([_unknown_row()], actor="test")
        records = per_decision_meter(["factory-1", "factory-999"])
        unknown = records[1]
        self.assertEqual(unknown["label"], "UNKNOWN")
        self.assertFalse(unknown["pass"])
        self.assertEqual(unknown["billable_amount"], 0)
        self.assertTrue(records[0]["pass"])  # reported row still passes

    # --- no modeled figures presented as real ------------------------------
    def test_no_modeled_as_real(self):
        for decision_id in ("factory-4", "factory-11", "factory-20"):
            p = price_decision(decision_id)
            self.assertEqual(p["label"], "DERIVED")  # never REPORTED
            self.assertNotEqual(p["label"], "REPORTED")

    def test_row_label_matches_primary_custody(self):
        for row in INDEX:
            if row["class"] == "claims":
                continue
            expected = (normalize_label(row["figures"][0]["custody"])
                        if row["figures"] else "UNKNOWN")
            self.assertEqual(price_decision(row["decision_id"])["label"], expected)

    # --- provenance labels are DCLM-valid -----------------------------------
    def test_provenance_labels_in_dclm_set(self):
        self.assertEqual(PROVENANCE_LABELS,
                         frozenset({"REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}))
        for row in INDEX:
            label = price_decision(row["decision_id"])["label"]
            self.assertIn(label, PROVENANCE_LABELS)

    # --- mutations need receipts ---------------------------------------------
    def test_extend_index_writes_receipt(self):
        before = index_hash()
        n_before = len(INDEX)
        receipt = extend_index([_unknown_row()], actor="test")
        self.assertEqual(receipt["before_hash"], before)
        self.assertEqual(receipt["after_hash"], index_hash())
        self.assertEqual(receipt["row_count_before"], n_before)
        self.assertEqual(receipt["row_count_after"], n_before + 1)
        self.assertEqual(receipt["rows_added"], ["factory-999"])
        receipts = read_receipts()
        self.assertEqual(receipts[-1]["after_hash"], index_hash())

    def test_extend_rejects_unmapped_custody(self):
        bad = _unknown_row()
        bad["decision_id"] = "factory-998"
        bad["figures"] = [{"name": "x", "amount_m": 1.0, "custody": "TRUST-ME"}]
        n_receipts = len(read_receipts())
        with self.assertRaises(ValueError):
            extend_index([bad], actor="test")
        self.assertEqual(len(INDEX), 53)  # unchanged
        self.assertEqual(len(read_receipts()), n_receipts)  # no receipt on failure

    def test_extend_rejects_duplicates(self):
        with self.assertRaises(ValueError):
            extend_index([_unknown_row(), _unknown_row()], actor="test")
        with self.assertRaises(ValueError):
            extend_index([{"decision_id": "factory-1", "class": "factory",
                           "figures": []}], actor="test")

    # --- fail closed ----------------------------------------------------------
    def test_unknown_decision_id_fails_closed(self):
        with self.assertRaises(KeyError):
            price_decision("factory-34")  # not in the index: never invented

    # --- addendum --------------------------------------------------------------
    def test_addendum_written(self):
        self.assertTrue(os.path.exists(ADDENDUM))
        with open(ADDENDUM, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("#101", text)
        self.assertIn("#102", text)
        self.assertIn("57 missing", text)
        self.assertIn("102", text)

    # --- testnet isolation: nothing outside economics/ --------------------------
    def test_receipts_stay_in_economics(self):
        self.assertTrue(
            os.path.abspath(pricing.RECEIPTS_LOG).startswith(
                os.path.abspath(_HERE) + os.sep
            )
        )


if __name__ == "__main__":
    unittest.main()
