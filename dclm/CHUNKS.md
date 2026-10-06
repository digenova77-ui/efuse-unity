# CHUNKED DATA SERVING — protocol document

`dclm/chunks.py` extends `dclm/data.py` (never rewrites it). DCLM serves the
unity-world data plane in signed, priority-ordered, byte-bounded chunks.
Testnet only (`unity-world-test` key). UNKNOWN is never PASS.

Implements Trinity verdict `PURITY_VERDICT_PROGRESSIVE_ARCH.md`
(PASS-WITH-NOTES, 2026-10-06): **P0-2 readjustment protocol** and **P0-3
tiered freshness**. P0-1 (the IndexedDB amendment) has since passed the
purity machine — `client/validate-client.mjs` now enforces the amended
write law ("DCLM writes records; the client writes bytes — and only inside
the fences"); the durable read-cache lives in the client worker's
sanctioned region, and `client/chunks.js` performs no durable writes
(in-memory Map only).

## Chunk inventory (epoch cut, 2026-10-06)

18 datasets, 19 chunks, ~747KB total. Chunk data payloads are bounded at
256 KiB each — volume changes shard count, never shard size.

| P | dataset | shards | tier | schema policy | labels |
|---|---------|--------|------|---------------|--------|
| 1 | doctrine | 1 | long | purge | REPORTED |
| 1 | world-state | 1 | long | retain-stale | VERIFIED, UNKNOWN |
| 1 | registry-summary | 1 | long | purge | REPORTED |
| 2 | countries.coarse | 1 | long | purge | REPORTED |
| 2 | chambers | 1 | long | purge | REPORTED |
| 2 | jurisdictions | 1 | long | purge | REPORTED |
| 2 | rtes | 1 | long | purge | REPORTED |
| 2 | canada | 1 | long | purge | REPORTED |
| 2 | sectors | 1 | long | purge | REPORTED |
| 2 | pharmacology | 1 | long | purge | REPORTED |
| 3 | cities.full | 1 | long | retain-stale | REPORTED |
| 3 | countries.full | 2 | long | retain-stale | REPORTED |
| 3 | telemetrics | 1 | long | retain-stale | REAL |
| 3 | feeds | 1 | short | retain-stale | UNKNOWN |
| 3 | verdicts | 1 | long | retain-stale | VERIFIED |
| 3 | pricing | 1 | short | retain-stale | REPORTED, REAL, DERIVED, UNKNOWN |
| 4 | economics.pricing | 1 | short | retain-stale | REPORTED, DERIVED, UNKNOWN |
| 4 | mesh.bulk | 1 | short | retain-stale | UNKNOWN (PENDING slot) |

## Readjustment protocol (P0-2)

**world_epoch** — monotonic integer, bumped on every regeneration
(`chunk_epoch.json`), carried on every chunk body, shard manifest,
manifest, and head. Client rule (no-downgrade): any head/chunk with
`world_epoch` below the client's cached maximum is rejected. Old-but-
validly-signed chunks can never replay as current — the relay is trusted
for liveness, never for freshness.

**Head document** — `GET /chunks/head.json`: tiny (~1KB), signed, fetched
on every load. Carries `world_epoch`, `schema_version`, `manifest_hash`,
`previous_epoch` / `previous_manifest_hash`, dataset/chunk counts, and the
freshness class listing. The only freshness-sensitive fetch; everything
else is content-addressed and immutable.

**Atomic version cuts** — one regeneration = one epoch; all chunks in a cut
carry the same `world_epoch`. Streams are version-pinned: the client
records the head's epoch at stream start and rejects lines from any other
epoch. The client never mixes epochs without labeling.

**Schema evolution** — manifest and chunks carry `schema_version`
(`chunk_schema.json`; cut via `bump_schema_version()`). Per-dataset
`schema_policy`: `purge` (small registries — drop the namespace,
re-stream) or `retain-stale` (heavy/detail — keep rendering the old world
labeled STALE while the new epoch streams behind, then atomic cutover).
The thin client never migrates bytes itself (client law: no computation).

**STALE state** — a freshness state, not a provenance label
(`CURRENT` / `STALE`; `compute.py`'s provenance enum is untouched). The
server retains the previous epoch's signed manifest
(`GET /chunks/manifest.json?epoch=N`), so STALE chunks stay verifiable
during transition. Hash verification happens on READ, not just download.

## Tiered freshness (P0-3)

- **long** — geometry + reference telemetry. Cache aggressively; revalidate
  on epoch change only.
- **short** — economic data (pricing, economics.pricing, feeds). Revalidate
  against the head on *every* load; chunk carries `as_of`; the client
  renders as-of + STALE badge past revalidation. A stale cached price is a
  financial hazard (Merit is transferable); geometry may go stale visibly,
  money may not.
- **wallet — NEVER chunked, always live** via `POST /api/world/*`
  server-round-trip, as the ratified thin client already does. The manifest
  states this explicitly so no client goes looking for a wallet chunk.

Freshness is encoded per dataset in the manifest and per chunk in the
chunk body (`freshness: {tier, revalidate, as_of, state}`). Enforcement is
epoch-based, never wall clock (clock skew must not decide freshness).

## Endpoints (`ChunkServer.handle`)

| Method | Path | Notes |
|---|---|---|
| GET | `/chunks/head.json` | signed head |
| GET | `/chunks/manifest.json[?epoch=N]` | signed dataset manifest (current + previous servable) |
| GET | `/chunks/<dataset>/shards.json[?page=&per=&epoch=]` | paged signed shard listing |
| GET | `/chunks/<chunk_id>[?epoch=]` | signed chunk; `Range:` → 206; `ETag`/`If-None-Match` → 304 |
| GET | `/chunks?priorities=1,2[&epoch=]` | chunk ids in fetch order + total bytes |
| GET | `/stream?priorities=1,2[&epoch=][&datasets=]` | NDJSON, one signed envelope/line, priority order, epoch-pinned |

## Client progressive flow (`client/chunks.js`)

1. `GET /chunks/head.json` → verify signature; **no-downgrade check**
   against cached max epoch (reject + keep old world on downgrade).
2. If head epoch > cached: fetch P1 chunk ids (`/chunks?priorities=1`),
   fetch each (ETag-cached), verify signature + `content_hash`, render
   shell. Record epoch.
3. Same for P2 → coarse world. (P1+P2 ≈ 90KB: immediate coarse world.)
4. Stream P3+P4 via `/stream?priorities=3,4` → NDJSON; verify + render each
   line progressively; reject lines whose `world_epoch` ≠ pinned epoch.
5. Freshness: `long` chunks render from cache with epoch check; `short`
   chunks revalidate against the head every load and render `as_of` +
   `[STALE]` when superseded. Wallet: never from chunks — always live POST.
6. Cache: in-memory Map keyed by `(chunk_id, envelope_hash)`; hash
   re-verified on every READ. (Durable read-cache awaits the P0-1 purity
   amendment; the storage backend is pluggable.)

Chunk ids are deterministic
(`<dataset>@shard-<nnnnnn>-of-<nnnnnn>`); the top manifest lists datasets
only, so it stays small at any scale — per-dataset shard listings are
paged. At 5TB / 256KiB chunks ≈ 20M shards, the manifest hierarchy keeps
every single response bounded.

## Relay integration

Chunks are relay bundles: `relay/wrap-chunk.mjs wrap <chunk.json>
<gate.json> <unity-id>` wraps a signed chunk envelope into a
`dualis.relay.v1.testnet` EVIDENCE bundle (BOUND gate enforced by the
relay itself). `verify` checks a wrapped bundle structurally. Python side:
`chunks.relay_wrap(chunk_envelope, unity_id, gate)`.

## Scale math

| volume | 256KiB chunks | manifest entries |
|---|---|---|
| 660KB (today) | 19 | 18 dataset rows |
| 300MB | ~1,200 | unchanged shape |
| 2GB | ~8,200 | unchanged shape |
| 5TB | ~20M | unchanged shape; shard manifests paged |

## Client verification layering (corrected 2026-10-06 per client worker)

The browser NEVER recomputes hashes. `canonical_sha256` covers the chunk
BODY while served bytes are the ENVELOPE's canonical form (plus Python
float / ensure_ascii rendering), so recompute-and-compare is unsound —
every real chunk would fail. Instead `client/chunks.js`:

- **structurally verifies** each envelope: well-formed, non-empty Ed25519
  signature present, state complete (chunk_id, world_epoch,
  schema_version, content_hash, data, freshness), deterministic shard id;
- **leaves signature authentication to the relay boundary**
  (`relay/wrap-chunk.mjs`), which verifies against the testnet key;
- **storage integrity via hash-on-read**: sha256 of the stored raw bytes,
  recorded at store time, re-checked on every cache read; corrupt bytes
  are evicted and refetched, never rendered.

## Relay contract (agreed with client worker, 2026-10-06)

- **Chunks are the authoritative world-data plane.** All world data
  (registries, telemetrics, verdicts, pricing) flows via the chunk
  endpoints above.
- **`GET /relay/bundle.json` is slimmed to wallet + metering only.**
- **On overlap, chunks win.** If the relay still serves the full legacy
  bundle shape, the client ignores the world-data keys — the chunk plane
  is the source of truth for world data, the relay bundle for
  wallet/metering. (Relay shape itself is the relay worker's side; this
  contract is the agreed division.)

## Receipts

Every mutation (epoch bump, schema cut, epoch build, tree export) appends
JSONL to `dclm/chunk_receipts.log` with before/after manifest hashes.
`ChunkServer.export_tree(root)` writes a pinnable tree
(head.json, manifest.json, chunks/, shards/).

## Concurrency (caught 2026-10-06)

Two overlapping regenerations used to interleave
(bump 5 → bump 6 → built 5 → built 6): the slower cut overwrote the
previous-manifest pointer and broke the epoch chain. The entire cut —
bump → sign → write previous manifest → receipt — now holds a
cross-process exclusive lock (`chunk_build.lock`, `fcntl.flock`;
reentrant in-process). Epochs stay monotonic and the previous-epoch
chain gapless under any interleaving of cooperating builders.

Test hermeticity: `CHUNK_STATE_DIR` env var redirects all chunk server
state (epoch file, lock, receipts, schema file, previous manifest) to
another directory. The test suite points it at a fresh temp dir per run,
so concurrent workers' builds on the shared box can never interleave
with the test's epoch chain.

## Files

- `dclm/chunks.py` — manifest generator, chunk builders, sharding,
  signing, `ChunkServer`, relay wrap, receipts
- `dclm/test_chunks.py` — 30 tests (contract + P0-2 + P0-3 + protocol +
  relay wrap + receipts)
- `relay/wrap-chunk.mjs` — chunk → EVIDENCE relay bundle wrapper
- `client/chunks.js` — progressive client helper (head → P1 → P2 →
  stream P3/P4, no-downgrade, STALE, tiered freshness, wallet live-only)
