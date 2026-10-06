/* ============================================================================
 * Unity World — thin client (the ONLY script on this page)
 * ----------------------------------------------------------------------------
 * THIN-CLIENT LAW
 *   This file displays what DCLM computed. Nothing more.
 *   - It fetches relay data and renders fields with their provenance labels.
 *   - It performs NO verdict computation, NO purity computation, NO physics math.
 *   - If data is not in the relay payload, it renders UNKNOWN. It never invents.
 *   - PENDING renders as PENDING. UNKNOWN renders as UNKNOWN — never as empty,
 *     and never as a passing claim.
 *   - A feed is LIVE only when the relay payload carries a reading hash for it.
 *     Until then PENDING is the truth.
 *
 * READ-CACHE AMENDMENT (ratified 2026-10-06 — purity-machine amendment, P0-1)
 *   The original NO-WRITE LAW banned IndexedDB outright. That ban is AMENDED:
 *   the client performs NO WRITES OF RECORD. It may write bytes to IndexedDB
 *   SOLELY as a non-authoritative read cache for DCLM-signed chunks, bounded by:
 *   1. Only DCLM-signed, hash-verified chunks are stored, keyed by content hash.
 *      A chunk whose bytes do not verify is never stored and never rendered.
 *   2. The cache is NEVER authoritative. Cached data renders only with the
 *      provenance labels carried inside the cached chunk itself. Stale or
 *      missing data renders STALE or UNKNOWN — never as current truth.
 *   3. Wallet, metering, and identity state are NEVER cached. They stay
 *      server-round-trip only, every load.
 *   4. Every IndexedDB touch lives inside the fenced READ-CACHE SANCTIONED
 *      REGION below. IndexedDB anywhere else fails the build.
 *   5. Invalidation is by DCLM-signed head document. The client never decides
 *      what is fresh; it only caches what DCLM said, and drops what DCLM's
 *      head supersedes.
 *   "Read cache" describes authority, not I/O: bytes are written, truth is not.
 *
 * PROGRESSIVE LOADING LAW
 *   The world must NEVER wait for bulk data before rendering.
 *   - Initial render comes from the local read cache immediately. Empty cache
 *     renders honest UNKNOWN shells — never a loading bar, never a blank page.
 *   - Data streams in priority order: head -> P1 shell -> P2 coarse ->
 *     P3/P4 detail over NDJSON. Coarse always; detail only as bandwidth allows.
 *   - Readjustment (a newer epoch published mid-session) NEVER blanks the
 *     screen: the old world keeps rendering labeled STALE while the new epoch
 *     streams behind it, then cuts over atomically.
 *   - Every stream is epoch-pinned: chunks carry their world_epoch, and a
 *     stream completes against the head it started with. An epoch cut
 *     mid-stream aborts the stream — epochs are never mixed on screen.
 *   - No-downgrade: the client rejects any head older than its cached head.
 *     The relay is trusted for liveness, never for freshness.
 *
 * WIRE PROTOCOL (DCLM chunked data plane — dclm/CHUNKS.md)
 *   GET /chunks/head.json                signed head (the only freshness-sensitive fetch)
 *   GET /chunks?priorities=1,2[&epoch=N]  chunk ids in fetch order
 *   GET /chunks/<chunk_id>[?epoch=N]      one signed chunk envelope
 *   GET /stream?priorities=3,4[&epoch=N]  NDJSON, one signed envelope per line, epoch-pinned
 *   GET /chunks/manifest.json[?epoch=N]   signed dataset manifest (current + previous)
 *   Chunk envelope: {state, canonical_sha256, signature, algorithm, key_id}.
 *   The client verifies sha256(raw served bytes) === canonical_sha256 and the
 *   presence of a DCLM signature. It does NOT re-canonicalize body.data —
 *   Python canonical JSON and JS re-serialization can differ on non-ASCII, so
 *   a client-side content_hash recompute would be unsound. Signature
 *   authentication happens at the relay boundary (the purity law keeps
 *   verification out of the browser). Storage integrity IS proven: every
 *   cached record carries sha256 of its raw bytes, re-verified on every read.
 *   Each layer checks what it can actually prove.
 *
 * ANTI-BUG DESIGN (the entry-gate bug class, made structurally impossible)
 *   The old build kept gate logic in the browser: a click handler decided entry
 *   from local state, the handler died, and users sat stuck on the first screen
 *   with no path forward. This client keeps no such state, so there is nothing
 *   to get stuck:
 *   - There is no gate. The world renders free on load.
 *   - Binding the Unity ID and running metered actions are server round-trips.
 *     Every activation does fetch() and then renders the RETURNED server state.
 *     No local branch ever decides bound/unbound, deducted/kept, allowed/denied.
 *   - Failure mode, by construction: if a handler breaks or the server is
 *     unreachable, nothing happens and the indicator still shows the last
 *     server-delivered state (honestly labeled). There is no silent stuck gate
 *     with no path — the path is always "the server answers, the client shows".
 * ========================================================================== */

export const BUNDLE_URL = "/relay/bundle.json"; /* wallet + metering only, live */
export const HEAD_URL = "/chunks/head.json";
export const CHUNK_IDS_URL = (priorities, epoch) =>
  `/chunks?priorities=${encodeURIComponent(priorities)}${epoch ? `&epoch=${epoch}` : ""}`;
export const CHUNK_URL = (chunkId, epoch) =>
  `/chunks/${encodeURIComponent(chunkId)}${epoch ? `?epoch=${epoch}` : ""}`;
export const STREAM_URL = (priorities, epoch, datasets) =>
  `/stream?priorities=${encodeURIComponent(priorities)}${epoch ? `&epoch=${epoch}` : ""}` +
  (datasets ? `&datasets=${encodeURIComponent(datasets)}` : "");
export const MANIFEST_URL = (epoch) =>
  `/chunks/manifest.json${epoch ? `?epoch=${epoch}` : ""}`;
export const API = {
  search: "/api/world/search",
  compute: "/api/world/compute",
  bind: "/api/world/bind",
};

export const PROVENANCE_LABELS = [
  "REPORTED", "VERIFIED", "MODELED", "DERIVED",
  "UNKNOWN", "REAL", "PENDING", "LIVE", "STALE",
];
/* STALE in the badge set renders the chunk's freshness STATE (CURRENT/STALE),
 * never a rewritten provenance: DCLM's provenance labels ride every figure
 * untouched, and a STALE badge is added beside them when the freshness state
 * says so. The verdict required STALE in the badge set; the data plane keeps
 * it out of the provenance enum. Both hold: the badge shows freshness, the
 * label shows provenance, and the two are never confused. */

/* Tiered freshness. long: geometry + reference telemetry — cache aggressively,
 * revalidate on epoch change. short: economic data — revalidate against the
 * head on every load; a superseded short chunk renders as_of + STALE.
 * Enforcement is epoch-based, never wall clock: clock skew must not decide
 * freshness. Identity/standing never enters the chunk cache at all. */
export const FRESHNESS_TIERS = ["long", "short"];
export const FRESHNESS_STATES = ["CURRENT", "STALE"];
export const LOD_NAMES = ["coarse", "standard", "fine"];

/* Every scalar the relay delivers is expected as { value, provenance }.
 * Bare scalars are tolerated and labeled UNKNOWN — never upgraded. */

export function esc(value) {
  return String(value === undefined || value === null ? "" : value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]),
  );
}

export function badge(provenance) {
  const p = PROVENANCE_LABELS.includes(provenance) ? provenance : "UNKNOWN";
  return `<span class="badge" data-provenance="${p}">[${p}]</span>`;
}

/* The single choke point for rendered figures. Missing data -> the literal
 * text UNKNOWN with an UNKNOWN badge. There is no other path to the screen. */
