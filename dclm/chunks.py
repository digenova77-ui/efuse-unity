"""
DCLM CHUNKED DATA SERVING LAYER — streamable, priority-ordered data chunks
for the unity-world deployment.

David's hard rule: DCLM serves data in streamable chunks; the client caches
aggressively and renders progressively.

This module EXTENDS data.py (it does not rewrite it): every chunk is built
from data.py's loaders, so figures keep the labels data.py assigned them.
Chunking never strips or flattens provenance — each chunk body carries the
union of its figures' labels, and the manifests carry per-chunk labels.

Priorities (client fetches coarse first, detail after):
  P1 shell-critical  — doctrine, world-state, registry-summary
                       (wallet-state REMOVED 2026-10-06 per Trinity P0-3:
                       wallet is never chunked, always live server-round-trip)
  P2 coarse          — country summaries, chambers, jurisdictions, rtes,
                       canada, sectors, pharmacology
  P3 detail          — full cities, full countries, telemetrics, feeds,
                       verdicts, pricing index
  P4 bulk            — economics pricing index, mesh escrow state

READJUSTMENT PROTOCOL (Trinity P0-2, verdict 2026-10-06):
  * world_epoch: monotonic integer, bumped on every regeneration, persisted
    in chunk_epoch.json. Every chunk body, shard manifest, manifest, and
    head document carries it. The client enforces the no-downgrade rule:
    any head/chunk with world_epoch below the client's cached max is
    rejected — old-but-validly-signed chunks can never replay as current.
  * Version-pinned streams: the client records the head's world_epoch at
    stream start; every chunk in the stream must carry the same epoch or
    it is rejected. The client never mixes epochs without labeling.
  * Head document (/chunks/head.json): tiny signed doc fetched every load
    (world_epoch, schema_version, manifest hash). The only
    freshness-sensitive fetch; everything else is content-addressed.
  * Schema evolution: manifest carries schema_version; each dataset
    carries a schema_policy ("purge" or "retain-stale"). The thin client
    never migrates (client law: no computation) — purge drops the old
    namespace and re-streams; retain-stale keeps rendering the old world
    labeled STALE while the new epoch streams behind, then cuts over
    atomically.
  * STALE state: a freshness state (not a provenance label). The server
    retains the previous epoch's signed manifest so STALE chunks stay
    verifiable during transition. Hash verification happens on READ.

TIERED FRESHNESS (Trinity P0-3, verdict 2026-10-06):
  * tier "long"  — geometry + reference telemetry: cache aggressively,
    revalidate on epoch change only.
  * tier "short" — economic data (prices, Merit-adjacent): revalidate
    against the head on every load; as_of timestamp on the chunk; the
    client renders as-of + STALE badge past revalidation.
  * wallet       — NEVER chunked. Always live via POST /api/world/*.
    The manifest says so explicitly.
  Freshness tier is encoded per dataset in the manifest and per chunk in
  the chunk body. TTLs are advisory; ENFORCEMENT is epoch-based (no wall
  clock — verdict: clock skew must not decide freshness).

Scale contract:
  * Every chunk's DATA payload is bounded by MAX_CHUNK_BYTES (256 KiB).
    Total data volume changes the shard COUNT, never the shard size.
  * The top manifest lists DATASETS only (never individual shards), so it
    stays small at any scale. Per-dataset shard listings are paged
    (/chunks/<dataset>/shards.json?page=N&per=M), also signed.
  * Chunk ids are deterministic: <dataset>@shard-<nnnnnn>-of-<nnnnnn>.

Every chunk is DCLM-signed (compute.sign_state, Ed25519, testnet key) and
carries its own content hash. The client verifies:
  1. the Ed25519 signature over the chunk body (relay boundary), and
  2. body.content_hash == sha256(canonical(body.data)) (integrity).

Chunks are relay bundles: relay/wrap-chunk.mjs wraps any signed chunk
envelope into a dualis.relay.v1.testnet EVIDENCE bundle for a BOUND
identity. The chunk endpoint itself is the free-to-look data plane
(world viewing needs no binding — gate.py's reframe); the relay wrap is
for metered flows to bound identities.

Testnet only. UNKNOWN is never PASS. Every mutation (regeneration) is
receipted to chunk_receipts.log (JSONL, before/after manifest hashes).
"""

import hashlib
import json
import os
import sys
import time

try:
    import fcntl
except ImportError:  # pragma: no cover — Linux-only deployment
    fcntl = None

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import data as _data  # noqa: E402  (extends data.py; does not rewrite it)
from compute import (  # noqa: E402
    KEY_ID,
    _canonical_bytes,
    sign_state,
    verify_envelope,
)

FIGURE_LABELS = _data.FIGURE_LABELS

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
CHUNK_SCHEMA = "dualis.chunk.v1.testnet"
SHARD_MANIFEST_SCHEMA = "dualis.chunk.shards.v1.testnet"
MANIFEST_SCHEMA = "dualis.chunk.manifest.v1.testnet"
HEAD_SCHEMA = "dualis.chunk.head.v1.testnet"

# Chunk content-schema version. Bumped only by bump_schema_version(); every
# chunk body, shard manifest, manifest, and head carries it so the client
# can apply the per-dataset schema_policy on a cut.
SCHEMA_VERSION = 1

