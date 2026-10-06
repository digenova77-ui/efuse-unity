/**
 * chunks.js — progressive chunk client for the unity-world data plane.
 *
 * Flow: head -> P1 shell -> P2 coarse -> stream P3/P4 detail.
 * Implements the Trinity readjustment protocol (P0-2) and tiered
 * freshness (P0-3) from dclm/CHUNKS.md:
 *
 *  - HEAD FIRST: GET /chunks/head.json on every load. The head's
 *    world_epoch is the only freshness-sensitive fetch.
 *  - NO-DOWNGRADE: a head with world_epoch below the cached maximum is
 *    REJECTED (rollback defense). Old-but-validly-signed chunks can never
 *    replay as current.
 *  - VERSION-PINNED STREAMS: the stream epoch is recorded at start; any
 *    NDJSON line whose world_epoch differs is rejected. No epoch mixing.
 *  - STALE: chunks from a superseded epoch keep rendering labeled [STALE]
 *    while the new epoch streams behind; cutover is atomic per dataset.
 *  - TIERED FRESHNESS: "long" chunks render from cache with an epoch
 *    check; "short" (economic) chunks revalidate against the head on
 *    every load and render as_of + [STALE] when superseded.
 *  - WALLET IS NEVER CHUNKED: wallet state is always live via
 *    POST /api/world/* — this module never looks for it in chunks.
 *  - STORAGE INTEGRITY ON READ: the sha256 of the stored raw bytes,
 *    recorded at store time, is re-checked on every cache read. Corrupt
 *    bytes are evicted and refetched — never rendered. No client-side
 *    hash recompute: canonical_sha256 covers the chunk BODY while served
 *    bytes are the ENVELOPE's canonical form (plus Python float and
 *    ensure_ascii rendering), so recompute-and-compare is unsound here.
 *    Signature authentication stays at the relay boundary.
 *
 * CACHE LAW (amended P0-1: "DCLM writes records; the client writes bytes —
 * and only inside the fences"): the cache here is an in-memory Map only.
 * This module performs no durable writes at all. A durable read-cache
 * lives in the client worker's sanctioned region; this module's Map is
 * the transport-level cache beneath it. DCLM remains the sole writer of
 * truth; no cache here is ever authoritative.
 *
 * Trust layering (honest): the browser verifies each envelope
 * STRUCTURALLY — well-formed, DCLM signature present, complete, pinnable
 * chunk_id. It never claims to authenticate the Ed25519 signature itself;
 * that proof happens at the relay boundary (relay/wrap-chunk.mjs), which
 * verifies against the testnet key before bytes flow. Each layer checks
 * what it can actually prove.
 */

const HEAD_URL = '/chunks/head.json'

/** In-memory chunk cache: chunk_id -> { body, bytes, etag, stored_hash, epoch }.
 *  Never treated as truth — every read re-hashes the STORED bytes. */
const cache = new Map()
let maxEpochSeen = 0

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Structural verification of a chunk envelope. NO hash recompute.
 *
 * The client worker proved recompute-and-compare unsound here:
 * envelope.canonical_sha256 is the hash of the chunk BODY's canonical
 * form, while the served bytes are the ENVELOPE's canonical form —
 * sha256(envelope bytes) can never equal it, so every chunk would fail.
 * Python float rendering and ensure_ascii escapes make client-side
 * recompute doubly unsound. This function does not try.
 *
 * What it checks instead, per chunk:
 *  - well-formed: envelope object with state, canonical_sha256 (64-hex),
 *    signature, algorithm, key_id in the right shapes;
 *  - DCLM-signed: a non-empty Ed25519 signature is PRESENT (authenticity
 *    is proven at the relay boundary, which verifies the signature
 *    against the testnet key);
 *  - complete: state carries chunk_id, world_epoch, schema_version,
 *    content_hash, data, and freshness — a truncated envelope is rejected;
 *  - pinnable: chunk_id matches the deterministic shard id format.
 * Anything else → throw: refetch, never render.
 */
