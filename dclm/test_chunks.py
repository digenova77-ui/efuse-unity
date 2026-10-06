"""
Tests for the DCLM chunked data serving layer (chunks.py) + the relay
chunk wrapper (relay/wrap-chunk.mjs).

Covers the original chunk contract AND the Trinity P0 findings
(PURITY_VERDICT_PROGRESSIVE_ARCH.md):
  P0-2 readjustment protocol — epoch/version on every chunk, no-downgrade
        data, version-pinned streams, schema version + per-dataset policy,
        STALE support via retained previous manifest.
  P0-3 tiered freshness — long/short tiers encoded per chunk and per
        dataset; wallet NEVER chunked, always live.

Testnet only. UNKNOWN is never PASS.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

# Hermetic test state: every test run gets its own epoch file, lock,
# receipts, and schema file, so concurrent workers' builds on this shared
# box can never interleave with (or corrupt) the test's epoch chain.
os.environ["CHUNK_STATE_DIR"] = tempfile.mkdtemp(prefix="chunk-test-state-")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import chunks  # noqa: E402
from chunks import (  # noqa: E402
    CHUNK_SCHEMA,
    FRESHNESS_CURRENT,
    HEAD_SCHEMA,
    MANIFEST_SCHEMA,
    MAX_CHUNK_BYTES,
    POLICY_PURGE,
    POLICY_RETAIN_STALE,
    SHARD_MANIFEST_SCHEMA,
    TIER_LONG,
    TIER_SHORT,
    ChunkServer,
    _canonical_bytes,
    _shard_items,
    build_all,
    build_dataset_chunks,
    build_shard_manifest,
)
from compute import KEY_ID, verify_envelope  # noqa: E402
from data import FIGURE_LABELS  # noqa: E402

WRAP_HELPER = os.path.normpath(os.path.join(_HERE, "..", "relay",
                                            "wrap-chunk.mjs"))


def _write_tmp(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_canonical_bytes(obj).decode()
                 if not isinstance(obj, str) else obj)


class TestChunkContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = build_all()

    def test_manifest_signed_and_verifies(self):
        m = self.bundle["manifest"]
        self.assertEqual(m["state"]["schema"], MANIFEST_SCHEMA)
        self.assertTrue(verify_envelope(m), "manifest signature must verify")
        self.assertEqual(m["key_id"], KEY_ID)

    def test_manifest_priority_order_and_inventory(self):
        ds = self.bundle["manifest"]["state"]["datasets"]
        pris = [d["priority"] for d in ds]
        self.assertEqual(pris, sorted(pris), "datasets in priority order")
        self.assertEqual(len(ds), 18)
        # every entry: id fields, sizes, hashes, labels, freshness, policy
        for d in ds:
            for f in ("dataset", "priority", "shards", "total_bytes",
                      "dataset_hash", "provenance", "provenance_labels",
                      "freshness_tier", "schema_policy", "status"):
                self.assertIn(f, d, f"dataset {d.get('dataset')} missing {f}")
            self.assertRegex(d["dataset_hash"], r"^[0-9a-f]{64}$")
            self.assertIn(d["provenance"], FIGURE_LABELS)
            self.assertTrue(set(d["provenance_labels"]) <= FIGURE_LABELS)
            self.assertIn(d["freshness_tier"], (TIER_LONG, TIER_SHORT))
            self.assertIn(d["schema_policy"],
                          (POLICY_PURGE, POLICY_RETAIN_STALE))

    def test_every_chunk_signed_bounded_labeled(self):
        for cid, env in self.bundle["chunks_by_id"].items():
            with self.subTest(chunk=cid):
                self.assertTrue(verify_envelope(env))
                body = env["state"]
                self.assertEqual(body["schema"], CHUNK_SCHEMA)
                self.assertEqual(body["chunk_id"], cid)
                self.assertLessEqual(body["data_bytes"], MAX_CHUNK_BYTES,
                                     "chunk data bounded at 256KiB")
                self.assertIn(body["provenance"], FIGURE_LABELS)
                self.assertTrue(set(body["provenance_labels"]) <= FIGURE_LABELS)
                # content hash matches the data actually carried
                self.assertEqual(
                    body["content_hash"],
                    hashlib.sha256(_canonical_bytes(body["data"])).hexdigest())

    def test_provenance_not_flattened(self):
        by_id = self.bundle["chunks_by_id"]
        tele = by_id["telemetrics@shard-000001-of-000001"]["state"]
        self.assertEqual(set(tele["provenance_labels"]), {"REAL"})
        feeds = by_id["feeds@shard-000001-of-000001"]["state"]
        self.assertEqual(set(feeds["provenance_labels"]), {"UNKNOWN"})
        pricing = by_id["pricing@shard-000001-of-000001"]["state"]
        self.assertIn("UNKNOWN", pricing["provenance_labels"])
        ws = by_id["world-state@shard-000001-of-000001"]["state"]
        self.assertIn("UNKNOWN", ws["provenance_labels"])
        # manifest dataset rows agree with their chunks
        for meta in self.bundle["datasets_meta"]:
            entries = self.bundle["shard_entries"][meta["dataset"]]
            union = set()
            for e in entries:
                union.update(e["provenance_labels"])
            self.assertEqual(sorted(union), meta["provenance_labels"])

    def test_sharding_roundtrip_and_bound(self):
        import data as _data
        cities = _data.load_registry("cities")["cities"]
        envs, entries = build_dataset_chunks(
            "cities.full", 3, chunks._b_cities_full, max_bytes=4096,
            world_epoch=99)
        self.assertGreater(len(envs), 10, "tiny bound forces many shards")
        for env in envs:
            self.assertLessEqual(env["state"]["data_bytes"], 4096)
            self.assertTrue(verify_envelope(env))
            self.assertEqual(env["state"]["world_epoch"], 99)
        reassembled = []
        for env in envs:
            reassembled.extend(env["state"]["data"])
        self.assertEqual(reassembled, cities)

    def test_oversize_item_flagged_never_dropped(self):
        big = {"blob": "x" * (MAX_CHUNK_BYTES + 100)}
        shards = _shard_items([{"ok": 1}, big, {"ok": 2}],
                              max_bytes=MAX_CHUNK_BYTES)
        self.assertEqual(len(shards), 3)
        self.assertTrue(shards[1][1], "oversize item flagged")
        self.assertEqual(shards[1][0], [big], "oversize item kept, not split")

    def test_unknown_never_pass(self):
        blob = _canonical_bytes(self.bundle["manifest"]).decode()
        self.assertNotIn("PASS", blob)
        for cid, env in self.bundle["chunks_by_id"].items():
            body = _canonical_bytes(env["state"]).decode()
            # no chunk may present an unknown figure as a positive claim
            self.assertNotIn('"provenance": "PASS"', body)


class TestReadjustmentProtocol(unittest.TestCase):
    """Trinity P0-2."""

    @classmethod
    def setUpClass(cls):
        cls.server = ChunkServer()
        cls.server.regenerate()

    def test_epoch_on_everything_and_monotonic(self):
        b1 = self.server._generations[self.server._current_epoch]
        e1 = b1["world_epoch"]
        self.assertGreaterEqual(e1, 1)
        for cid, env in b1["chunks_by_id"].items():
            self.assertEqual(env["state"]["world_epoch"], e1)
            self.assertEqual(env["state"]["schema_version"],
                             b1["schema_version"])
        self.assertEqual(b1["manifest"]["state"]["world_epoch"], e1)
        self.assertEqual(b1["head"]["state"]["world_epoch"], e1)
        # second cut -> epoch bumps by exactly one (hermetic state dir:
        # no other writer can intervene, so the cut is exactly +1).
        self.server.regenerate()
        b2 = self.server._generations[self.server._current_epoch]
        self.assertEqual(b2["world_epoch"], e1 + 1)
        # the lock guarantees the previous-epoch chain is always gapless.
        self.assertEqual(b2["manifest"]["state"]["previous_epoch"], e1)
        self.assertEqual(b2["manifest"]["state"]["previous_manifest_hash"],
                         b1["manifest"]["canonical_sha256"])
        self.assertEqual(b2["head"]["state"]["previous_epoch"], e1)

    def test_head_is_the_freshness_fetch(self):
        st, _, body = self.server.handle("GET", "/chunks/head.json")
        self.assertEqual(st, 200)
        head = json.loads(body.decode())
        self.assertTrue(verify_envelope(head))
        s = head["state"]
        self.assertEqual(s["schema"], HEAD_SCHEMA)
        cur = self.server._generations[self.server._current_epoch]
        self.assertEqual(s["manifest_hash"],
                         cur["manifest"]["canonical_sha256"])
        self.assertEqual(s["world_epoch"], cur["world_epoch"])
        # freshness classes name every dataset exactly once
        named = s["freshness_classes"]["long"] + s["freshness_classes"]["short"]
        self.assertEqual(sorted(named),
                         sorted(m["dataset"] for m in cur["datasets_meta"]))
        self.assertLess(len(body), 2048, "head stays tiny")

    def test_previous_manifest_servable_for_stale(self):
        prev = self.server._previous_epoch
        self.assertIsNotNone(prev)
        st, _, body = self.server.handle(
            "GET", "/chunks/manifest.json", query={"epoch": str(prev)})
        self.assertEqual(st, 200)
        m = json.loads(body.decode())
        self.assertTrue(verify_envelope(m))
        self.assertEqual(m["state"]["world_epoch"], prev)
        st, _, _ = self.server.handle(
            "GET", "/chunks/manifest.json", query={"epoch": "1"})
        # epoch 1 was superseded long ago (or never served here)
        if 1 not in self.server._generations:
            self.assertEqual(st, 404)

    def test_stream_version_pinned(self):
        cur = self.server._current_epoch
        st, headers, body = self.server.handle(
            "GET", "/stream", query={"priorities": "1,2,3,4"})
        self.assertEqual(st, 200)
        self.assertEqual(headers["x-world-epoch"], str(cur))
        epochs = set()
        order = []
        for line in body.decode().strip().split("\n"):
            env = json.loads(line)
            self.assertTrue(verify_envelope(env))
            epochs.add(env["state"]["world_epoch"])
            order.append((env["state"]["priority"], env["state"]["dataset"]))
        self.assertEqual(epochs, {cur}, "no epoch mixing inside a stream")
        self.assertEqual(order, sorted(order), "priority order in stream")

    def test_schema_policy_recorded(self):
        b = self.server._generations[self.server._current_epoch]
        policies = {m["dataset"]: m["schema_policy"]
                    for m in b["datasets_meta"]}
        # small registries purge; heavy/detail retain-stale for bedside cutover
        for d in ("doctrine", "chambers", "countries.coarse"):
            self.assertEqual(policies[d], POLICY_PURGE)
        for d in ("cities.full", "pricing", "economics.pricing"):
            self.assertEqual(policies[d], POLICY_RETAIN_STALE)

    def test_concurrent_cuts_serialize(self):
        # Regression: two overlapping cuts used to interleave
        # (bump 5, bump 6, built 5, built 6), corrupting the
        # previous-manifest chain. The build lock serializes cuts.
        # Cuts go through server.regenerate() — the server owns the cut
        # lifecycle, so its in-memory generations stay in sync with the
        # epoch file (bare build_all() would advance the file behind the
        # server's back).
        import threading

        def cut():
            self.server.regenerate()

        threads = [threading.Thread(target=cut) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        cur = self.server._current_epoch
        prev = self.server._previous_epoch
        self.assertIsNotNone(cur)
        self.assertIsNotNone(prev)
        self.assertEqual(cur, prev + 1,
                         "concurrent cuts must land on consecutive epochs")
        b = self.server._generations[cur]
        # gapless chain even under concurrency
        self.assertEqual(b["manifest"]["state"]["previous_epoch"], prev)
        self.assertEqual(
            b["manifest"]["state"]["previous_manifest_hash"],
            self.server._generations[prev]["manifest"]["canonical_sha256"])

    def test_schema_bump_recuts_with_new_version(self):
        v0 = chunks.read_schema_version()
        try:
            v1 = chunks.bump_schema_version(note="test cut")
            self.assertEqual(v1, v0 + 1)
            b = build_all()
            self.assertEqual(b["schema_version"], v1)
            for env in b["chunks_by_id"].values():
                self.assertEqual(env["state"]["schema_version"], v1)
            self.assertEqual(b["manifest"]["state"]["schema_version"], v1)
        finally:
            # restore: schema cuts are manual ops; tests must not leave one
            with open(chunks._schema_file(), "w") as fh:
                json.dump({"schema_version": v0}, fh)


class TestTieredFreshness(unittest.TestCase):
    """Trinity P0-3."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = build_all()

    def test_tiers_encoded_per_chunk_and_dataset(self):
        for cid, env in self.bundle["chunks_by_id"].items():
            f = env["state"]["freshness"]
            self.assertIn(f["tier"], (TIER_LONG, TIER_SHORT))
            self.assertIn(f["revalidate"], ("epoch", "every-load"))
            self.assertEqual(f["state"], FRESHNESS_CURRENT)
            self.assertTrue(f["as_of"])
        for meta in self.bundle["datasets_meta"]:
            entries = self.bundle["shard_entries"][meta["dataset"]]
            for e in entries:
                self.assertEqual(e["freshness_tier"], meta["freshness_tier"])

    def test_economic_data_is_short(self):
        tiers = {m["dataset"]: m["freshness_tier"]
                 for m in self.bundle["datasets_meta"]}
        self.assertEqual(tiers["pricing"], TIER_SHORT)
        self.assertEqual(tiers["economics.pricing"], TIER_SHORT)
        self.assertEqual(tiers["feeds"], TIER_SHORT)
        self.assertEqual(tiers["cities.full"], TIER_LONG)
        self.assertEqual(tiers["doctrine"], TIER_LONG)

    def test_wallet_never_chunked(self):
        datasets = [m["dataset"] for m in self.bundle["datasets_meta"]]
        self.assertNotIn("wallet-state", datasets)
        for cid in self.bundle["chunks_by_id"]:
            self.assertNotIn("wallet", cid)
        # the manifest says where the wallet lives instead
        self.assertIn("live-only",
                      self.bundle["manifest"]["state"]["wallet"])
        self.assertIn("live-only",
                      self.bundle["head"]["state"]["wallet"])

    def test_short_chunks_carry_as_of(self):
        env = self.bundle["chunks_by_id"][
            "pricing@shard-000001-of-000001"]
        self.assertEqual(env["state"]["freshness"]["tier"], TIER_SHORT)
        self.assertEqual(env["state"]["freshness"]["revalidate"], "every-load")


class TestServingProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ChunkServer()
        cls.server.regenerate()
        cur = cls.server._generations[cls.server._current_epoch]
        cls.any_chunk = next(iter(cur["chunks_by_id"]))

    def test_chunk_fetch_etag_range(self):
        s = self.server
        st, h, body = s.handle("GET", f"/chunks/{self.any_chunk}")
        self.assertEqual(st, 200)
        etag = h["etag"]
        st, _, b2 = s.handle("GET", f"/chunks/{self.any_chunk}",
                             headers={"if-none-match": etag})
        self.assertEqual(st, 304)
        self.assertEqual(b2, b"")
        st, h, b3 = s.handle("GET", f"/chunks/{self.any_chunk}",
                             headers={"range": "bytes=0-99"})
        self.assertEqual(st, 206)
        self.assertEqual(h["content-range"],
                         f"bytes 0-99/{len(body)}")
        self.assertEqual(b3, body[0:100])
        st, h, b4 = s.handle("GET", f"/chunks/{self.any_chunk}",
                             headers={"range": "bytes=-50"})
        self.assertEqual(st, 206)
        self.assertEqual(b4, body[-50:])
        st, _, _ = s.handle("GET", f"/chunks/{self.any_chunk}",
                            headers={"range": "bytes=99999999-"})
        self.assertEqual(st, 416)

    def test_unknown_chunk_and_path_404(self):
        s = self.server
        st, _, _ = s.handle("GET", "/chunks/nope@shard-000001-of-000001")
        self.assertEqual(st, 404)
        st, _, _ = s.handle("GET", "/nope")
        self.assertEqual(st, 404)

    def test_priority_selection(self):
        s = self.server
        st, _, body = s.handle("GET", "/chunks", query={"priorities": "1"})
        self.assertEqual(st, 200)
        idx = json.loads(body.decode())
        self.assertEqual(idx["count"], 3)  # doctrine, world-state, registry-summary
        self.assertTrue(all("@shard-" in c for c in idx["chunk_ids"]))

    def test_shard_manifest_paged_and_signed(self):
        s = self.server
        st, _, body = s.handle("GET", "/chunks/countries.full/shards.json",
                               query={"page": "0", "per": "1"})
        self.assertEqual(st, 200)
        sm = json.loads(body.decode())
        self.assertTrue(verify_envelope(sm))
        self.assertEqual(sm["state"]["schema"], SHARD_MANIFEST_SCHEMA)
        self.assertEqual(len(sm["state"]["shards"]), 1)
        self.assertEqual(sm["state"]["world_epoch"], s._current_epoch)

    def test_stream_priorities_filter(self):
        s = self.server
        st, h, body = s.handle("GET", "/stream", query={"priorities": "4"})
        self.assertEqual(st, 200)
        for line in body.decode().strip().split("\n"):
            env = json.loads(line)
            self.assertEqual(env["state"]["priority"], 4)