# Hard bound on a chunk's DATA payload. Volume changes shard count, never
# shard size: 300MB -> ~1,200 shards; 2GB -> ~8,200; 5TB -> ~20M.
MAX_CHUNK_BYTES = 256 * 1024

RECEIPT_LOG = os.path.join(_HERE, "chunk_receipts.log")
EPOCH_FILE = os.path.join(_HERE, "chunk_epoch.json")
PREV_MANIFEST_FILE = os.path.join(_HERE, "chunk_prev_manifest.json")
LOCK_FILE = os.path.join(_HERE, "chunk_build.lock")
SCHEMA_FILE = os.path.join(_HERE, "chunk_schema.json")


def _state_dir():
    """Directory holding chunk server state. CHUNK_STATE_DIR overrides it
    (tests point it at a temp dir for hermetic runs — no shared mutable
    state with other workers' builds)."""
    return os.environ.get("CHUNK_STATE_DIR", _HERE)


def _receipt_log():
    return os.path.join(_state_dir(), "chunk_receipts.log")


def _epoch_file():
    return os.path.join(_state_dir(), "chunk_epoch.json")


def _prev_manifest_file():
    return os.path.join(_state_dir(), "chunk_prev_manifest.json")


def _lock_file():
    return os.path.join(_state_dir(), "chunk_build.lock")


def _schema_file():
    return os.path.join(_state_dir(), "chunk_schema.json")

PRIORITY_NAMES = {
    1: "shell-critical",
    2: "coarse",
    3: "detail",
    4: "bulk",
}

# Freshness states (a freshness dimension, NOT a provenance label —
# compute.py's PROVENANCE_LABELS enum is untouched).
FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_STATES = frozenset({FRESHNESS_CURRENT, FRESHNESS_STALE})

# Freshness tiers (Trinity P0-3). Enforcement is epoch-based, never wall
# clock: "long" revalidates on epoch change; "short" revalidates against
# the head on every load and carries as_of for the STALE badge.
TIER_LONG = "long"
TIER_SHORT = "short"

# Schema policies per dataset (Trinity P0-2 §3). "purge": drop the old
# namespace and re-stream on a schema cut. "retain-stale": keep rendering
# the old epoch labeled STALE while the new epoch streams behind, then
# atomic cutover. The thin client never migrates bytes itself.
POLICY_PURGE = "purge"
POLICY_RETAIN_STALE = "retain-stale"


# ---------------------------------------------------------------------------
# sharding — the scale mechanism
# ---------------------------------------------------------------------------
def _shard_items(items, max_bytes=MAX_CHUNK_BYTES):
    """Split a list of JSON-serializable items into byte-bounded shards.

    Greedy accumulation over canonical JSON bytes: each shard's canonical
    payload stays under max_bytes. Returns [(items, oversize_flag), ...].
    A single item that alone meets/exceeds max_bytes gets its own shard
    with oversize=True — flagged, never silently dropped, never split.
    """
    shards = []
    cur, cur_bytes = [], 2  # b"[]"
    for item in items:
        ib = _canonical_bytes(item)
        n = len(ib)
        if n >= max_bytes:
            if cur:
                shards.append((cur, False))
                cur, cur_bytes = [], 2
            shards.append(([item], True))
            continue
        add = n + (1 if cur else 0)  # comma separator
        if cur_bytes + add > max_bytes:
            shards.append((cur, False))
            cur, cur_bytes = [], 2
            add = n
        cur.append(item)
        cur_bytes += add
    if cur:
        shards.append((cur, False))
    return shards


def _chunk_id(dataset, index, total):
    return f"{dataset}@shard-{index + 1:06d}-of-{total:06d}"


# ---------------------------------------------------------------------------
# dataset builders — each returns (payload, labels)
# payload is a list (shardable) or a dict (single chunk).
# labels is the set of figure labels present in the payload.
# ---------------------------------------------------------------------------
def _b_doctrine():
    d = _data.load_registry("doctrine")
    return d, {"REPORTED"}


# _b_wallet_state was REMOVED 2026-10-06 (Trinity P0-3): wallet is never
# chunked, always live. Wallet state flows only via POST /api/world/*
# server-round-trip, exactly as the ratified thin client already does.
# A stale cached price is a financial hazard (Merit is transferable);
# geometry can go stale visibly, money cannot.

def _b_world_state():
    state = _data.serve_world_state()
    labels = set()
    for v in state["verdicts"]:
        labels.add(v["provenance"])
    labels.add(state["registry_digest"]["provenance"])
    labels.add(state["purity_pulse"]["provenance"])
    for entry in state["feed_status"].values():
        labels.add(entry["provenance"])
    return state, labels


def _b_registry_summary():
    summary = _data.registry_summary()
    labels = {"REPORTED"}
    # registry_summary marks missing datasets UNKNOWN — carry that honestly.
    for entry in summary.values():
        labels.add(entry.get("provenance", "UNKNOWN"))
    return summary, labels


def _b_countries_coarse():
    d = _data.load_registry("countries")
    coarse = [
        {"a3": c["a3"], "name": c["name"], "continent": c.get("continent")}
        for c in d["countries"]
    ]
    return coarse, {"REPORTED"}


def _registry_list(name, label="REPORTED"):
    return _data.load_registry(name), {label}


def _b_cities_full():
    d = _data.load_registry("cities")
    return d["cities"], {"REPORTED"}