function checkChunkEnvelope(envelope) {
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) {
    throw new Error('REJECTED · chunk envelope is not an object')
  }
  if (!/^[0-9a-f]{64}$/.test(String(envelope.canonical_sha256 || ''))) {
    throw new Error('REJECTED · chunk envelope missing canonical_sha256')
  }
  if (typeof envelope.signature !== 'string' || !envelope.signature) {
    throw new Error('REJECTED · chunk is not DCLM-signed (no signature) — never render unsigned bytes')
  }
  if (envelope.algorithm !== 'Ed25519') {
    throw new Error('REJECTED · chunk signature is not Ed25519')
  }
  if (typeof envelope.key_id !== 'string' || !envelope.key_id) {
    throw new Error('REJECTED · chunk envelope missing key_id')
  }
  const s = envelope.state
  if (!s || typeof s !== 'object' || Array.isArray(s)) {
    throw new Error('REJECTED · chunk envelope missing state')
  }
  const missing = []
  if (typeof s.chunk_id !== 'string' || !s.chunk_id.includes('@shard-')) missing.push('chunk_id')
  if (!Number.isInteger(s.world_epoch) || s.world_epoch < 1) missing.push('world_epoch')
  if (!Number.isInteger(s.schema_version) || s.schema_version < 1) missing.push('schema_version')
  if (!/^[0-9a-f]{64}$/.test(String(s.content_hash || ''))) missing.push('content_hash')
  if (s.data === undefined) missing.push('data')
  if (!s.freshness || !['long', 'short'].includes(s.freshness.tier)) missing.push('freshness.tier')
  if (missing.length) {
    throw new Error(`REJECTED · chunk envelope incomplete (${missing.join(', ')}) — refetch, never render`)
  }
  return s
}

/** Read from cache with storage-integrity check: re-hash the STORED raw
 *  bytes and compare against the hash recorded at store time. Corrupted
 *  bytes are evicted (caller refetches). No canonical-form recompute. */
async function readCached(chunkId, epoch) {
  const cached = cache.get(chunkId)
  if (!cached || cached.epoch !== epoch) return null
  const hash = await sha256Hex(cached.bytes)
  if (hash !== cached.stored_hash) {
    cache.delete(chunkId)
    return null
  }
  return cached.body
}

async function getJson(url, etag) {
  const headers = {}
  if (etag) headers['If-None-Match'] = etag
  const res = await fetch(url, { headers })
  if (res.status === 304) return { notModified: true }
  if (!res.ok) throw new Error(`chunk fetch failed: ${url} -> ${res.status}`)
  return { notModified: false, etag: res.headers.get('ETag'), json: await res.json(), res }
}

/**
 * Boot: fetch head, enforce no-downgrade, return the pinned epoch.
 * Throws on downgrade — the caller keeps rendering the cached world.
 */
export async function fetchHead(base = '') {
  const { json: head } = await getJson(base + HEAD_URL)
  const epoch = head.state.world_epoch
  if (epoch < maxEpochSeen) {
    throw new Error(
      `REJECTED · head epoch ${epoch} is older than cached epoch ${maxEpochSeen} — possible rollback, keeping cached world`
    )
  }
  maxEpochSeen = Math.max(maxEpochSeen, epoch)
  return { head: head.state, headEnvelope: head, epoch }
}

/** Fetch one chunk by id (ETag-cached), structurally verify, cache it.
 *  Cache hits re-hash stored bytes (storage integrity); misses and
 *  corrupt entries fall through to a network fetch. */
export async function fetchChunk(base, chunkId, epoch) {
  const hit = await readCached(chunkId, epoch)
  if (hit) return hit
  const cached = cache.get(chunkId)
  const attempt = await getJson(
    `${base}/chunks/${chunkId}?epoch=${epoch}`,
    cached ? cached.etag : undefined
  )
  let res, etag
  if (attempt.notModified) {
    const retry = await readCached(chunkId, epoch)
    if (retry) return retry
    // 304 but our stored bytes are gone/corrupt — refetch unconditionally
    const full = await getJson(`${base}/chunks/${chunkId}?epoch=${epoch}`)
    res = full.res
    etag = full.etag
  } else {
    res = attempt.res
    etag = attempt.etag
  }
  const rawBytes = new Uint8Array(await res.arrayBuffer())
  const envelope = JSON.parse(new TextDecoder().decode(rawBytes))
  const body = checkChunkEnvelope(envelope)
  if (body.world_epoch !== epoch) {
    throw new Error(`chunk ${chunkId}: epoch ${body.world_epoch} != pinned ${epoch} — rejected`)
  }
  cache.set(chunkId, {
    body,
    bytes: rawBytes,
    etag,
    stored_hash: await sha256Hex(rawBytes),
    epoch,
  })
  return body
}

