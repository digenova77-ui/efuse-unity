"""Unit tests for purity GUI wiring.

Does not launch a window. Checks source contracts
and that the imported callables exist.
"""
from __future__ import annotations

import unittest
from pathlib import Path


GUI = Path(__file__).with_name("purity_gui.py")


class GUIWiringTests(unittest.TestCase):
    def setUp(self):
        self.text = GUI.read_text()

    def test_imports_omni_brief(self):
        self.assertIn("from omni import omni_brief", self.text)

    def test_imports_playground_pieces(self):
        for name in ("DiamondPlayground", "Facet", "visual_report",
                     "save_report", "grade"):
            self.assertIn(name, self.text)

    def test_status_includes_omni_brief_call(self):
        self.assertIn("omni_brief()", self.text)

    def test_buttons_present(self):
        for label in ("Refresh", "Save report", "Apply pressure",
                      "Inject impurity", "Reset"):
            self.assertIn(label, self.text)

    def test_color_tags_configured(self):
        self.assertIn('tag_configure("pass"', self.text)
        self.assertIn('tag_configure("glass"', self.text)

    def test_save_uses_filedialog(self):
        self.assertIn("filedialog.asksaveasfilename", self.text)
        self.assertIn("save_report(", self.text)

    def test_callable_targets_exist(self):
        from diamond_playground import (DiamondPlayground, visual_report,
                                        save_report, grade)
        from omni import omni_brief
        self.assertTrue(callable(visual_report))
        self.assertTrue(callable(save_report))
        self.assertTrue(callable(grade))
        self.assertTrue(callable(omni_brief))
        self.assertTrue(callable(DiamondPlayground))


if __name__ == "__main__":
    unittest.main()
