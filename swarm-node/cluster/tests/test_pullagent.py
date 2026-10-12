#!/usr/bin/env python3
"""pull-agent fused apply/rollback tests.

Proves: apply_bundle swaps the fused layout (node/ + pull-agent/ + unit),
keeps previous for rollback, restores both on rollback — and still applies
a legacy node-only bundle (v1.0.0 shape).

Run: python3 tests/test_pullagent.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

CLUSTER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load():
    spec = importlib.util.spec_from_file_location(
        "pullagent", os.path.join(CLUSTER, "pull-agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.pa = load()
        self.tmp = tempfile.mkdtemp(prefix="pa-test-")
        self.pa.NODE_DIR = os.path.join(self.tmp, "opt/dualis/node")
        self.pa.PULL_DIR = os.path.join(self.tmp, "opt/dualis/pull-agent")
        self.pa.PULL_UNIT = os.path.join(
            self.tmp, "etc/systemd/system/dualis-pull-agent.service")
        self.pa.VERSION_FILE = os.path.join(self.tmp, "etc/dualis/version")
        os.makedirs(os.path.dirname(self.pa.VERSION_FILE), exist_ok=True)
        with open(self.pa.VERSION_FILE, "w") as f:
            f.write("v1.0.0\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _live(self):
        os.makedirs(self.pa.NODE_DIR)
        open(os.path.join(self.pa.NODE_DIR, "old.txt"), "w").write("old")
        os.makedirs(self.pa.PULL_DIR)
        open(os.path.join(self.pa.PULL_DIR, "old.txt"), "w").write("old")

    def _stage(self, fused=True):
        stage = os.path.join(self.tmp, "stage")
        os.makedirs(os.path.join(stage, "node"))
        open(os.path.join(stage, "node", "new.txt"), "w").write("new")
        if fused:
            os.makedirs(os.path.join(stage, "pull-agent"))
            open(os.path.join(stage, "pull-agent", "new.txt"),
                 "w").write("new")
            open(os.path.join(stage, "dualis-pull-agent.service"),
                 "w").write("[Unit]\n")
        return stage

    def _read(self, *parts):
        with open(os.path.join(*parts)) as f:
            return f.read()

    def test_fused_apply_and_rollback(self):
        self._live()
        moved = self.pa.apply_bundle(self._stage(fused=True), "v1.1.0")
        self.assertEqual(self._read(self.pa.NODE_DIR, "new.txt"), "new")
        self.assertEqual(self._read(self.pa.PULL_DIR, "new.txt"), "new")
        self.assertTrue(os.path.isfile(self.pa.PULL_UNIT))
        self.assertEqual(self._read(self.pa.VERSION_FILE), "v1.1.0\n")
        self.assertEqual(set(moved), {"node", "pull-agent"})
        self.assertTrue(self.pa.rollback_bundle(moved))
        self.assertEqual(self._read(self.pa.NODE_DIR, "old.txt"), "old")
        self.assertEqual(self._read(self.pa.PULL_DIR, "old.txt"), "old")

    def test_legacy_node_only_bundle_still_applies(self):
        self._live()
        moved = self.pa.apply_bundle(self._stage(fused=False), "v1.0.0")
        self.assertEqual(self._read(self.pa.NODE_DIR, "new.txt"), "new")
        # pull-agent untouched by a legacy bundle
        self.assertEqual(self._read(self.pa.PULL_DIR, "old.txt"), "old")
        self.assertEqual(set(moved), {"node"})
        self.assertTrue(self.pa.rollback_bundle(moved))
        self.assertEqual(self._read(self.pa.NODE_DIR, "old.txt"), "old")

    def test_rollback_nothing_is_false(self):
        self.assertFalse(self.pa.rollback_bundle({}))
        self.assertFalse(self.pa.rollback_bundle(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