def _b_countries_full():
    d = _data.load_registry("countries")
    return d["countries"], {"REPORTED"}


def _b_telemetrics():
    t = _data.rte_telemetry()
    return t["rows"], {r["label"] for r in t["rows"]}


def _b_feeds():
    feeds = _data.feed_registry()
    # PENDING feeds: UNKNOWN is never PASS — status rides along, unlabeled
    # readings stay null.
    return list(feeds.values()), {"UNKNOWN"}


def _b_verdicts():
    verdicts = _data.factory_verdicts()
    labels = {v.get("provenance", "UNKNOWN") for v in verdicts} or {"UNKNOWN"}
    return verdicts, labels


def _b_pricing():
    p = _data.pricing_index()
    labels = set()
    for r in p["rows"]:
        labels.add(r.get("provenance", "UNKNOWN"))
        for f in r.get("figures", []):
            labels.add(f.get("label", "UNKNOWN"))
    return p["rows"], labels or {"UNKNOWN"}


def _b_economics_pricing():
    """P4 bulk: the economics pricing engine's full decision index.

    Real economic data with per-figure custody labels (normalized to the
    DCLM label set). Fail-soft: if the economics module is unavailable the
    dataset goes PENDING/UNKNOWN instead of breaking the whole build —
    nothing invented either way.
    """
    econ_dir = os.path.normpath(os.path.join(_HERE, "..", "economics"))
    try:
        if econ_dir not in sys.path:
            sys.path.insert(0, econ_dir)
        import pricing as econ_pricing  # noqa: E402
    except Exception as exc:
        return {
            "status": "PENDING",
            "note": f"economics pricing index unavailable: {exc}",
            "provenance": "UNKNOWN",
        }, {"UNKNOWN"}
    rows, labels = [], set()
    for r in econ_pricing.INDEX:
        row = dict(r)
        row_figs = []
        for f in r.get("figures", []):
            try:
                label = econ_pricing.normalize_label(f.get("custody"))
            except Exception:
                label = "UNKNOWN"
            labels.add(label)
            row_figs.append({**f, "label": label})
        row["figures"] = row_figs
        rows.append(row)
    return rows, labels or {"UNKNOWN"}


def _b_mesh_bulk():
    """P4 bulk slot: mesh escrow state.

    Honest PENDING stub — the mesh clearing state is not yet served on
    this side, so the slot exists (priority 4, provenance UNKNOWN) with
    zero invented data. When the mesh pipeline lands, this builder starts
    emitting sharded chunks and the slot flips without protocol changes.
    """
    return {
        "status": "PENDING",
        "note": "mesh escrow state not yet served on this side — slot reserved",
        "provenance": "UNKNOWN",
    }, {"UNKNOWN"}


# dataset -> (priority, builder, freshness_tier, schema_policy).
# Order here is the manifest order within a priority (dataset name tiebreak).
# Freshness (P0-3): geometry + reference telemetry = long; economic data =
# short (revalidate every load, as_of on the chunk). Wallet is absent by
# law — never chunked, always live.
DATASET_PLAN = [
    # P1 — shell-critical
    (1, "doctrine", _b_doctrine, TIER_LONG, POLICY_PURGE),
    (1, "world-state", _b_world_state, TIER_LONG, POLICY_RETAIN_STALE),
    (1, "registry-summary", _b_registry_summary, TIER_LONG, POLICY_PURGE),
    # P2 — coarse registries (geometry-ish: long-lived, purge-and-restream)
    (2, "countries.coarse", _b_countries_coarse, TIER_LONG, POLICY_PURGE),
    (2, "chambers", lambda: _registry_list("chambers"), TIER_LONG, POLICY_PURGE),
    (2, "jurisdictions", lambda: _registry_list("jurisdictions"), TIER_LONG, POLICY_PURGE),
    (2, "rtes", lambda: _registry_list("rtes"), TIER_LONG, POLICY_PURGE),
    (2, "canada", lambda: _registry_list("canada"), TIER_LONG, POLICY_PURGE),
    (2, "sectors", lambda: _registry_list("sectors"), TIER_LONG, POLICY_PURGE),
    (2, "pharmacology", lambda: _registry_list("pharmacology"), TIER_LONG, POLICY_PURGE),
    # P3 — detail
    (3, "cities.full", _b_cities_full, TIER_LONG, POLICY_RETAIN_STALE),
    (3, "countries.full", _b_countries_full, TIER_LONG, POLICY_RETAIN_STALE),
    (3, "telemetrics", _b_telemetrics, TIER_LONG, POLICY_RETAIN_STALE),
    (3, "feeds", _b_feeds, TIER_SHORT, POLICY_RETAIN_STALE),
    (3, "verdicts", _b_verdicts, TIER_LONG, POLICY_RETAIN_STALE),
    (3, "pricing", _b_pricing, TIER_SHORT, POLICY_RETAIN_STALE),
    # P4 — bulk (economic data: short TTL; mesh slot PENDING)
    (4, "economics.pricing", _b_economics_pricing, TIER_SHORT, POLICY_RETAIN_STALE),
    (4, "mesh.bulk", _b_mesh_bulk, TIER_SHORT, POLICY_RETAIN_STALE),
]
DATASET_PLAN.sort(key=lambda t: (t[0], t[1]))