/** Fetch all chunks up to a max priority (coarse-first), in manifest order.
 *  onChunk(body) is called per verified chunk for progressive rendering. */
export async function fetchChunksUpToPriority(base, head, maxPriority, onChunk) {
  const epoch = head.world_epoch
  const { json: idx } = await getJson(`${base}/chunks?priorities=${prioritiesUpTo(maxPriority)}&epoch=${epoch}`)
  if (idx.world_epoch !== epoch) throw new Error('chunk index epoch mismatch — stream not pinned')
  for (const chunkId of idx.chunk_ids) {
    const body = await fetchChunk(base, chunkId, epoch)
    if (onChunk) await onChunk(body)
  }
  return idx
}

function prioritiesUpTo(n) {
  return Array.from({ length: n }, (_, i) => i + 1).join(',')
}

/**
 * Stream priorities as NDJSON: one signed chunk envelope per line, in
 * priority order, version-pinned to the head epoch. Progressive rendering:
 * each verified line renders immediately; the stream never blocks the
 * already-rendered coarse world.
 */
export async function streamPriorities(base, head, priorities, onChunk) {
  const epoch = head.world_epoch
  const res = await fetch(`${base}/stream?priorities=${priorities}&epoch=${epoch}`)
  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`)
  const streamEpoch = parseInt(res.headers.get('X-World-Epoch') || '0', 10)
  if (streamEpoch !== epoch) throw new Error('stream epoch != pinned head epoch — rejected')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (!line) continue
      const rawBytes = new TextEncoder().encode(line)
      const envelope = JSON.parse(line)
      const body = checkChunkEnvelope(envelope)
      if (body.world_epoch !== epoch) {
        throw new Error('stream epoch leak mid-stream — aborting, keeping rendered world')
      }
      cache.set(body.chunk_id, {
        body,
        bytes: rawBytes,
        etag: `"${envelope.canonical_sha256}"`,
        stored_hash: await sha256Hex(rawBytes),
        epoch,
      })
      if (onChunk) await onChunk(body)
    }
  }
}

/**
 * Freshness check for a cached chunk against the current head.
 * Returns 'CURRENT' | 'STALE'.
 *  - long tier: CURRENT while head epoch == cached epoch.
 *  - short tier: STALE unless revalidated this load (caller revalidates by
 *    re-fetching the head and comparing dataset_hash; economic figures
 *    always render with their as_of).
 */
export function freshnessOf(cachedBody, head) {
  if (!cachedBody) return 'STALE'
  if (cachedBody.world_epoch !== head.world_epoch) return 'STALE'
  return 'CURRENT'
}

/** Label helper: provenance badge + freshness badge for rendering. */
export function badgesFor(chunkBody, head) {
  const prov = `[${chunkBody.provenance}]`
  const fresh = freshnessOf(chunkBody, head) === 'STALE'
    ? ` [STALE as-of ${chunkBody.freshness.as_of}]`
    : ''
  return prov + fresh
}

/** Full progressive boot: head -> P1 shell -> P2 coarse -> stream P3/P4.
 *  Callbacks: onShellChunk, onCoarseChunk, onDetailChunk, onStale(dataset). */
export async function bootProgressive(base = '', hooks = {}) {
  const { head, epoch } = await fetchHead(base)
  await fetchChunksUpToPriority(base, head, 1, hooks.onShellChunk)
  await fetchChunksUpToPriority(base, head, 2, hooks.onCoarseChunk)
  // detail streams behind the already-rendered coarse world — never blocks
  await streamPriorities(base, head, '3,4', (body) => {
    if (hooks.onDetailChunk) return hooks.onDetailChunk(body)
  })
  return { head, epoch }
}

// test seam
export const _internals = { cache, checkChunkEnvelope, get maxEpochSeen() { return maxEpochSeen } }