export function fig(field) {
  const f = field && typeof field === "object"
    ? field
    : { value: field, provenance: "UNKNOWN" };
  const raw = f.value;
  const text = raw === undefined || raw === null || raw === "" ? "UNKNOWN" : esc(raw);
  return `<span class="figure"><span class="figure-value">${text}</span> ${badge(f.provenance)}</span>`;
}

/* Freshness-aware figure. A superseded short-tier chunk keeps its DCLM label
 * and gains a STALE badge plus its as-of — a human must see the staleness on
 * the figure's face, never discover it after acting. Epoch-based: stale means
 * the chunk's world_epoch is older than the head's, never a wall-clock TTL. */
export function figFresh(field, tierInfo, headEpoch) {
  const base = fig(field);
  if (!tierInfo || tierInfo.tier !== "short") return base;
  if (tierInfo.epoch === headEpoch) return base;
  const asOfText = tierInfo.as_of ? ` as of ${esc(tierInfo.as_of)}` : "";
  return `${base} ${badge("STALE")}<span class="fine">${asOfText}</span>`;
}

/* Chunk freshness state against the current head epoch. */
export function freshnessState(body, headEpoch) {
  if (!body || typeof body.world_epoch !== "number") return "STALE";
  return body.world_epoch === headEpoch ? "CURRENT" : "STALE";
}

export async function sha256HexBytes(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text) {
  return sha256HexBytes(new TextEncoder().encode(text));
}

/* Chunk envelope verification — STRUCTURAL (see WIRE PROTOCOL above). Proves the
 * envelope is well-formed, DCLM-signed (presence), complete, and pinnable.
 * Never invents cryptographic proof it cannot perform: content_hash and
 * canonical_sha256 are Python-canonical values the browser cannot reproduce
 * soundly, so the client checks structure here and storage integrity at rest
 * (sha256 of cached raw bytes, re-verified on every read). */
export function verifyChunkEnvelope(envelope) {
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
    return { ok: false, reason: "not-an-object" };
  }
  const body = envelope.state;
  if (!body || typeof body !== "object") return { ok: false, reason: "no-state" };
  if (typeof envelope.signature !== "string" || envelope.signature.length < 8) {
    return { ok: false, reason: "no-dclm-signature" };
  }
  for (const k of ["chunk_id", "dataset", "world_epoch", "schema_version",
                   "content_hash", "freshness", "schema_policy", "data"]) {
    if (body[k] === undefined || body[k] === null || body[k] === "") {
      return { ok: false, reason: "missing:" + k };
    }
  }
  if (typeof body.world_epoch !== "number") return { ok: false, reason: "bad-world-epoch" };
  const fr = body.freshness;
  if (!fr || !FRESHNESS_TIERS.includes(fr.tier)) return { ok: false, reason: "bad-tier" };
  if (!["purge", "retain-stale"].includes(body.schema_policy)) {
    return { ok: false, reason: "bad-schema-policy" };
  }
  return { ok: true, body };
}

export function tierInfoOf(body) {
  const fr = (body && body.freshness) || {};
  return { tier: fr.tier || "long", as_of: fr.as_of || null, epoch: body ? body.world_epoch : null };
}

/* === READ-CACHE SANCTIONED REGION BEGIN === */
/* Purity amendment P0-1.
 * CACHE_NON_AUTHORITATIVE
 * Every IndexedDB touch in this client lives between these fences. Nothing
 * outside may open the database, read it, or write it.
 * Boundary, restated so no future edit can blur it:
 *   - Stored records are DCLM-signed chunk envelopes ONLY, keyed
 *     "chunk:{world_epoch}:{chunk_id}", plus the single head record.
 *   - Every record is hash-verified BEFORE write and ON EVERY READ, over the
 *     raw served bytes. A record that fails verification on read is treated
 *     as absent — never rendered.
 *   - No spendable balances, no identity bindings, no usage tallies, no
 *     decisions are stored here. Those stay server-round-trip, every load, by
 *     construction: this region has no code path that accepts them.
 *   - Quota pressure degrades to streaming-only (evict detail-first, then give
 *     up the write) — the cache layer never throws into the render path.
 */

const CACHE_DB_NAME = "unity-world-read-cache";
const CACHE_STORE = "dclm-chunks";
const HEAD_RECORD_KEY = "head:current";

export function cacheAvailable() {
  return typeof indexedDB !== "undefined" && indexedDB !== null;
}

function idbRequest(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = (ev) => resolve(ev.target.result);
    req.onerror = () => reject(req.error || new Error("indexeddb request failed"));
  });
}

export async function openCacheDb() {
  if (!cacheAvailable()) return null;
  const req = indexedDB.open(CACHE_DB_NAME, 1);
  const opened = new Promise((resolve, reject) => {
    req.onupgradeneeded = (ev) => {
      const db = ev.target.result;
      if (!db.objectStoreNames.contains(CACHE_STORE)) db.createObjectStore(CACHE_STORE);
    };
    req.onsuccess = (ev) => resolve(ev.target.result);
    req.onerror = () => reject(req.error || new Error("indexeddb open failed"));
  });
  return opened;
}

function cacheTx(db, mode) {
  return db.transaction(CACHE_STORE, mode).objectStore(CACHE_STORE);
}

async function idbPut(db, key, value) {
  return idbRequest(cacheTx(db, "readwrite").put(value, key));
}

async function idbGet(db, key) {
  const v = await idbRequest(cacheTx(db, "readonly").get(key));
  return v === undefined ? null : v;
}

function chunkRecordKey(epoch, chunkId) {
  return `chunk:${epoch}:${chunkId}`;
}

/* A cache record carries the raw served bytes plus their sha256, so
 * hash-on-read re-verifies exactly what was stored — the partial-corruption
 * defense. This proves storage integrity (what I wrote is what I read), not
 * server authenticity (the relay boundary's job). */
async function toRecord(rawText, envelope, body, etag) {
  return {
    chunk_id: body.chunk_id,
    dataset: body.dataset,
    epoch: body.world_epoch,
    schema_version: body.schema_version,
    priority: body.priority,
    tier: body.freshness.tier,
    as_of: body.freshness.as_of || null,
    schema_policy: body.schema_policy,
    servedHash: await sha256Hex(rawText),
    etag: etag || null,
    rawText,
  };
}

function bodyOfRecord(record) {
  return record && record.rawText ? JSON.parse(record.rawText).state : null;
}

/* Write path: verify structure FIRST, store second with a storage-integrity
 * hash. Quota-aware: on QuotaExceededError, evict detail-first and retry once;
 * if it still fails, report {stored:false} and the caller streams without
 * caching. */
export async function cacheWriteChunk(db, rawText, envelope, etag) {
  const v = verifyChunkEnvelope(envelope);
  if (!v.ok) return { stored: false, reason: v.reason };
  const key = chunkRecordKey(v.body.world_epoch, v.body.chunk_id);
  const record = await toRecord(rawText, envelope, v.body, etag);
  try {
    await idbPut(db, key, record);
    return { stored: true, key, body: v.body };
  } catch (err) {
    if (err && err.name === "QuotaExceededError") {
      await evictDetailFirst(db);
      try {
        await idbPut(db, key, record);
        return { stored: true, key, body: v.body, afterEvict: true };
      } catch (err2) {
        return { stored: false, reason: "quota-persist" };
      }
    }
    return { stored: false, reason: "idb-error" };
  }
}

/* Read path: storage-integrity hash re-verified ON EVERY READ, not just at
 * download. A record whose bytes changed under us is treated as absent —
 * the partial-corruption defense. */
export async function cacheReadChunk(db, key) {
  const record = await idbGet(db, key);
  if (!record || !record.rawText || !record.servedHash) return null;
  const recomputed = await sha256Hex(record.rawText);
  if (recomputed !== record.servedHash) return null;
  return record;
}

export async function cacheHasChunk(db, chunkId, epoch) {
  const record = await cacheReadChunk(db, chunkRecordKey(epoch, chunkId));
  return !!record;
}

