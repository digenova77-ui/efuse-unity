"""Hermetic tests for whole-runtime integrity and explicit authority boundaries."""
import os
import tempfile
import unittest

from iris_integrity import (
    RUNTIME_MODULES,
    build_runtime_manifest,
    verify_runtime_manifest,
)


class TestRuntimeManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="iris-runtime-manifest-")
        self.root = self.tmp.name
        for name in RUNTIME_MODULES:
            path = os.path.join(self.root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(("module:" + name + "\\n").encode("utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_runtime_set_passes_self_consistency(self):
        manifest, digest = build_runtime_manifest(self.root)
        result = verify_runtime_manifest(manifest, digest, self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["module_count"], len(RUNTIME_MODULES))
        self.assertEqual(result["authority"], "NOT_ESTABLISHED")
        self.assertEqual(result["external_trust_anchor"], "NOT_CONFIGURED")

    def test_one_changed_chamber_refuses(self):
        manifest, digest = build_runtime_manifest(self.root)
        path = os.path.join(self.root, "iris-intake", "iris_patterns.py")
        with open(path, "ab") as handle:
            handle.write(b"# changed after activation\n")
        result = verify_runtime_manifest(manifest, digest, self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "runtime module mismatch")
        self.assertTrue(any("iris_patterns.py" in item["module"] for item in result["mismatches"]))

    def test_changed_deterministic_law_refuses(self):
        manifest, digest = build_runtime_manifest(self.root)
        path = os.path.join(self.root, "iris-intake", "iris_laws.py")
        with open(path, "ab") as handle:
            handle.write(b"# changed law\n")
        result = verify_runtime_manifest(manifest, digest, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("iris_laws.py" in item["module"] for item in result["mismatches"]))

    def test_missing_runtime_module_refuses_manifest_creation(self):
        os.remove(os.path.join(self.root, "iris-intake", "neural.py"))
        with self.assertRaises(FileNotFoundError):
            build_runtime_manifest(self.root)

    def test_missing_runtime_module_refuses_verification(self):
        manifest, digest = build_runtime_manifest(self.root)
        os.remove(os.path.join(self.root, "iris-intake", "iris_arbiter.py"))
        result = verify_runtime_manifest(manifest, digest, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("iris_arbiter.py" in item["module"] for item in result["mismatches"]))

    def test_manifest_digest_tampering_refuses(self):
        manifest, digest = build_runtime_manifest(self.root)
        result = verify_runtime_manifest(manifest, "0" * 64, self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "manifest digest mismatch")

    def test_unexpected_or_omitted_module_refuses(self):
        manifest, digest = build_runtime_manifest(self.root)
        manifest["modules"].pop("iris-intake/iris_arbiter.py")
        result = verify_runtime_manifest(manifest, digest, self.root)
        self.assertFalse(result["ok"])
        self.assertIn("module set", result["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