# ---------------------------------------------------------------------------
# chunk construction
# ---------------------------------------------------------------------------
def _dominant_label(labels):
    """One summary label per chunk; the full union rides alongside."""
    if len(labels) == 1:
        return next(iter(labels))
    # mixed: prefer the most informative claim, never upgrade UNKNOWN.
    for cand in ("REAL", "VERIFIED", "REPORTED", "MODELED", "DERIVED"):
        if cand in labels:
            return cand
    return "UNKNOWN"


def build_dataset_chunks(dataset, priority, builder, max_bytes=MAX_CHUNK_BYTES,
                         world_epoch=0, freshness_tier=TIER_LONG,
                         schema_policy=POLICY_PURGE, schema_version=None):
    """Build all signed chunks for one dataset.

    Returns (chunk_envelopes, shard_entries). Each envelope is
    compute.sign_state(chunk_body); each shard entry is the manifest row.
    Every chunk body carries world_epoch + schema_version (rollback
    defense: the client rejects epochs below its cached max) and the
    freshness contract (tier, revalidation rule, as_of).
    """
    sv = schema_version if schema_version is not None else read_schema_version()
    payload, labels = builder()
    labels = {l for l in labels if l in FIGURE_LABELS} or {"UNKNOWN"}
    dominant = _dominant_label(labels)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if isinstance(payload, list):
        shard_payloads = _shard_items(payload, max_bytes)
    else:
        shard_payloads = [([payload], False)]
        # dict payloads are single chunks; represent data as the dict itself
        # (the list wrapper is only for the sharding path).

    total = len(shard_payloads)
    envelopes, entries = [], []
    for i, (items, oversize) in enumerate(shard_payloads):
        data = items[0] if (not isinstance(payload, list) and len(items) == 1) else items
        data_bytes = _canonical_bytes(data)
        body = {
            "schema": CHUNK_SCHEMA,
            "schema_version": sv,
            "world_epoch": world_epoch,
            "chunk_id": _chunk_id(dataset, i, total),
            "dataset": dataset,
            "priority": priority,
            "priority_name": PRIORITY_NAMES[priority],
            "index": i,
            "of": total,
            "item_count": len(items) if isinstance(payload, list) else 1,
            "data_bytes": len(data_bytes),
            "content_hash": hashlib.sha256(data_bytes).hexdigest(),
            "provenance": dominant,
            "provenance_labels": sorted(labels),
            "freshness": {
                "tier": freshness_tier,
                # Enforcement is epoch-based, never wall clock (clock skew
                # must not decide freshness — Trinity verdict).
                # long: render from cache, revalidate on epoch change.
                # short: revalidate against the head on every load; as_of
                # rides the chunk so the client can badge STALE honestly.
                "revalidate": ("epoch" if freshness_tier == TIER_LONG
                               else "every-load"),
                "as_of": generated_at,
                "state": FRESHNESS_CURRENT,
            },
            "schema_policy": schema_policy,
            "oversize_item": oversize,
            "generated_at": generated_at,
            "key_id": KEY_ID,
            "data": data,
        }
        envelope = sign_state(body)
        env_bytes = _canonical_bytes(envelope)
        envelopes.append(envelope)
        entries.append({
            "chunk_id": body["chunk_id"],
            "index": i,
            "world_epoch": world_epoch,
            "item_count": body["item_count"],
            "data_bytes": body["data_bytes"],
            "byte_size": len(env_bytes),
            "envelope_hash": envelope["canonical_sha256"],
            "data_hash": body["content_hash"],
            "provenance": dominant,
            "provenance_labels": sorted(labels),
            "freshness_tier": freshness_tier,
            "oversize_item": oversize,
        })
    return envelopes, entries


def build_manifest(datasets_meta, max_bytes=MAX_CHUNK_BYTES, world_epoch=0,
                   prev_epoch=None, prev_manifest_hash=None,
                   schema_version=None):
    """Top-level manifest: DATASETS only — never individual shards.

    Per-dataset: priority, shard count, total bytes, dataset_hash (hash of
    the concatenated shard envelope hashes), provenance label union,
    freshness tier, schema policy. Carries world_epoch + schema_version
    for atomic version cuts, and the previous epoch's manifest hash so the
    client can validate STALE chunks during transition.
    Signed with the testnet key. Stays small at any data volume.
    """
    ds_rows = []
    total_chunks = 0
    total_bytes = 0
    for meta in datasets_meta:
        ds_rows.append({
            "dataset": meta["dataset"],
            "priority": meta["priority"],
            "priority_name": PRIORITY_NAMES[meta["priority"]],
            "shards": meta["shards"],
            "total_bytes": meta["total_bytes"],
            "dataset_hash": meta["dataset_hash"],
            "provenance": meta["provenance"],
            "provenance_labels": meta["provenance_labels"],
            "freshness_tier": meta["freshness_tier"],
            "schema_policy": meta["schema_policy"],
            "status": meta["status"],
        })
        total_chunks += meta["shards"]
        total_bytes += meta["total_bytes"]
    ds_rows.sort(key=lambda r: (r["priority"], r["dataset"]))
    sv = schema_version if schema_version is not None else read_schema_version()
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": sv,
        "world_epoch": world_epoch,
        "previous_epoch": prev_epoch,
        "previous_manifest_hash": prev_manifest_hash,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "key_id": KEY_ID,
        "max_chunk_bytes": max_bytes,
        "testnet": True,
        # Wallet is never chunked (Trinity P0-3): always live, server
        # round-trip. The manifest states this so no client goes looking.
        "wallet": "live-only — never chunked; use POST /api/world/*",
        "total_chunks": total_chunks,
        "total_bytes": total_bytes,
        "datasets": ds_rows,
    }
    return sign_state(manifest)