/* Head write enforces the no-downgrade rule at the storage layer too: an
 * older head is refused even if some code path asks to store it. */
export async function cacheWriteHead(db, rawText, envelope) {
  const v = verifyEnvelope(envelope);
  if (!v.ok) return { stored: false, reason: v.reason };
  const hs = verifyHeadShape(v.body);
  if (!hs.ok) return { stored: false, reason: "bad-head" };
  const current = await idbGet(db, HEAD_RECORD_KEY);
  if (current && typeof current.epoch === "number" && v.body.world_epoch < current.epoch) {
    return { stored: false, reason: "downgrade-refused" };
  }
  try {
    await idbPut(db, HEAD_RECORD_KEY, {
      epoch: v.body.world_epoch,
      schema_version: v.body.schema_version,
      servedHash: await sha256Hex(rawText),
      rawText,
    });
    return { stored: true, head: v.body };
  } catch (err) {
    return { stored: false, reason: "idb-error" };
  }
}

export async function cacheReadHead(db) {
  const record = await idbGet(db, HEAD_RECORD_KEY);
  if (!record || !record.rawText || !record.servedHash) return null;
  const recomputed = await sha256Hex(record.rawText);
  if (recomputed !== record.servedHash) return null;
  return record;
}

/* Eviction order: detail-before-coarse (higher priority number first), then
 * by key. The offline world degrades to coarse, never to empty. */
export function evictionOrder(records) {
  return records.slice().sort((a, b) =>
    (b.priority - a.priority) || (a.chunk_id < b.chunk_id ? -1 : a.chunk_id > b.chunk_id ? 1 : 0));
}

export async function evictDetailFirst(db) {
  const keys = await idbRequest(cacheTx(db, "readonly").getAllKeys());
  const records = [];
  for (const key of keys) {
    if (!String(key).startsWith("chunk:")) continue;
    const record = await idbGet(db, key);
    if (record) records.push({ key, priority: record.priority || 0, chunk_id: record.chunk_id || "" });
  }
  const ordered = evictionOrder(records);
  let evicted = 0;
  const store = cacheTx(db, "readwrite");
  for (const r of ordered) {
    if (r.priority >= 3) {
      await idbRequest(store.delete(r.key));
      evicted++;
    }
  }
  if (evicted === 0) {
    for (const r of ordered) {
      if (r.priority >= 2) {
        await idbRequest(store.delete(r.key));
        evicted++;
      }
    }
  }
  return { evicted };
}

/* Load the cached world: dataset -> [bodies]. Every record re-verified on
 * the way out via cacheReadChunk. */
export async function loadCachedWorld(db) {
  const byDataset = {};
  const keys = await idbRequest(cacheTx(db, "readonly").getAllKeys());
  for (const key of keys) {
    if (!String(key).startsWith("chunk:")) continue;
    const record = await cacheReadChunk(db, key);
    if (!record) continue;
    const body = bodyOfRecord(record);
    if (!body) continue;
    (byDataset[body.dataset] = byDataset[body.dataset] || []).push(body);
  }
  return byDataset;
}

/* === READ-CACHE SANCTIONED REGION END === */

/* ---- readjustment protocol (P0-2) ------------------------------------------
 * The signed head document is the only freshness-sensitive fetch. Everything
 * else is immutable, content-addressed, and cacheable. Readjustment:
 *   1. fetch head (tiny, every load), verify over raw bytes
 *   2. compare world_epoch against cached head: older -> reject (no-downgrade);
 *      same -> delta (short-tier chunks revalidate every load; long-tier reuse);
 *      newer -> STALE-holdover, stream the new epoch pinned, atomic cutover.
 * Rollback defense: a head older than the cached head is refused at the policy
 * layer AND at the storage layer (cacheWriteHead). Old-but-validly-signed
 * chunks can never replay as current, because currency is decided by the
 * monotonic world_epoch, never by signature presence alone.
 * Schema changes: per-dataset schema_policy from the chunk body. purge:
 * the old dataset's namespace is dropped on a schema cut and re-streamed.
 * retain-stale: the old world keeps rendering labeled STALE while the new
 * epoch streams behind, then cuts over atomically. The client never migrates
 * bytes itself (thin-client law: no computation on the client).
 * -------------------------------------------------------------------------- */

/* Generic envelope check: well-formed state plus DCLM signature presence.
 * Chunk and head bodies add their own shape checks on top. Structural, not
 * cryptographic — see WIRE PROTOCOL. */
export function verifyEnvelope(envelope) {
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
    return { ok: false, reason: "not-an-object" };
  }
  if (!envelope.state || typeof envelope.state !== "object") {
    return { ok: false, reason: "no-state" };
  }
  if (typeof envelope.signature !== "string" || envelope.signature.length < 8) {
    return { ok: false, reason: "no-dclm-signature" };
  }
  return { ok: true, body: envelope.state };
}

export function verifyHeadShape(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, missing: ["head is not an object"] };
  }
  const missing = ["world_epoch", "schema_version", "manifest_hash", "freshness_classes"]
    .filter((k) => body[k] === undefined || body[k] === null);
  if (typeof body.world_epoch !== "number") missing.push("world_epoch:not-a-number");
  return { ok: missing.length === 0, missing };
}

async function readBody(fetchFn, url) {
  const res = await fetchFn(url, { method: "GET", headers: { accept: "application/json" } });
  const buf = new Uint8Array(await res.arrayBuffer());
  const text = new TextDecoder().decode(buf);
  return { buf, text, json: JSON.parse(text), res };
}

export async function fetchHead(fetchFn) {
  const { text, json } = await readBody(fetchFn, HEAD_URL);
  const v = verifyEnvelope(json);
  if (!v.ok) return { ok: false, reason: v.reason };
  const hs = verifyHeadShape(v.body);
  if (!hs.ok) return { ok: false, reason: "bad-head", missing: hs.missing };
  return { ok: true, head: v.body, rawText: text, envelope: json };
}

export async function fetchChunkIds(fetchFn, priorities, epoch) {
  const { json } = await readBody(fetchFn, CHUNK_IDS_URL(priorities, epoch));
  if (json.world_epoch !== epoch) {
    return { ok: false, reason: "index-epoch-mismatch" };
  }
  if (!Array.isArray(json.chunk_ids)) return { ok: false, reason: "no-chunk-ids" };
  return { ok: true, chunk_ids: json.chunk_ids };
}

/* Chunk fetch with ETag revalidation: pass the cached record's etag and a
 * 304 means "unchanged" — the delta-sync fast path, decided by the server's
 * own validator, never by client arithmetic. */
export async function fetchChunk(fetchFn, chunkId, epoch, etag) {
  const headers = { accept: "application/json" };
  if (etag) headers["if-none-match"] = etag;
  const res = await fetchFn(CHUNK_URL(chunkId, epoch), { method: "GET", headers });
  if (res.status === 304) return { ok: true, notModified: true };
  const buf = new Uint8Array(await res.arrayBuffer());
  const text = new TextDecoder().decode(buf);
  const json = JSON.parse(text);
  const v = verifyChunkEnvelope(json);
  if (!v.ok) return { ok: false, reason: v.reason };
  if (v.body.world_epoch !== epoch) return { ok: false, reason: "epoch-mismatch" };
  const outEtag = res.headers && typeof res.headers.get === "function"
    ? res.headers.get("etag") : null;
  return { ok: true, body: v.body, rawText: text, envelope: json, etag: outEtag };
}

/* NDJSON stream: one signed envelope per line, epoch-pinned. A line whose
 * world_epoch differs from the pinned epoch aborts the stream — versions are
 * never mixed. Each line is structurally verified; the stream epoch header is
 * cross-checked against the pin. */
