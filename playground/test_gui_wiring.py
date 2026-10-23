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



class PressureInjectionTests(unittest.TestCase):
    def test_apply_pressure_increments(self):
        from diamond_playground import DiamondPlayground
        p = DiamondPlayground()
        self.assertEqual(p.pressure_passes, 0)
        p.apply_pressure()
        self.assertEqual(p.pressure_passes, 1)
        p.apply_pressure()
        self.assertEqual(p.pressure_passes, 2)

    def test_pressure_does_not_break_floor(self):
        from diamond_playground import DiamondPlayground
        p = DiamondPlayground()
        for _ in range(5):
            p.apply_pressure()
        self.assertTrue(p.floor_holds())
        self.assertTrue(p.rise().get("ok"))

    def test_inject_impurity_blocks_ceiling(self):
        from diamond_playground import DiamondPlayground, Facet
        p = DiamondPlayground()
        self.assertTrue(p.ceiling().get("reached"))
        bad = Facet("tinted_claim", "economy",
                    clarity="FL", color="J", cut="Fair")
        p.facets.insert(-1, bad)
        self.assertFalse(p.rise().get("ok"))
        self.assertFalse(p.ceiling().get("reached"))

    def test_reset_restores_clean(self):
        from diamond_playground import DiamondPlayground, Facet
        p = DiamondPlayground()
        p.apply_pressure()
        p.facets.insert(-1, Facet("bad", "economy", clarity="I"))
        # simulate reset
        p2 = DiamondPlayground()
        self.assertEqual(p2.pressure_passes, 0)
        self.assertTrue(p2.ceiling().get("reached"))
        self.assertFalse(any(f.name == "bad" for f in p2.facets))

    def test_gui_wires_pressure_and_inject(self):
        text = GUI.read_text()
        self.assertIn("on_pressure", text)
        self.assertIn("on_impurity", text)
        self.assertIn("apply_pressure", text)
        self.assertIn("tinted_claim", text)



class UITests(unittest.TestCase):
    def test_status_label_exists(self):
        text = GUI.read_text()
        self.assertIn("status_label", text)
        self.assertIn("textvariable=self.status", text)

    def test_tree_columns(self):
        text = GUI.read_text()
        for col in ("name", "kind", "clarity", "color", "cut", "verdict"):
            self.assertIn(f'"{col}"', text)

    def test_color_backgrounds(self):
        text = GUI.read_text()
        self.assertIn("#e6ffe6", text)  # green pass
        self.assertIn("#ffe6e6", text)  # red glass

    def test_refresh_rebuilds_tree(self):
        text = GUI.read_text()
        self.assertIn("self.tree.delete", text)
        self.assertIn("self.tree.insert", text)

    def test_window_title_and_geometry(self):
        text = GUI.read_text()
        self.assertIn("Diamond Purity Playground", text)
        self.assertIn("geometry", text)

    def test_headless_import(self):
        # Import must succeed even without a display
        import importlib.util
        spec = importlib.util.spec_from_file_location("purity_gui", GUI)
        mod = importlib.util.module_from_spec(spec)
        # Do not exec main; just confirm module file is valid Python
        compile(GUI.read_text(), str(GUI), "exec")
        self.assertIsNotNone(spec)



class ImportExportTests(unittest.TestCase):
    def test_export_writes_report(self):
        import tempfile, os
        from diamond_playground import DiamondPlayground, save_report, visual_report
        p = DiamondPlayground()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.txt")
            returned = save_report(path, p)
            self.assertEqual(returned, path)
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn("DIAMOND PURITY REPORT", content)
            self.assertEqual(content.strip(), visual_report(p).strip())

    def test_export_default_name(self):
        text = GUI.read_text()
        self.assertIn("purity_report.txt", text)
        self.assertIn("defaultextension", text)

    def test_import_round_trip(self):
        import tempfile, os
        from diamond_playground import DiamondPlayground, save_report
        p = DiamondPlayground()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "round.txt")
            save_report(path, p)
            loaded = open(path).read()
            # re-export and compare
            path2 = os.path.join(d, "round2.txt")
            save_report(path2, p)
            self.assertEqual(open(path).read(), open(path2).read())
            self.assertIn("rise:", loaded)
            self.assertIn("ceiling:", loaded)

    def test_gui_export_wired(self):
        text = GUI.read_text()
        self.assertIn("on_save", text)
        self.assertIn("asksaveasfilename", text)
        self.assertIn("save_report", text)


if __name__ == "__main__":
    unittest.main()