class TestRelayWrap(unittest.TestCase):
    def test_wrap_and_verify_roundtrip(self):
        bundle = build_all()
        cid = "doctrine@shard-000001-of-000001"
        chunk_env = bundle["chunks_by_id"][cid]
        unity_id = "unity:testnet:" + "ab" * 32
        # TEST-ONLY forged BOUND gate: exercises the relay's structural
        # checks, not the binding ceremony (that belongs to gate.py).
        gate = {
            "schema": "unity.gate.v1.testnet",
            "type": "GATE",
            "identity": unity_id,
            "state": "BOUND",
            "receipt_id": "test-receipt-chunks-1",
            "authorizes": "test wrap only",
            "issued_at": "2026-10-06T00:00:00Z",
        }
        wrapped = chunks.relay_wrap(chunk_env, unity_id, gate,
                                    reason="test chunk wrap")
        self.assertEqual(wrapped["envelope"], "EVIDENCE")
        self.assertEqual(wrapped["payload"]["state"]["chunk_id"], cid)
        tmp = "/tmp/chunk-wrap-test-bundle.json"
        _write_tmp(tmp, json.dumps(wrapped))
        proc = subprocess.run(["node", WRAP_HELPER, "verify", tmp],
                              capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertIn(cid, proc.stdout.decode())

    def test_wrap_rejects_chunk_missing_epoch(self):
        bundle = build_all()
        chunk_env = bundle["chunks_by_id"]["doctrine@shard-000001-of-000001"]
        tampered = {"state": {k: v for k, v in chunk_env["state"].items()
                              if k != "world_epoch"},
                    "canonical_sha256": chunk_env["canonical_sha256"],
                    "signature": chunk_env["signature"],
                    "algorithm": "Ed25519", "key_id": chunk_env["key_id"],
                    "provenance": "VERIFIED"}
        unity_id = "unity:testnet:" + "ab" * 32
        gate = {"schema": "unity.gate.v1.testnet", "type": "GATE",
                "identity": unity_id, "state": "BOUND",
                "receipt_id": "t", "authorizes": "t", "issued_at": "t"}
        with self.assertRaises(RuntimeError):
            chunks.relay_wrap(tampered, unity_id, gate)


class TestReceipts(unittest.TestCase):
    def test_epoch_build_receipted(self):
        log = chunks._receipt_log()
        before = os.path.getsize(log) if os.path.exists(log) else 0
        b = build_all()
        with open(log, encoding="utf-8") as fh:
            fh.seek(before)
            new_lines = [json.loads(l) for l in fh if l.strip()]
        kinds = {l["action"] for l in new_lines}
        self.assertIn("epoch_built", kinds)
        built = next(l for l in new_lines if l["action"] == "epoch_built")
        self.assertEqual(built["world_epoch"], b["world_epoch"])
        self.assertEqual(built["manifest_hash"],
                         b["manifest"]["canonical_sha256"])


if __name__ == "__main__":
    unittest.main()