export async function streamChunks(fetchFn, priorities, epoch, onChunk) {
  const res = await fetchFn(STREAM_URL(priorities, epoch), {
    method: "GET", headers: { accept: "application/x-ndjson" },
  });
  const epochHeader = res.headers && typeof res.headers.get === "function"
    ? res.headers.get("x-world-epoch") : null;
  const streamEpoch = epochHeader === null || epochHeader === undefined ? NaN : Number(epochHeader);
  if (!Number.isNaN(streamEpoch) && streamEpoch !== epoch) {
    return { ok: false, aborted: "stream-epoch-mismatch", count: 0 };
  }
  const text = new TextDecoder().decode(new Uint8Array(await res.arrayBuffer()));
  let count = 0;
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    let envelope = null;
    try {
      envelope = JSON.parse(line);
    } catch (err) {
      continue;
    }
    const v = verifyChunkEnvelope(envelope);
    if (!v.ok) continue;
    if (v.body.world_epoch !== epoch) {
      return { ok: false, aborted: "epoch-cut", count };
    }
    count++;
    if (onChunk) {
      try { await onChunk(v.body, line, envelope); } catch (err) { /* observer-only */ }
    }
  }
  return { ok: true, count };
}

/* Head policy: the client never decides freshness — it compares monotonic
 * epochs. Older head: reject. Same: delta. Newer: readjust. */
export function applyHeadPolicy(cachedEpoch, head) {
  if (cachedEpoch === null || cachedEpoch === undefined) {
    return { action: "readjust", reason: "no-cached-head" };
  }
  if (head.world_epoch < cachedEpoch) return { action: "reject-downgrade", reason: "head-older-than-cache" };
  if (head.world_epoch === cachedEpoch) return { action: "delta", reason: "same-epoch" };
  return { action: "readjust", reason: "newer-epoch" };
}

/* Adaptive stream governor: measures real throughput and matches the stream
 * to it. Sequential by design — concurrency stays 1 so epoch-pinning order
 * is never violated by a racing chunk. */
export class StreamGovernor {
  constructor() {
    this.kbps = 0;
    this.samples = 0;
  }
  observe(bytes, ms) {
    if (ms > 0 && bytes > 0) {
      const k = (bytes * 8) / ms;
      this.kbps = this.samples === 0 ? k : this.kbps * 0.7 + k * 0.3;
      this.samples++;
    }
    return this.kbps;
  }
}

/* Group cached/streamed bodies by dataset for the views. */
export function groupByDataset(bodies) {
  const byDataset = {};
  for (const body of bodies || []) {
    if (!body || !body.dataset) continue;
    (byDataset[body.dataset] = byDataset[body.dataset] || []).push(body);
  }
  return byDataset;
}

function mergeBodies(into, bodies) {
  for (const [ds, list] of Object.entries(groupByDataset(bodies))) {
    into[ds] = (into[ds] || []).concat(list);
  }
  return into;
}

/* The background sync. Never blocks initial render, never blanks the screen:
 * on a newer epoch the old world keeps rendering labeled STALE until the new
 * epoch completes, then a single render pass cuts over atomically. */
export async function progressiveSync(doc, fetchFn, cache, cachedHead, hooks = {}) {
  let headRes = null;
  try {
    headRes = await fetchHead(fetchFn);
  } catch (err) {
    return { ok: false, reason: "head-unreachable" };
  }
  if (!headRes.ok) return { ok: false, reason: headRes.reason };
  const head = headRes.head;
  const epoch = head.world_epoch;
  const cachedEpoch = cachedHead && typeof cachedHead.epoch === "number" ? cachedHead.epoch : null;
  const policy = applyHeadPolicy(cachedEpoch, head);

  if (policy.action === "reject-downgrade") {
    renderReadjustNote(doc,
      `Relay offered epoch v${epoch}, older than cached v${cachedEpoch} — refused (no-downgrade). Cached world retained.`);
    return { ok: false, reason: "downgrade-rejected" };
  }

  const governor = hooks.governor || new StreamGovernor();
  const onFetch = (bytes, ms) => {
    governor.observe(bytes, ms);
    if (hooks.onFetch) { try { hooks.onFetch(bytes, ms); } catch (err) { /* observer */ } }
  };
  const storeChunk = async (body, rawText, envelope, etag) => {
    if (cache) { try { await cacheWriteChunk(cache, rawText, envelope, etag); } catch (err) { /* streaming-only */ } }
  };

  /* Delta: same epoch. Short-tier chunks revalidate every load via ETag
   * (304 = unchanged, decided by the server's validator); long-tier chunks
   * are reused from cache (storage hash verified on read). */
  if (policy.action === "delta") {
    const byDataset = hooks.cachedBodies ? groupByDataset(hooks.cachedBodies) : {};
    let changed = 0;
    let revalidated = 0;
    /* Short-tier datasets revalidate every load; long-tier never refetches on
     * delta. The tier comes from the head's freshness_classes via the dataset
     * prefix in the chunk id — no fetch needed to decide. */
    const shortDatasets = new Set((head.freshness_classes && head.freshness_classes.short) || []);
    const tierOfChunk = (chunkId) =>
      shortDatasets.has(String(chunkId).split("@shard-")[0]) ? "short" : "long";
    const idsRes = await fetchChunkIds(fetchFn, "1,2,3,4", epoch).catch(() => null);
    const ids = (idsRes && idsRes.ok ? idsRes.chunk_ids : []);
    for (const chunkId of ids) {
      if (tierOfChunk(chunkId) !== "short") continue;
      const cached = cache ? await cacheReadChunk(cache, `chunk:${epoch}:${chunkId}`) : null;
      let fres = null;
      try { fres = await fetchChunk(fetchFn, chunkId, epoch, cached ? cached.etag : null); }
      catch (err) { continue; }
      if (!fres.ok) continue;
      if (fres.notModified) { revalidated++; continue; }
      onFetch(new TextEncoder().encode(fres.rawText).length, 1);
      await storeChunk(fres.body, fres.rawText, fres.envelope, fres.etag);
      const list = byDataset[fres.body.dataset] || [];
      const ix = list.findIndex((b) => b.chunk_id === fres.body.chunk_id);
      if (ix === -1) { list.push(fres.body); changed++; }
      else if (list[ix].content_hash !== fres.body.content_hash) { list[ix] = fres.body; changed++; }
      byDataset[fres.body.dataset] = list;
    }
    if (cache) { try { await cacheWriteHead(cache, headRes.rawText, headRes.envelope); } catch (err) { /* non-fatal */ } }
    renderEpochInto(doc, head, "VERIFIED");
    renderReadjustNote(doc, "");
    if (changed > 0 && hooks.renderCutover) hooks.renderCutover(byDataset, epoch);
    return { ok: true, action: "delta", epoch, changed, revalidated, byDataset };
  }

  /* Readjust: newer epoch. Schema-cut handling per dataset policy: purge
   * datasets drop the old namespace immediately; retain-stale datasets keep
   * rendering labeled STALE until the new epoch arrives. */
  const hadCachedWorld = cachedEpoch !== null;
  const schemaCut = hadCachedWorld && cachedHead &&
    typeof cachedHead.schema_version === "number" &&
    head.schema_version !== cachedHead.schema_version;
  const dropped = new Set();
  if (schemaCut && hooks.cachedBodies) {
    for (const body of hooks.cachedBodies) {
      if (body.schema_policy === "purge") dropped.add(body.dataset);
    }
  }
  if (hadCachedWorld) {
    renderEpochInto(doc, { world_epoch: cachedEpoch, schema_version: cachedHead.schema_version }, "STALE");
    renderReadjustNote(doc,
      `Epoch v${epoch} is materializing — showing the cached world labeled STALE until cutover. Nothing here is current.`);
  }

  const fresh = {};
  const collect = async (body, rawText, envelope, etag) => {
    /* The server's ETag is the envelope's canonical_sha256; derive it when
     * the transport didn't carry one (NDJSON stream lines). */
    const tag = etag || (envelope && envelope.canonical_sha256
      ? `"${envelope.canonical_sha256}"` : null);
    await storeChunk(body, rawText, envelope, tag);
    (fresh[body.dataset] = fresh[body.dataset] || []).push(body);
    if (!hadCachedWorld && hooks.renderProgressive) {
      try { hooks.renderProgressive(groupByDataset(Object.values(fresh).flat()), epoch); } catch (err) { /* observer */ }
    }
  };

  /* P1+P2: shell + coarse, individual fetch (few, small). */
  try {
    const idsRes = await fetchChunkIds(fetchFn, "1,2", epoch);
    if (!idsRes.ok) return { ok: false, reason: idsRes.reason };
    for (const chunkId of idsRes.chunk_ids) {
      let fres = null;
      try { fres = await fetchChunk(fetchFn, chunkId, epoch); } catch (err) { continue; }
      if (!fres.ok) continue;
      onFetch(new TextEncoder().encode(fres.rawText).length, 1);
      await collect(fres.body, fres.rawText, fres.envelope, fres.etag);
    }
  } catch (err) {
    return { ok: false, reason: "priorities-unreachable" };
  }

  /* P3+P4: detail over the NDJSON stream, epoch-pinned. Falls back to
   * individual fetch if the stream endpoint is unavailable. */
  let streamRes = null;
  try {
    streamRes = await streamChunks(fetchFn, "3,4", epoch, collect);
  } catch (err) {
    streamRes = null;
  }
  if (!streamRes) {
    try {
      const idsRes = await fetchChunkIds(fetchFn, "3,4", epoch);
      if (idsRes.ok) {
        for (const chunkId of idsRes.chunk_ids) {
          let fres = null;
          try { fres = await fetchChunk(fetchFn, chunkId, epoch); } catch (err) { continue; }
          if (!fres.ok) continue;
          onFetch(new TextEncoder().encode(fres.rawText).length, 1);
          await collect(fres.body, fres.rawText, fres.envelope, fres.etag);
        }
        streamRes = { ok: true, count: 0, fallback: true };
      }
    } catch (err) { /* detail is optional; coarse world stands */ }
  }
  if (streamRes && !streamRes.ok) {
    renderReadjustNote(doc,
      "The world changed mid-stream — the partial stream was discarded, nothing mixed. Cached world retained.");
    return { ok: false, reason: streamRes.aborted || "stream-aborted" };
  }

  if (cache) { try { await cacheWriteHead(cache, headRes.rawText, headRes.envelope); } catch (err) { /* non-fatal */ } }

  /* Atomic cutover: retained-stale survivors (not purge-dropped) merge under
   * the fresh epoch; a single render pass swaps the world. */
  const survivors = {};
  if (hooks.cachedBodies) {
    for (const body of hooks.cachedBodies) {
      if (dropped.has(body.dataset)) continue;
      if (fresh[body.dataset]) continue; /* superseded by fresh chunks */
      (survivors[body.dataset] = survivors[body.dataset] || []).push(body);
    }
  }
  const cutover = mergeBodies(survivors, Object.values(fresh).flat());
  if (hooks.renderCutover) hooks.renderCutover(cutover, epoch);
  renderEpochInto(doc, head, "VERIFIED");
  renderReadjustNote(doc, "");
  return { ok: true, action: "readjust", epoch, dropped: [...dropped], byDataset: cutover };
}

