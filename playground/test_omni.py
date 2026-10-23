"""Omni layer invariants."""
from __future__ import annotations

import unittest

from omni import omni, omni_brief
from diamond_playground import DiamondPlayground, Facet


class OmniTests(unittest.TestCase):
    def test_snapshot_shape(self):
        o = omni()
        self.assertEqual(o["label"], "OMNI")
        self.assertIn("diamond", o)
        self.assertIn("frontier", o)
        self.assertIn("learning", o)
        self.assertIn("contract", o)
        self.assertIn("UNCHANGED", o["integrity"])

    def test_law_and_boundary_present(self):
        o = omni()
        self.assertEqual(o["contract"]["law"], "LAW WINS")
        self.assertEqual(o["contract"]["origin"], "immutable")
        self.assertEqual(o["learning"]["boundary"], "NOT_FOR_EMISSION")

    def test_impure_playground_reported(self):
        bad = Facet("bad", "economy", clarity="I", color="J", cut="Poor")
        pg = DiamondPlayground(facets=[
            Facet("foundation", "floor"),
            bad,
            Facet("ceiling", "ceiling"),
        ])
        o = omni(playground=pg)
        self.assertFalse(o["diamond"]["ceiling_reached"])
        self.assertFalse(o["frontier"]["ceiling_claimable"])

    def test_brief_contains_key_fields(self):
        b = omni_brief()
        self.assertIn("OMNI", b)
        self.assertIn("floor=", b)
        self.assertIn("frontier_claimable=", b)
        self.assertIn("NOT_FOR_EMISSION", b)

    def test_facing_subset_of_pure(self):
        o = omni()
        # frontier held_count >= 0 and claimable implies held_count == 0
        if o["frontier"]["ceiling_claimable"]:
            self.assertEqual(o["frontier"]["held_count"], 0)



class OmniElevations(unittest.TestCase):
    def test_standing_boundary(self):
        from omni import standing_boundary
        b = standing_boundary()
        self.assertTrue(b["standing_callable"] or b["tokenizer_present"])
        self.assertEqual(b["boundary"], "NOT_FOR_EMISSION")
        self.assertIn("origin", b["emission_source"])

    def test_receipt_checksum(self):
        from omni import receipt_checksum
        c = receipt_checksum()
        self.assertIn("learnings", c)
        self.assertIn("last_receipt", c)
        self.assertIsInstance(c["chain_intact"], bool)



class OmniOptional(unittest.TestCase):
    def test_standing_boundary_fields(self):
        from omni import standing_boundary
        b = standing_boundary()
        for key in ("standing_callable", "tokenizer_present",
                    "emission_source", "boundary"):
            self.assertIn(key, b)
        self.assertIsInstance(b["standing_callable"], bool)
        self.assertIsInstance(b["tokenizer_present"], bool)

    def test_receipt_checksum_non_negative(self):
        from omni import receipt_checksum
        c = receipt_checksum()
        self.assertGreaterEqual(c["learnings"], 0)
        if c["learnings"] > 0:
            self.assertTrue(c["last_receipt"])
            self.assertTrue(c["last_receipt"].startswith("rcpt:"))

    def test_omni_brief_stable_on_repeat(self):
        from omni import omni_brief
        a = omni_brief()
        b = omni_brief()
        self.assertEqual(a, b)

    def test_gui_references_omni_brief(self):
        from pathlib import Path
        text = Path("purity_gui.py").read_text()
        self.assertIn("omni_brief", text)


if __name__ == "__main__":
    unittest.main()