def build_head(manifest_envelope, world_epoch, prev_epoch=None,
               prev_manifest_hash=None, schema_version=None):
    """The head document: the ONLY freshness-sensitive fetch.

    Tiny, signed, fetched on every load: world_epoch, schema_version, the
    manifest's hash, previous-epoch markers for STALE validation, and the
    freshness class listing. Everything else is content-addressed and
    immutable — the head tells the client whether its cache is current.
    """
    m = manifest_envelope["state"]
    freshness_classes = {"long": [], "short": []}
    for ds in m["datasets"]:
        freshness_classes[ds["freshness_tier"]].append(ds["dataset"])
    sv = schema_version if schema_version is not None else read_schema_version()
    head = {
        "schema": HEAD_SCHEMA,
        "schema_version": sv,
        "world_epoch": world_epoch,
        "manifest_hash": manifest_envelope["canonical_sha256"],
        "previous_epoch": prev_epoch,
        "previous_manifest_hash": prev_manifest_hash,
        "dataset_count": len(m["datasets"]),
        "total_chunks": m["total_chunks"],
        "total_bytes": m["total_bytes"],
        "freshness_classes": freshness_classes,
        "wallet": "live-only — never chunked",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "key_id": KEY_ID,
    }
    return sign_state(head)


def build_shard_manifest(dataset, priority, shard_entries, page=0, per=1000,
                         world_epoch=0, schema_version=None):
    """Paged, signed shard listing for one dataset.

    The client fetches this lazily per dataset; pages keep any single
    response bounded even when a dataset holds millions of shards.
    Version-pinned: carries world_epoch so a stream can complete against
    the head it started with — no v1/v2 mixing.
    """
    total = len(shard_entries)
    pages = max(1, (total + per - 1) // per)
    page = max(0, min(page, pages - 1))
    sv = schema_version if schema_version is not None else read_schema_version()
    body = {
        "schema": SHARD_MANIFEST_SCHEMA,
        "schema_version": sv,
        "world_epoch": world_epoch,
        "dataset": dataset,
        "priority": priority,
        "priority_name": PRIORITY_NAMES[priority],
        "total_shards": total,
        "page": page,
        "per": per,
        "pages": pages,
        "shards": shard_entries[page * per:(page + 1) * per],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "key_id": KEY_ID,
    }
    return sign_state(body)


# ---------------------------------------------------------------------------
# epoch + schema-version management (rollback defense)
# ---------------------------------------------------------------------------


def _read_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return default


class _BuildLock:
    """Cross-process exclusive lock for epoch cuts.

    Two concurrent regenerations used to interleave (bump 5, bump 6,
    built 5, built 6) — epochs stayed monotonic in the file but the
    slower build overwrote the previous-manifest pointer and broke the
    chain. The whole cut (bump -> sign -> write prev manifest -> receipt)
    now holds this lock. Same-process re-entry is allowed (threading
    RLock); cross-process exclusion is via flock.
    """

    def __init__(self):
        import threading
        self._local = threading.RLock()
        self._depth = 0
        self._fh = None

    def __enter__(self):
        self._local.acquire()
        if self._depth == 0 and fcntl is not None:
            self._fh = open(_lock_file(), "w")
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        self._depth += 1
        return self

    def __exit__(self, *exc):
        self._depth -= 1
        if self._depth == 0 and self._fh is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None
        self._local.release()
        return False


_BUILD_LOCK = _BuildLock()


def read_epoch():
    """Current world_epoch (0 = never built). Monotonic; never decremented."""
    return int(_read_json_file(_epoch_file(), {"world_epoch": 0})["world_epoch"])


def read_schema_version():
    return int(_read_json_file(_schema_file(), {"schema_version": 1})["schema_version"])


def _log_receipt(entry):
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "key_id": KEY_ID, **entry}
    with open(_receipt_log(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def bump_epoch():
    """Increment the world epoch. Every regeneration is a new epoch; the
    client no-downgrade rule makes old epochs unreplayable as current.
    Holds the build lock: the bump is part of the atomic cut."""
    with _BUILD_LOCK:
        n = read_epoch() + 1
        with open(_epoch_file(), "w", encoding="utf-8") as fh:
            json.dump({"world_epoch": n}, fh)
        _log_receipt({"action": "epoch_bumped", "world_epoch": n})
        return n


def bump_schema_version(note=""):
    """Cut a new chunk schema version. Records the per-dataset policy
    application; clients apply purge vs retain-stale per dataset."""
    v = read_schema_version() + 1
    with open(_schema_file(), "w", encoding="utf-8") as fh:
        json.dump({"schema_version": v, "note": note}, fh)
    policies = {d: p for _, d, _, _, p in DATASET_PLAN}
    _log_receipt({"action": "schema_version_bumped", "schema_version": v,
                  "note": note, "policies": policies})
    return v


# ---------------------------------------------------------------------------
# build_all — one atomic version cut
# ---------------------------------------------------------------------------
def build_all(max_bytes=MAX_CHUNK_BYTES, epoch=None):
    """Build every chunk, shard manifest, manifest, and head for one epoch.

    The epoch bump IS the version cut: all chunks in the cut carry the
    same world_epoch, so a stream pinned to the head it started with can
    never mix versions. The previous manifest is retained for STALE
    validation during transition.
    Returns the bundle dict; also receipts the mutation (before/after
    manifest hashes).

    The entire cut holds the cross-process build lock: bump, signing,
    previous-manifest write, and receipt are atomic against concurrent
    regenerations. Without this, two overlapping cuts interleave epochs
    and corrupt the previous-manifest chain (caught 2026-10-06).
    """
    with _BUILD_LOCK:
        return _build_all_locked(max_bytes=max_bytes, epoch=epoch)


def _build_all_locked(max_bytes=MAX_CHUNK_BYTES, epoch=None):
    """build_all body. Caller must hold _BUILD_LOCK."""
    schema_version = read_schema_version()
    prev_manifest = _read_json_file(_prev_manifest_file(), None)
    if epoch is None:
        epoch = bump_epoch()
    prev_epoch = (prev_manifest["state"]["world_epoch"]
                  if prev_manifest else None)
    prev_manifest_hash = (prev_manifest["canonical_sha256"]
                          if prev_manifest else None)

    chunks_by_id = {}
    shard_entries = {}
    datasets_meta = []
    for priority, dataset, builder, tier, policy in DATASET_PLAN:
        envelopes, entries = build_dataset_chunks(
            dataset, priority, builder, max_bytes=max_bytes,
            world_epoch=epoch, freshness_tier=tier, schema_policy=policy,
            schema_version=schema_version)
        for env in envelopes:
            chunks_by_id[env["state"]["chunk_id"]] = env
        shard_entries[dataset] = entries
        labels = set()
        for e in entries:
            labels.update(e["provenance_labels"])
        first_data = envelopes[0]["state"]["data"]
        status = ("PENDING" if isinstance(first_data, dict)
                  and first_data.get("status") == "PENDING" else "CURRENT")
        datasets_meta.append({
            "dataset": dataset,
            "priority": priority,
            "shards": len(entries),
            "total_bytes": sum(e["byte_size"] for e in entries),
            "dataset_hash": hashlib.sha256(
                "".join(e["envelope_hash"] for e in entries).encode()
            ).hexdigest(),
            "provenance": _dominant_label(labels),
            "provenance_labels": sorted(labels),
            "freshness_tier": tier,
            "schema_policy": policy,
            "status": status,
        })

    manifest = build_manifest(
        datasets_meta, max_bytes, epoch, prev_epoch, prev_manifest_hash,
        schema_version=schema_version)
    head = build_head(manifest, epoch, prev_epoch, prev_manifest_hash,
                      schema_version=schema_version)

    # Retain this manifest as the previous generation's for the next cut.
    with open(_prev_manifest_file(), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)

    _log_receipt({
        "action": "epoch_built",
        "world_epoch": epoch,
        "schema_version": schema_version,
        "previous_epoch": prev_epoch,
        "manifest_hash": manifest["canonical_sha256"],
        "previous_manifest_hash": prev_manifest_hash,
        "chunk_count": len(chunks_by_id),
        "total_bytes": sum(m["total_bytes"] for m in datasets_meta),
        "datasets": [m["dataset"] for m in datasets_meta],
    })
    return {
        "world_epoch": epoch,
        "schema_version": schema_version,
        "manifest": manifest,
        "head": head,
        "chunks_by_id": chunks_by_id,
        "shard_entries": shard_entries,
        "datasets_meta": datasets_meta,
    }


# ---------------------------------------------------------------------------
# ChunkServer — the serving protocol
# ---------------------------------------------------------------------------
# Endpoints (all GET unless noted):
#   /chunks/head.json                        signed head (freshness-sensitive)
#   /chunks/manifest.json[?epoch=N]          signed dataset manifest
#   /chunks/<dataset>/shards.json[?page=&per=&epoch=]  paged shard listing
#   /chunks/<chunk_id>[?epoch=]              signed chunk envelope
#       Range: bytes=A-B -> 206 partial; ETag + If-None-Match -> 304
#   /chunks?priorities=1,2[&epoch=]          chunk ids in fetch order
#   /stream?priorities=1,2[&epoch=][&datasets=a,b]
#       NDJSON: one signed chunk envelope per line, priority order,
#       version-pinned to the requested (or current) epoch.
#
# Two generations are retained: current + previous. The previous epoch's
# manifest stays servable so STALE chunks remain verifiable during the
# transition window (Trinity P0-2 §4).
import re as _re

_RANGE_RE = _re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header_value, total):
    """Parse a single Range header. Returns (start, end) inclusive or None
    (None = unsatisfiable/malformed -> 416). Multiple ranges unsupported."""
    if not header_value:
        return None
    m = _RANGE_RE.match(header_value.strip())
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if a == "" and b == "":
        return None
    if a == "":
        # suffix: last N bytes
        n = int(b)
        if n <= 0:
            return None
        start = max(0, total - n)
        return (start, total - 1)
    start = int(a)
    end = int(b) if b != "" else total - 1
    if start >= total or end < start:
        return None
    return (start, min(end, total - 1))


class ChunkServer:
    """In-process chunk server. Framework-free handle() returns
    (status, headers, body_bytes); wire it into any HTTP layer.

    The server owns the cut lifecycle: every epoch cut goes through
    regenerate(), which holds the cross-process build lock AND a
    thread lock around the in-memory generation swap, so concurrent
    regenerations (threads or processes) can neither interleave epochs
    nor corrupt the previous-generation chain."""

    def __init__(self):
        import threading
        self._generations = {}  # epoch -> build_all() bundle
        self._current_epoch = None
        self._previous_epoch = None
        self._swap_lock = threading.Lock()

    # -- lifecycle ------------------------------------------------------
    def regenerate(self, max_bytes=MAX_CHUNK_BYTES):
        """Cut a new epoch: build everything, shift generations, receipt.

        The build itself is serialized cross-process by the build lock;
        the in-memory generation swap is guarded by a thread lock so two
        concurrent regenerations can't interleave the previous/current
        pointers."""
        bundle = build_all(max_bytes=max_bytes)
        epoch = bundle["world_epoch"]
        with self._swap_lock:
            self._previous_epoch = self._current_epoch
            self._current_epoch = epoch
            self._generations[epoch] = bundle
            # retain only current + previous
            for e in [e for e in self._generations if e not in
                      (self._current_epoch, self._previous_epoch)]:
                del self._generations[e]
        return bundle

    def _gen(self, epoch=None):
        try:
            epoch = self._current_epoch if epoch is None else int(epoch)
        except (TypeError, ValueError):
            return None, None
        bundle = self._generations.get(epoch)
        return epoch, bundle

    # -- request handling -----------------------------------------------
    def handle(self, method, path, headers=None, query=None):
        """(status, headers_dict, body_bytes). Never raises on bad input."""
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        query = query or {}
        try:
            if method not in ("GET", "HEAD"):
                return 405, {}, b"method not allowed"
            if path == "/chunks/head.json":
                _, bundle = self._gen()
                if bundle is None:
                    return self._err(503, "no epoch built yet")
                return self._json(bundle["head"], headers, method)
            if path == "/chunks/manifest.json":
                epoch, bundle = self._gen(query.get("epoch"))
                if bundle is None:
                    return self._err(404, "unknown epoch")
                return self._json(bundle["manifest"], headers, method)
            if path == "/chunks":
                return self._chunk_index(query)
            if path == "/stream":
                return self._stream(query)
            m = _re.match(r"^/chunks/([^/]+)/shards\.json$", path)
            if m:
                return self._shard_page(m.group(1), query, headers, method)
            m = _re.match(r"^/chunks/([^/]+)$", path)
            if m:
                return self._serve_chunk(m.group(1), query, headers, method)
            return self._err(404, "unknown path")
        except Exception as exc:  # fail-closed, never a half-response
            return self._err(500, f"server error: {exc}")

    # -- responses ------------------------------------------------------
    @staticmethod
    def _err(status, reason):
        body = json.dumps({"ok": False, "reason": reason}).encode()
        return status, {"content-type": "application/json"}, body

    def _json(self, envelope, headers, method):
        body = _canonical_bytes(envelope)
        etag = f'"{envelope["canonical_sha256"]}"'
        if headers.get("if-none-match") == etag:
            return 304, {"etag": etag}, b""
        resp = {"content-type": "application/json",
                "etag": etag,
                "cache-control": "public, immutable",
                "accept-ranges": "bytes",
                "content-length": str(len(body))}
        return 200, resp, (b"" if method == "HEAD" else body)

    def _serve_chunk(self, chunk_id, query, headers, method):
        epoch, bundle = self._gen(query.get("epoch"))
        if bundle is None:
            return self._err(404, "unknown epoch")
        env = bundle["chunks_by_id"].get(chunk_id)
        if env is None:
            return self._err(404, f"unknown chunk {chunk_id}")
        body = _canonical_bytes(env)
        etag = f'"{env["canonical_sha256"]}"'
        if headers.get("if-none-match") == etag:
            return 304, {"etag": etag}, b""
        total = len(body)
        rng = headers.get("range")
        if rng:
            parsed = _parse_range(rng, total)
            if parsed is None:
                return (416, {"content-range": f"bytes */{total}"}, b"")
            start, end = parsed
            part = body[start:end + 1]
            resp = {"content-type": "application/json",
                    "etag": etag,
                    "accept-ranges": "bytes",
                    "content-range": f"bytes {start}-{end}/{total}",
                    "content-length": str(len(part))}
            return 206, resp, (b"" if method == "HEAD" else part)
        resp = {"content-type": "application/json",
                "etag": etag,
                "cache-control": "public, immutable",
                "accept-ranges": "bytes",
                "content-length": str(total)}
        return 200, resp, (b"" if method == "HEAD" else body)

    def _shard_page(self, dataset, query, headers, method):
        epoch, bundle = self._gen(query.get("epoch"))
        if bundle is None:
            return self._err(404, "unknown epoch")
        entries = bundle["shard_entries"].get(dataset)
        if entries is None:
            return self._err(404, f"unknown dataset {dataset}")
        meta = next(m for m in bundle["datasets_meta"]
                    if m["dataset"] == dataset)
        page = int(query.get("page", 0))
        per = min(int(query.get("per", 1000)), 5000)
        env = build_shard_manifest(dataset, meta["priority"], entries,
                                   page=page, per=per, world_epoch=epoch,
                                   schema_version=bundle["schema_version"])
        return self._json(env, headers, method)

    def _chunk_index(self, query):
        epoch, bundle = self._gen(query.get("epoch"))
        if bundle is None:
            return self._err(404, "unknown epoch")
        pris = query.get("priorities")
        want = ({int(p) for p in pris.split(",")} if pris else {1, 2, 3, 4})
        ids, total = [], 0
        for meta in sorted(bundle["datasets_meta"],
                           key=lambda m: (m["priority"], m["dataset"])):
            if meta["priority"] not in want:
                continue
            for e in bundle["shard_entries"][meta["dataset"]]:
                ids.append(e["chunk_id"])
                total += e["byte_size"]
        body = json.dumps({"world_epoch": epoch, "chunk_ids": ids,
                           "count": len(ids), "total_bytes": total}).encode()
        return 200, {"content-type": "application/json",
                     "content-length": str(len(body))}, body

    def _stream(self, query):
        """NDJSON: one signed chunk envelope per line, priority order,
        version-pinned to a single epoch. The client records the head epoch
        at stream start and rejects lines from any other epoch."""
        epoch, bundle = self._gen(query.get("epoch"))
        if bundle is None:
            return self._err(404, "unknown epoch")
        pris = query.get("priorities")
        want_p = ({int(p) for p in pris.split(",")} if pris else {1, 2, 3, 4})
        want_d = (set(query["datasets"].split(",")) if query.get("datasets")
                  else None)
        lines = []
        for meta in sorted(bundle["datasets_meta"],
                           key=lambda m: (m["priority"], m["dataset"])):
            if meta["priority"] not in want_p:
                continue
            if want_d is not None and meta["dataset"] not in want_d:
                continue
            for e in bundle["shard_entries"][meta["dataset"]]:
                env = bundle["chunks_by_id"][e["chunk_id"]]
                assert env["state"]["world_epoch"] == epoch, \
                    "epoch leak inside a pinned stream"
                lines.append(_canonical_bytes(env))
        body = b"\n".join(lines) + (b"\n" if lines else b"")
        return 200, {"content-type": "application/x-ndjson",
                     "x-world-epoch": str(epoch),
                     "x-chunk-count": str(len(lines)),
                     "content-length": str(len(body))}, body

    # -- export ---------------------------------------------------------
    def export_tree(self, root):
        """Write a pinnable tree: head.json, manifest.json, shards and
        chunks as files. Receipted."""
        epoch, bundle = self._gen()
        os.makedirs(os.path.join(root, "chunks"), exist_ok=True)
        os.makedirs(os.path.join(root, "shards"), exist_ok=True)
        with open(os.path.join(root, "head.json"), "w") as fh:
            fh.write(_canonical_bytes(bundle["head"]).decode())
        with open(os.path.join(root, "manifest.json"), "w") as fh:
            fh.write(_canonical_bytes(bundle["manifest"]).decode())
        for cid, env in bundle["chunks_by_id"].items():
            with open(os.path.join(root, "chunks", cid + ".json"), "w") as fh:
                fh.write(_canonical_bytes(env).decode())
        for dataset, entries in bundle["shard_entries"].items():
            meta = next(m for m in bundle["datasets_meta"]
                        if m["dataset"] == dataset)
            pages = max(1, (len(entries) + 999) // 1000)
            for page in range(pages):
                env = build_shard_manifest(
                    dataset, meta["priority"], entries, page=page, per=1000,
                    world_epoch=epoch,
                    schema_version=bundle["schema_version"])
                with open(os.path.join(
                        root, "shards", f"{dataset}.page-{page}.json"),
                        "w") as fh:
                    fh.write(_canonical_bytes(env).decode())
        _log_receipt({"action": "tree_exported", "world_epoch": epoch,
                      "root": root,
                      "chunk_count": len(bundle["chunks_by_id"])})
        return root


# ---------------------------------------------------------------------------
# relay integration — chunks are relay bundles
# ---------------------------------------------------------------------------
def relay_wrap(chunk_envelope, unity_id, gate, reason=None,
               helper_path=None):
    """Wrap a signed chunk envelope into a dualis.relay.v1.testnet EVIDENCE
    bundle via relay/wrap-chunk.mjs. The gate must be a BOUND gate envelope
    for unity_id (the relay enforces this; this function passes it through
    untouched). Returns the bundle dict. Testnet only."""
    import subprocess
    import tempfile
    helper = helper_path or os.path.normpath(
        os.path.join(_HERE, "..", "relay", "wrap-chunk.mjs"))
    with tempfile.TemporaryDirectory() as tmp:
        chunk_path = os.path.join(tmp, "chunk.json")
        gate_path = os.path.join(tmp, "gate.json")
        with open(chunk_path, "w") as fh:
            fh.write(_canonical_bytes(chunk_envelope).decode())
        with open(gate_path, "w") as fh:
            fh.write(json.dumps(gate))
        proc = subprocess.run(
            ["node", helper, "wrap", chunk_path, gate_path, unity_id,
             reason or "CHUNK · DCLM-signed data chunk for the bound identity"],
            capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"chunk relay wrap failed: "
                           f"{proc.stderr.decode()!r}")
    return json.loads(proc.stdout.decode())