/* ---- views: pure string builders, no DOM, no math, no decisions ------------
 * The playground's materials. Registries are the building blocks, telemetry
 * is the scoreboard, verdicts are the rules. Every view renders DCLM's
 * datasets with their provenance labels; freshness state renders beside them.
 */

function readoutRow(label, field) {
  return `<div class="readout-row"><dt>${esc(label)}</dt><dd>${fig(field)}</dd></div>`;
}

function humanize(key) {
  return String(key).replace(/_/g, " ");
}

function unknownBlock(what) {
  return `<p class="notice">${esc(what)} — the relay carries no data for this. ${badge("UNKNOWN")}</p>`;
}

/* STALE banner for a dataset's bodies against the head epoch. Epoch-based:
 * any body from an older epoch renders labeled STALE while the new epoch
 * materializes. Short-tier bodies also show their as_of. */
function staleBanner(bodies, headEpoch) {
  const stale = (bodies || []).filter((b) => freshnessState(b, headEpoch) === "STALE");
  if (!stale.length) return "";
  const oldest = Math.min(...stale.map((b) => b.world_epoch));
  const asOf = stale.map((b) => b.freshness && b.freshness.as_of).find(Boolean);
  return `<p class="notice">Showing epoch v${oldest} labeled STALE — v${headEpoch} materializing.` +
    (asOf ? ` As of ${esc(asOf)}.` : "") + ` ${badge("STALE")}</p>`;
}

function firstBodies(chunks, dataset) {
  const list = (chunks && chunks[dataset]) || [];
  return list.length ? list : null;
}

export function renderWorldState(chunks, headEpoch) {
  const bodies = firstBodies(chunks, "world-state");
  if (!bodies) return unknownBlock("World state");
  const data = bodies[0].data || {};
  let html = `<dl class="readout">`;
  if (data.registry_digest) html += readoutRow("Registry digest", data.registry_digest);
  if (data.purity_pulse) {
    html += readoutRow("Purity pulse", {
      value: data.purity_pulse.pulse_id || data.purity_pulse.signed || "—",
      provenance: data.purity_pulse.provenance || "UNKNOWN",
    });
  }
  const feeds = data.feed_status && typeof data.feed_status === "object" ? data.feed_status : {};
  for (const [name, f] of Object.entries(feeds)) {
    html += readoutRow(`Feed · ${humanize(name)}`, { value: f.status, provenance: f.provenance });
  }
  html += `</dl>`;
  return html + staleBanner(bodies, headEpoch);
}

export function renderAtlas(chunks, headEpoch) {
  const bodies = firstBodies(chunks, "registry-summary");
  if (!bodies) return unknownBlock("Atlas registry");
  const data = bodies[0].data || {};
  let html = `<dl class="readout">`;
  for (const [name, entry] of Object.entries(data)) {
    const counts = entry && entry.counts ? entry.counts : {};
    const items = counts.items !== undefined ? `${counts.items} items` : "—";
    const bytes = entry && entry.bytes !== undefined ? ` · ${entry.bytes} bytes` : "";
    const sha = entry && entry.sha256 ? ` <code>${esc(String(entry.sha256).slice(0, 12))}</code>` : "";
    html += `<div class="readout-row"><dt>${esc(humanize(name))}</dt>` +
      `<dd><span class="figure"><span class="figure-value">${esc(items)}${esc(bytes)}</span>` +
      ` ${badge(entry && entry.provenance)}</span>${sha}</dd></div>`;
  }
  html += `</dl><p class="fine">Registry building blocks from DCLM, relay-delivered.</p>`;
  return html + staleBanner(bodies, headEpoch);
}

function telemetryRow(metric, value, provenance, tierInfo, headEpoch) {
  return `<div class="readout-row"><dt>${esc(metric)}</dt><dd>${figFresh({ value, provenance }, tierInfo, headEpoch)}</dd></div>`;
}

