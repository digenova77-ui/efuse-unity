"""
Tests for the DCLM data serving layer (~/workspace/unity-world/dclm/data.py).

All must pass. Testnet only. Every figure must carry a label;
UNKNOWN is never PASS.
"""
import hashlib
import os
import re
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "core-rings")))
sys.path.insert(0, _HERE)

from data import (  # noqa: E402
    FIGURE_LABELS,
    clear_feed_sources,
    factory_verdicts,
    feed_registry,
    ingest_reading,
    load_registry,
    pricing_index,
    PRICES_MD,
    SEAL_DIR,
    register_feed_source,
    rte_telemetry,
    serve_world_data,
    serve_world_state,
)
from compute import PROVENANCE_LABELS  # noqa: E402

DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "data"))
MANIFEST = os.path.join(DATA_DIR, "MANIFEST.md")


def _assert_all_labeled(node, path="root"):
    """Every dict with a numeric/financial-looking value must carry a label."""
    if isinstance(node, dict):
        has_label = node.get("label") in FIGURE_LABELS
        has_prov = node.get("provenance") in FIGURE_LABELS
        values = " ".join(str(v) for v in node.values())
        if re.search(r"\$\d|[\d,]+\s*(M|B|T|%|bps)\b", values):
            assert has_label or has_prov, (
                f"unlabeled number at {path}: {str(node)[:120]}"
            )
        for k, v in node.items():
            _assert_all_labeled(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _assert_all_labeled(v, f"{path}[{i}]")


class TestFigureLabels(unittest.TestCase):
    def test_rte_figures_never_overstate_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "MEMORY.md")
            rte = rte_telemetry(source_path=missing)
            self.assertEqual(rte["provenance"], "UNKNOWN")
            self.assertEqual(rte["source_status"], "MISSING")
            self.assertIsNone(rte["source_sha256"])
            self.assertTrue(all(row["label"] == "UNKNOWN" for row in rte["rows"]))

    def test_rte_source_content_match_is_reported_not_real(self):
        values = (
            "$32.02B $1,273.5M/yr $6.08B 72 2,071,550 4,684 81% 100% "
            "$348.5M 320 144,200 $215/visit $5,940/standard stay "
            "$812.4M 575 112,500 $340/visit $6,820/standard stay over 100%"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "MEMORY.md")
            with open(source, "w", encoding="utf-8") as fh:
                fh.write(values)
            rte = rte_telemetry(source_path=source)
            self.assertEqual(rte["provenance"], "REPORTED")
            self.assertEqual(rte["source_status"], "CONTENT_MATCH")
            self.assertRegex(rte["source_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(all(row["label"] == "REPORTED" for row in rte["rows"]))

    def test_pricing_figures_all_labeled(self):
        pricing = pricing_index()
        _assert_all_labeled(pricing["rows"])
        for row in pricing["rows"]:
            for fig in row.get("figures", []):
                self.assertIn(fig["label"], FIGURE_LABELS)

    def test_feeds_all_labeled(self):
        for name, entry in feed_registry().items():
            self.assertIn(entry["provenance"], FIGURE_LABELS, name)

    def test_verdicts_all_labeled(self):
        for v in factory_verdicts():
            self.assertIn(v["provenance"], FIGURE_LABELS, v.get("seal"))

    def test_world_state_accepts_bundle(self):
        # compute.py's own provenance validator runs inside serve_world_state.
        state = serve_world_state()
        for name, entry in state["feed_status"].items():
            self.assertIn(entry["provenance"], PROVENANCE_LABELS)
        self.assertIn(state["registry_digest"]["provenance"], PROVENANCE_LABELS)


class TestManifest(unittest.TestCase):
    def test_manifest_sha256_verify(self):
        self.assertTrue(os.path.exists(MANIFEST), "MANIFEST.md missing")
        with open(MANIFEST, encoding="utf-8") as fh:
            text = fh.read()
        rows = re.findall(
            r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|\s*(\d+)\s*\|",
            text,
        )
        self.assertGreaterEqual(len(rows), 7, "manifest has too few rows")
        for fname, want_sha, want_size in rows:
            path = os.path.join(DATA_DIR, fname)
            self.assertTrue(os.path.exists(path), f"vendored file missing: {fname}")
            with open(path, "rb") as fh:
                raw = fh.read()
            got_sha = hashlib.sha256(raw).hexdigest()
            self.assertEqual(got_sha, want_sha, f"sha256 mismatch: {fname}")
            self.assertEqual(len(raw), int(want_size), f"size mismatch: {fname}")

    def test_all_registry_datasets_load_and_validate(self):
        expected = ["countries", "cities", "chambers", "jurisdictions",
                    "doctrine", "rtes", "trinity-verdict"]
        for name in expected:
            data = load_registry(name)  # raises honestly on corrupt data
            self.assertIsNotNone(data)

    def test_load_registry_raises_on_unknown(self):
        with self.assertRaises(ValueError):
            load_registry("no-such-dataset")


class TestFeeds(unittest.TestCase):
    # Contract change 2026-10-06: every feed source is Unity-bound. The
    # medium refuses anonymous ingestion, so these tests bind sources
    # first — exactly as production must.
    FEED_SOURCE = "unity:testnet:feed-operator"

    def setUp(self):
        clear_feed_sources()
        for name in ("air", "iss", "kp_index"):
            register_feed_source(name, self.FEED_SOURCE)

    def tearDown(self):
        clear_feed_sources()

    def test_unbound_feed_refuses_anonymous_ingest(self):
        from purify import PurificationRefused
        clear_feed_sources()
        with self.assertRaises(PurificationRefused):
            ingest_reading("air", reading=b"x", reading_hash="y")

    def test_mismatched_source_refused(self):
        from purify import PurificationRefused
        with self.assertRaises(PurificationRefused):
            ingest_reading("air", reading=b"x", reading_hash="y",
                           source_identity="unity:testnet:impostor")

    def test_live_entry_records_its_source(self):
        entry = ingest_reading("air", reading=b"x", reading_hash="y")
        self.assertEqual(entry["status"], "LIVE")
        self.assertEqual(entry["source_identity"], self.FEED_SOURCE)

    def test_six_feeds_all_pending_null(self):
        feeds = feed_registry()
        self.assertEqual(len(feeds), 6)
        for name in ("air", "moira_river", "earthquakes", "iss",
                     "kp_index", "britain_grid_carbon"):
            self.assertIn(name, feeds)
            entry = feeds[name]
            self.assertEqual(entry["status"], "PENDING")
            self.assertIsNone(entry["last_reading"])
            self.assertIsNone(entry["reading_hash"])
            self.assertEqual(entry["provenance"], "UNKNOWN")

    def test_reading_without_hash_stays_pending(self):
        entry = ingest_reading("air", reading=b"some-bytes", reading_hash=None)
        self.assertEqual(entry["status"], "PENDING")
        self.assertIsNone(entry["last_reading"])

    def test_hash_without_reading_stays_pending(self):
        entry = ingest_reading("iss", reading=None, reading_hash="abc123")
        self.assertEqual(entry["status"], "PENDING")
        self.assertIsNone(entry["reading_hash"])

    def test_reading_plus_hash_goes_live(self):
        entry = ingest_reading("kp_index", reading="Kp=4", reading_hash="deadbeef")
        self.assertEqual(entry["status"], "LIVE")
        self.assertEqual(entry["reading_hash"], "deadbeef")
        self.assertEqual(entry["provenance"], "REPORTED")

    def test_unknown_feed_raises(self):
        with self.assertRaises(ValueError):
            ingest_reading("nope", reading="x", reading_hash="y")

    def test_serve_world_data_feeds_are_pending(self):
        bundle = serve_world_data()
        self.assertEqual(len(bundle["feeds"]), 6)
        state = serve_world_state()
        for name, entry in state["feed_status"].items():
            self.assertEqual(entry["status"], "PENDING")


class TestPricingParsing(unittest.TestCase):
    def test_parsed_count_matches_prices_md_or_reports_absence(self):
        pricing = pricing_index()
        print(f"\n[pricing] parsed={pricing['parsed']} expected={pricing['expected']} "
              f"unknown_rows={pricing['unknown_rows']}")
        self.assertEqual(pricing["expected"], 51)
        if not os.path.exists(PRICES_MD):
            self.assertEqual(pricing["provenance"], "UNKNOWN")
            self.assertEqual(pricing["parsed"], 0)
            self.assertIn("not found", pricing["note"])
        else:
            self.assertEqual(pricing["parsed"], 51)
            self.assertEqual(pricing["source_status"], "CONTENT_AVAILABLE")
            self.assertRegex(pricing["source_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(all(
                row["source_sha256"] == pricing["source_sha256"]
                for row in pricing["rows"]
            ))

    def test_factory_rows_are_not_invented_when_source_absent(self):
        pricing = pricing_index()
        factory = [r for r in pricing["rows"] if r["class"] == "factory-verdict"]
        if not os.path.exists(PRICES_MD):
            self.assertEqual(pricing["provenance"], "UNKNOWN")
            self.assertEqual(factory, [])
            return
        self.assertEqual(len(factory), 33)
        companies = {r["company"] for r in factory}
        self.assertIn("abbvie", companies)
        self.assertIn("walgreens", companies)
        for r in factory:
            self.assertTrue(r["claim_hash"], f"no claim hash for {r['company']}")

    def test_claims_rows_no_dollar_cost(self):
        pricing = pricing_index()
        claims = [r for r in pricing["rows"] if r["class"] == "claims-adjudication"]
        if not os.path.exists(PRICES_MD):
            self.assertEqual(pricing["provenance"], "UNKNOWN")
            self.assertEqual(claims, [])
            return
        self.assertEqual(len(claims), 16)
        self.assertIn("C1", {r["index"] for r in claims})

    def test_rte_decision_rows(self):
        pricing = pricing_index()
        rte = [r for r in pricing["rows"] if r["class"] == "rte-decision"]
        if not os.path.exists(PRICES_MD):
            self.assertEqual(pricing["provenance"], "UNKNOWN")
            self.assertEqual(rte, [])
            return
        self.assertEqual(len(rte), 2)


class TestRteTelemetry(unittest.TestCase):
    def _by_metric(self):
        return {r["metric"]: r for r in rte_telemetry()["rows"]}

    def test_headline_figures_match_memory_md(self):
        m = self._by_metric()
        self.assertEqual(m["combined_operating_envelope"]["value"], "$32.02B")
        self.assertEqual(m["recoverable_nonclassroom_friction"]["value"], "$1,273.5M/yr")
        self.assertEqual(m["five_year_cumulative"]["value"], "$6.08B")
        self.assertEqual(m["school_boards"]["value"], "72")
        self.assertEqual(m["students_fte"]["value"], "2,071,550")
        self.assertEqual(m["schools"]["value"], "4,684")
        self.assertEqual(m["qhc_revenue"]["value"], "$348.5M")
        self.assertEqual(m["qhc_cost_per_ed_visit"]["value"], "$215/visit")
        self.assertEqual(m["khsc_revenue"]["value"], "$812.4M")
        self.assertEqual(m["khsc_kgh_cost_per_ed_visit"]["value"], "$340/visit")

    def test_every_rte_metric_has_source_note(self):
        for row in rte_telemetry()["rows"]:
            self.assertTrue(row["source"], f"no source for {row['metric']}")


class TestFactoryVerdicts(unittest.TestCase):
    def test_trinity_packet_decisions_wired(self):
        verdicts = factory_verdicts()
        packet = [v for v in verdicts
                  if v["seal_ref"].startswith("trinity-verdict.json")]
        self.assertEqual(len(packet), 18)
        self.assertTrue(all(v["provenance"] == "VERIFIED" for v in packet))
        self.assertTrue(all("sha256:" in v["seal_ref"] for v in packet))

    def test_corp_helper_seals_are_scoped_to_available_directory(self):
        verdicts = factory_verdicts()
        if not os.path.isdir(SEAL_DIR):
            self.assertEqual(
                sum(v["seal_ref"].startswith("trinity-verdict.json") for v in verdicts),
                18,
            )
            self.assertFalse(any(
                v.get("seal_note") == "unparseable seal file" for v in verdicts
            ))
            return
        disk_seals = [
            f for f in os.listdir(SEAL_DIR)
            if f.endswith(".md") and (
                ("seal" in f.lower() and not f.startswith("attempt1-"))
                or (f.startswith("ed-enc-") and "-verdict-" in f)
                or f.startswith("ed-adjudication-"))
        ]
        seals = [v for v in verdicts if v["seal_ref"] in disk_seals
                 or v["seal_ref"].replace(".md", "") in disk_seals]
        print(f"\n[seals] disk={len(disk_seals)} wired={len(seals)} "
              f"packet_decisions=18")
        self.assertEqual(len(seals), len(disk_seals))


if __name__ == "__main__":
    unittest.main(verbosity=2)