export function renderTelemetry(chunks, headEpoch) {
  const sets = [];
  const tele = firstBodies(chunks, "telemetrics");
  if (tele) sets.push({ title: "RTE real telemetry", bodies: tele, kind: "rows" });
  const pricing = firstBodies(chunks, "pricing");
  if (pricing) sets.push({ title: "Pricing — economic", bodies: pricing, kind: "pricing" });
  const econ = firstBodies(chunks, "economics.pricing");
  if (econ) sets.push({ title: "Economics pricing — economic", bodies: econ, kind: "pricing" });
  if (!sets.length) return unknownBlock("Telemetry");
  let html = "";
  const allBodies = [];
  for (const s of sets) {
    allBodies.push(...s.bodies);
    html += `<h3>${esc(s.title)}</h3><dl class="readout">`;
    for (const body of s.bodies) {
      const ti = tierInfoOf(body);
      if (s.kind === "rows") {
        const groups = {};
        for (const r of body.data || []) {
          (groups[r.context || "telemetry"] = groups[r.context || "telemetry"] || []).push(r);
        }
        for (const [ctx, rows] of Object.entries(groups)) {
          html += `<div class="readout-row"><dt>${esc(ctx)}</dt><dd></dd></div>`;
          for (const r of rows) {
            const val = r.unit && r.unit !== "USD" ? `${r.value} ${r.unit}` : r.value;
            html += telemetryRow(r.metric, val, r.label || "UNKNOWN", ti, headEpoch);
          }
        }
      } else {
        for (const r of body.data || []) {
          const figs = (r.figures || []).map((f) => `${f.figure} [${f.label || "UNKNOWN"}]`).join("; ");
          html += `<div class="readout-row"><dt>${esc(r.company || r.index || "?")}</dt>` +
            `<dd>${esc(r.decision || "")}${figs ? `<br><span class="fine">${esc(figs)}</span>` : ""} ` +
            `${badge("REPORTED")}</dd></div>`;
        }
      }
    }
    html += `</dl>`;
  }
  return html + staleBanner(allBodies, headEpoch);
}

export function renderFeeds(chunks, headEpoch) {
  const bodies = firstBodies(chunks, "feeds");
  if (!bodies) return unknownBlock("Feed list");
  const feeds = Array.isArray(bodies[0].data) ? bodies[0].data : [];
  const ti = tierInfoOf(bodies[0]);
  const items = feeds
    .map((f) => {
      const hasReading =
        typeof f.reading_hash === "string" && f.reading_hash.length > 0;
      const live = f.status === "LIVE" && hasReading;
      const shown = live ? "LIVE" : "PENDING";
      const hashPart = live
        ? ` <span class="feed-hash">reading <code>${esc(f.reading_hash)}</code></span> ${badge(f.provenance)}`
        : "";
      return `<li class="feed"><span class="feed-name">${esc(f.display || f.name || "unnamed feed")}</span> — <span class="feed-status">${shown}</span> ${badge(shown)}${hashPart}</li>`;
    })
    .join("");
  return (
    `<ul class="ledger">${items}</ul>` +
    `<p class="fine">A feed is LIVE only when the relay payload carries a reading hash for it. Until then, PENDING is the truth.</p>` +
    staleBanner(bodies, headEpoch)
  );
}

export function renderVerdicts(chunks, headEpoch) {
  const bodies = firstBodies(chunks, "verdicts");
  if (!bodies) return unknownBlock("Verdicts");
  const list = Array.isArray(bodies[0].data) ? bodies[0].data : [];
  const items = list
    .map((v) => `<li class="verdict"><span class="verdict-title">${esc(v.seal || v.id || "verdict")}</span>: ` +
      `${fig({ value: v.verdict, provenance: v.provenance || "UNKNOWN" })}` +
      (v.disposition ? ` <span class="fine">${esc(v.disposition)}</span>` : "") +
      (v.sealed ? ` <span class="fine">${esc(v.sealed)}</span>` : "") + `</li>`)
    .join("");
  return `<h3>The rules, as sealed</h3><ul class="ledger">${items}</ul>` +
    staleBanner(bodies, headEpoch);
}

/* The wall of builders. Renders ONLY the public projection: obfuscated Unity
 * IDs, cohorts, designations. No names, no raw IDs, no member numbers, no PII
 * — the privacy law is structural, and this view cannot render what it is
 * never given. */
export function renderFounders(founders) {
  if (!founders || !Array.isArray(founders.members)) {
    return unknownBlock("Wall of builders");
  }
  const items = founders.members
    .map((m) => `<li class="founder"><code>${esc(m.obfuscated_unity_id || "?")}</code> — ` +
      `${esc(m.designation || m.role || "builder")} · ${esc(m.cohort || "")} ` +
      `${badge(m.verified ? "VERIFIED" : "UNKNOWN")}</li>`)
    .join("");
  const cohorts = (founders.cohorts || [])
    .map((c) => `${esc(c.label || c.cohort_id)}: ${c.member_count} seated`).join("; ");
  return `<ul class="ledger">${items}</ul>` +
    (cohorts ? `<p class="fine">${esc(cohorts)}. ${esc(founders.community || "")}</p>` : "");
}

/* === LOD-CONTRACT SANCTIONED REGION BEGIN === */
/* The #world-viewport mount contract — the playground entrance.
 * #world-viewport is owned by the 3D renderer: the playground the user walks
 * into. This client never writes into it and places nothing over it. The ONLY
 * sanctioned contact is the LOD contract, and it is data-attributes plus
 * events, never DOM writes:
 *   - viewport.dataset.lod = "coarse" | "standard" | "fine"
 *   - viewport dispatches CustomEvent("unity:lod", { detail: { level, kbps } })
 * The renderer listens for "unity:lod" and reads dataset.lod to pick geometry
 * detail: near geometry high-res, far geometry low-res, upgrading as bandwidth
 * allows — the world materializes around the entrant. Hysteresis is
 * structural: upgrade after ONE fast window (humans forgive sharpening),
 * downgrade only after THREE consecutive slow windows past a minimum dwell
 * (humans read quality-pumping as broken). No markup injection, no children,
 * no overlays — the contract is two fields, and it stays two fields.
 */

export const LOD_LEVELS = ["coarse", "standard", "fine"];

export class LodController {
  constructor(viewport, opts = {}) {
    this.viewport = viewport || null;
    this.level = 0;
    this.upKbps = opts.upKbps !== undefined ? opts.upKbps : 800;
    this.downKbps = opts.downKbps !== undefined ? opts.downKbps : 250;
    this.slowNeeded = opts.slowNeeded !== undefined ? opts.slowNeeded : 3;
    this.minDwellMs = opts.minDwellMs !== undefined ? opts.minDwellMs : 5000;
    this.slowStreak = 0;
    this.lastChangeMs = 0;
    this.publish(0);
  }
  levelName() {
    return LOD_LEVELS[this.level];
  }
  /* Feed measured chunk throughput. Returns the current level name. */
  record(bytes, ms) {
    const kbps = ms > 0 && bytes > 0 ? (bytes * 8) / ms : 0;
    const now = Date.now();
    if (kbps >= this.upKbps && this.level < LOD_LEVELS.length - 1) {
      this.setLevel(this.level + 1, now, kbps);
      this.slowStreak = 0;
    } else if (kbps <= this.downKbps && kbps > 0) {
      this.slowStreak += 1;
      if (this.slowStreak >= this.slowNeeded &&
          this.level > 0 &&
          now - this.lastChangeMs >= this.minDwellMs) {
        this.setLevel(this.level - 1, now, kbps);
        this.slowStreak = 0;
      }
    } else {
      this.slowStreak = 0;
    }
    return this.levelName();
  }
  setLevel(level, now, kbps) {
    this.level = level;
    this.lastChangeMs = now;
    this.publish(kbps);
  }
  publish(kbps) {
    const vp = this.viewport;
    if (!vp) return;
    vp.dataset.lod = LOD_LEVELS[this.level];
    if (typeof CustomEvent !== "undefined" && typeof vp.dispatchEvent === "function") {
      vp.dispatchEvent(new CustomEvent("unity:lod", {
        detail: { level: LOD_LEVELS[this.level], kbps: Math.round(kbps || 0) },
      }));
    }
  }
}

/* The single sanctioned lookup of the viewport. Everything else in this file
 * reaches the renderer only through the returned controller. */
export function attachLodController(doc, opts) {
  const vp = doc.getElementById("world-viewport");
  if (!vp) return null;
  return new LodController(vp, opts);
}

/* === LOD-CONTRACT SANCTIONED REGION END === */

/* ---- DOM mounting (display only — the DOM is the accessibility mirror) ----- */

function setHtml(doc, id, html) {
  const el = doc.getElementById(id);
  if (el) el.innerHTML = html;
}

export function renderWalletInto(doc, wallet) {
  const w = wallet && typeof wallet === "object" ? wallet : {};
  setHtml(doc, "wallet-state", fig(w.status));
  setHtml(doc, "wallet-balance", fig(w.key_balance));
  setHtml(doc, "wallet-id", fig(w.unity_id));
}

export function renderMeteringInto(doc, metering) {
  const m = metering && typeof metering === "object" ? metering : {};
  setHtml(doc, "search-cost", fig(m.search_cost));
  setHtml(doc, "compute-cost", fig(m.compute_cost));
}

/* The slim bundle contract: world data moved to the chunk plane
 * (/chunks/*). The bundle now carries the playground token (wallet) and its
 * key prices (metering) — live, every load, never cached. */
const REQUIRED_TOP_LEVEL = ["metering", "wallet"];

export function verifyBundleShape(bundle) {
  if (!bundle || typeof bundle !== "object" || Array.isArray(bundle)) {
    return { ok: false, missing: ["bundle is not an object"] };
  }
  const missing = REQUIRED_TOP_LEVEL.filter((k) => !(k in bundle));
  return { ok: missing.length === 0, missing };
}

export async function fetchBundle(fetchFn) {
  const res = await fetchFn(BUNDLE_URL, {
    method: "GET",
    headers: { accept: "application/json" },
  });
  return res.json();
}

export const FOUNDERS_URL = "/relay/founding-board.json";
export async function fetchFounders(fetchFn) {
  const res = await fetchFn(FOUNDERS_URL, {
    method: "GET",
    headers: { accept: "application/json" },
  });
  return res.json();
}

export async function postAction(fetchFn, path, body) {
  const res = await fetchFn(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

/* Renders the SERVER's receipt. Deducted amounts and balances come from the
 * server response only. This function performs no arithmetic on money. */
export function renderActionResult(doc, action, data) {
  const mount = doc.getElementById("action-result");
  if (!mount) return;
  if (!data || data.ok !== true) {
    const reason = data && data.error ? esc(data.error) : "no receipt returned";
    mount.innerHTML =
      `<h3>${esc(action)} — server receipt</h3>` +
      `<p class="notice">Declined or unreachable (${reason}). Nothing was deducted, nothing changed. ${badge("UNKNOWN")}</p>`;
    return;
  }
  const r = data.receipt || {};
  mount.innerHTML =
    `<h3>${esc(action)} — server receipt</h3>` +
    `<dl class="readout">` +
    readoutRow("Deducted (server-computed)", r.deducted) +
    readoutRow("New key balance (server-computed)", r.new_balance) +
    readoutRow("Receipt status", r.status) +
    `</dl><p class="fine">Metered and deducted by DCLM on the server. This page only displays the receipt.</p>`;
  if (data.state && data.state.wallet) renderWalletInto(doc, data.state.wallet);
}

/* Bind = a server round-trip. The client renders whatever the server returns.
 * If this handler breaks, the failure mode is "nothing happens and the
 * indicator still shows the last server state" — never a stuck gate. */
export async function requestBind(doc, fetchFn) {
  const note = doc.getElementById("bind-note");
  const setNote = (t) => { if (note) note.textContent = t; };
  setNote("Contacting server…");
  try {
    const data = await postAction(fetchFn, API.bind, {});
    renderWalletInto(doc, data && data.state ? data.state.wallet : undefined);
    setNote(
      data && data.ok === true
        ? "The server reports the Unity ID as bound. The indicator above is the server's answer."
        : "The server declined the bind. State unchanged.",
    );
  } catch (err) {
    setNote("Server unreachable. Nothing changed — the indicator still shows the last server state.");
  }
}

/* The entry ceremony — the doorway. The client REQUESTS; DCLM performs.
 * The client never generates identities: it supplies ceremony material and
 * DCLM derives the Unity ID server-side (bind-then-validate, gate/entry.py).
 * POST /api/world/bind carries { covenant_accepted, ceremony }; DCLM returns
 * the entry envelope or a refusal. A dead button here strands no one: the
 * failure mode is "nothing happens, the doorway stays open." */
export function buildTestnetCeremonyProof() {
  /* TESTNET ONLY. The sandbox stand-in for the device ceremony: 32 bytes of
   * ceremony material, explicitly labeled a stub. Production uses the
   * WebAuthn platform authenticator (SPEC slot — unwired in this build);
   * the derivation rule and the ceremony stay server-side either way. */
  const bytes = new Uint8Array(32);
  const c = typeof crypto !== "undefined" && crypto.getRandomValues ? crypto : null;
  if (c) c.getRandomValues(bytes);
  else for (let i = 0; i < 32; i++) bytes[i] = (Math.random() * 256) | 0;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return {
    kind: "testnet-stub",
    testnet_ceremony: true,
    stub_seed: hex,
    note: "TESTNET ONLY — sandbox stand-in for the device ceremony",
  };
}

function addClass(el, cls) {
  if (el && el.classList && typeof el.classList.add === "function") el.classList.add(cls);
}

function hideEl(el) {
  if (el && el.style) el.style.display = "none";
}

/* The doorway collapses — it was the doorway, not the destination. The world
 * is already in page flow; dismissal just walks the entrant in. */
function dismissGateSection(doc) {
  const section = doc.getElementById("entry-gate");
  hideEl(section);
  const world = doc.getElementById("h-world");
  if (world && typeof world.scrollIntoView === "function") {
    try { world.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (err) { /* never load-bearing */ }
  }
}

/* Normalize receipt ids out of either entry shape: the full ceremony result
 * or the idempotent replay (which nests the existing ignition record). */
function entryReceiptIds(e) {
  if (!e) return {};
  if (e.already && e.entry && e.entry.ignition) {
    const r = e.entry.ignition.receipt || e.entry.ignition;
    return { bind: r.bind_receipt_id, seed: r.seed_id, ignition: null };
  }
  return {
    bind: e.bind && e.bind.receipt_id,
    seed: e.seed && e.seed.seed_id,
    ignition: e.ignition && e.ignition.ignition_id,
  };
}

function renderEntryReceipts(doc, e) {
  const el = doc.getElementById("entry-receipts");
  if (!el || !e) return;
  const ids = entryReceiptIds(e);
  const short = (s) => typeof s === "string" && s.length > 18 ? esc(s.slice(0, 16)) + "…" : esc(s || "—");
  el.innerHTML =
    "entry receipts — bind " + short(ids.bind) +
    " · seed " + short(ids.seed) +
    " · ignition " + short(ids.ignition) +
    " " + badge("VERIFIED");
}

/* The eFuse ignition — the LAUNCH moment, client-side, played IN FLOW where
 * the card stood. The signed spark is the server's ignition record; this is
 * the theatre around it: the card dissolves into the ignition scene, light
 * refracts through diamond geometry (teal → purple → gold), the doorway
 * collapses, and the member is IN. Reduced-motion entrants skip the theatre
 * and walk straight in — the spark is the record, not the animation.
 * Returns a promise that resolves when the moment is over. */
export function playIgnition(doc, data) {
  return new Promise((resolve) => {
    const card = doc.getElementById("gate-card");
    const scene = doc.getElementById("ignition-scene");
    const idEl = doc.getElementById("ignition-unity-id");
    if (idEl) idEl.textContent = (data && data.obfuscated_display) || "";
    const reduced =
      typeof window !== "undefined" && window.matchMedia &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = typeof setTimeout !== "undefined" ? setTimeout : (fn) => { fn(); return 0; };
    if (!scene || reduced) { dismissGateSection(doc); resolve(); return; }
    addClass(card, "dissolved");                 /* the card dissolves… */
    t(() => {
      hideEl(card);
      scene.hidden = false;                      /* …into the ignition */
    }, 620);
    t(() => {                                    /* and they're IN */
      dismissGateSection(doc);
      resolve();
    }, 3000);
  });
}

export async function performEntry(doc, fetchFn) {
  const note = doc.getElementById("entry-status");
  const setNote = (t) => { if (note) note.textContent = t; };
  setNote("Reading the ceremony…");
  let data = null;
  try {
    data = await postAction(fetchFn, API.bind, {
      covenant_accepted: true,
      ceremony: buildTestnetCeremonyProof(),
    });
  } catch (err) {
    data = null;
  }
  if (!data) {
    setNote("Server unreachable. Nothing changed — the doorway is still open.");
    return { ok: false };
  }
  if (data.ok === true && data.entry) {
    /* The full entry envelope: DCLM performed the ceremony. The serving
     * layer wraps it as { ok: true, entry: <envelope> }. */
    const e = data.entry;
    renderWalletInto(doc, {
      status: { value: "BOUND", provenance: "VERIFIED" },
      unity_id: { value: e.obfuscated_display || "UNKNOWN", provenance: "DERIVED" },
      key_balance: { value: "UNKNOWN", provenance: "UNKNOWN" },
    });
    renderEntryReceipts(doc, e);
    setNote(e.already
      ? "Already entered — the doorway was passed. No duplicate spark."
      : "Bound · seed issued · igniting…");
    await playIgnition(doc, e);
    return { ok: true, entry: e };
  }
  if (data.ok === true) {
    /* Older server shape: render what the server returned, no ignition. */
    renderWalletInto(doc, data.state ? data.state.wallet : undefined);
    setNote("The server reports the Unity ID as bound.");
    return { ok: true };
  }
  const refused = data.refused || {};
  setNote("The doorway declined (" + (refused.reason || "unknown") +
    "). Nothing changed — read the card and try again.");
  return { ok: false, refused };
}

export async function meteredAction(doc, fetchFn, action, input) {
  const path = action === "search" ? API.search : API.compute;
  const body = action === "search" ? { query: input } : { params: input };
  let data = null;
  try {
    data = await postAction(fetchFn, path, body);
  } catch (err) {
    data = null;
  }
  renderActionResult(doc, action, data);
}

function wireActions(doc, fetchFn) {
  const on = (id, fn) => {
    const el = doc.getElementById(id);
    if (el && typeof el.addEventListener === "function") {
      el.addEventListener("click", async (ev) => {
        if (ev && typeof ev.preventDefault === "function") ev.preventDefault();
        await fn();
      });
    }
  };
  on("bind-btn", () => requestBind(doc, fetchFn));
  on("entry-accept-btn", () => performEntry(doc, fetchFn));
  on("entry-look-btn", () => dismissGateSection(doc));
  on("search-btn", () => {
    const q = doc.getElementById("search-q");
    return meteredAction(doc, fetchFn, "search", q ? q.value : "");
  });
  on("compute-btn", () => {
    const p = doc.getElementById("compute-p");
    return meteredAction(doc, fetchFn, "compute", p ? p.value : "");
  });
}

function renderWorldSections(doc, chunks, headEpoch) {
  setHtml(doc, "world-state-mount", renderWorldState(chunks, headEpoch));
  setHtml(doc, "atlas-mount", renderAtlas(chunks, headEpoch));
  setHtml(doc, "telemetry-mount", renderTelemetry(chunks, headEpoch));
  setHtml(doc, "feeds-mount", renderFeeds(chunks, headEpoch));
  setHtml(doc, "verdicts-mount", renderVerdicts(chunks, headEpoch));
}

/* Visible epoch indicator. Quiet, in flow, never an overlay: the small
 * marker so two humans never argue about different worlds. */
export function renderEpochInto(doc, headOrEpoch, state) {
  const el = doc.getElementById("epoch-version");
  if (!el) return;
  const epoch = headOrEpoch && typeof headOrEpoch === "object"
    ? headOrEpoch.world_epoch : headOrEpoch;
  const schema = headOrEpoch && typeof headOrEpoch === "object"
    ? headOrEpoch.schema_version : null;
  if (typeof epoch !== "number") {
    el.innerHTML = `UNKNOWN ${badge("UNKNOWN")}`;
    return;
  }
  const s = state === "STALE" ? "STALE" : state === "VERIFIED" ? "VERIFIED" : "UNKNOWN";
  el.innerHTML = `epoch v${epoch}` + (schema !== null && schema !== undefined ? ` · schema v${schema}` : "") + ` ${badge(s)}`;
}

export function renderReadjustNote(doc, text) {
  const el = doc.getElementById("readjust-note");
  if (el) el.textContent = text || "";
}

/* Boot: the initial render NEVER waits on the wire. The playground
 * materializes around the entrant: cached world first (honest UNKNOWN shells
 * when the cache is empty), wallet token + wall of builders alongside, then
 * the progressive sync streams the world in behind. If the connection drops,
 * the cached world still works. */
export async function start(doc, fetchFn) {
  const d = doc || (typeof document !== "undefined" ? document : null);
  const f = fetchFn || (typeof fetch !== "undefined" ? fetch : null);
  if (!d || !f) return { ok: false, shape: { ok: false, missing: ["no document or fetch"] } };

  wireActions(d, f);
  const lod = attachLodController(d);

  /* 1. Cache-first render. Immediate. Never waits for bulk data. */
  let db = null;
  let cachedHead = null;
  let cachedBodies = [];
  try {
    db = await openCacheDb();
    if (db) {
      cachedHead = await cacheReadHead(db);
      const byDataset = await loadCachedWorld(db);
      cachedBodies = Object.values(byDataset).flat();
    }
  } catch (err) {
    db = null;
  }
  const cachedEpoch = cachedHead && typeof cachedHead.epoch === "number" ? cachedHead.epoch : null;
  const cachedChunks = groupByDataset(cachedBodies);
  renderWorldSections(d, cachedChunks, cachedEpoch);
  renderWalletInto(d, undefined);
  renderMeteringInto(d, undefined);
  setHtml(d, "founders-mount", renderFounders(null));
  renderEpochInto(d, cachedHead ? { world_epoch: cachedHead.epoch, schema_version: cachedHead.schema_version } : null,
    cachedHead ? "STALE" : "UNKNOWN");

  /* 2. Wallet token + wall of builders. The wallet is the playground token:
   * looking and entering are free; keys are spent to build and test, never
   * to look. Both are live reads, never cached. */
  let foundersOk = false;
  try {
    const founders = await fetchFounders(f);
    setHtml(d, "founders-mount", renderFounders(founders));
    foundersOk = true;
  } catch (err) {
    setHtml(d, "founders-mount", renderFounders(null));
  }
  let server = null;
  let shape = { ok: false, missing: ["relay unreachable"] };
  try {
    server = await fetchBundle(f);
    shape = verifyBundleShape(server);
  } catch (err) {
    server = null;
    shape = { ok: false, missing: ["relay unreachable"] };
  }
  renderWalletInto(d, server && server.wallet);
  renderMeteringInto(d, server && server.metering);

  /* 3. Progressive sync in the background: head, then prioritized chunks.
   * Cutover closures re-render world sections atomically; the wallet token
   * is untouched by the sync (it stays the server's live answer). */
  const syncPromise = progressiveSync(d, f, db,
    cachedHead ? { epoch: cachedHead.epoch, schema_version: cachedHead.schema_version } : null,
    {
      cachedBodies,
      onFetch: (bytes, ms) => { if (lod) lod.record(bytes, ms); },
      renderProgressive: (chunks, epoch) => renderWorldSections(d, chunks, epoch),
      renderCutover: (chunks, epoch) => renderWorldSections(d, chunks, epoch),
    }).catch(() => ({ ok: false, reason: "sync-error" }));

  return { ok: shape.ok, shape, epoch: cachedEpoch, foundersOk, sync: syncPromise };
}

if (typeof document !== "undefined") {
  start();
}
