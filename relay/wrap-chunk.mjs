/**
 * wrap-chunk.mjs — wrap a DCLM-signed chunk envelope into a
 * dualis.relay.v1.testnet EVIDENCE bundle, or verify a wrapped bundle.
 *
 * Chunks are relay bundles: the chunk endpoint is the free-to-look data
 * plane (world viewing needs no binding); when a chunk must flow through
 * the relay to a BOUND identity, this helper wraps the signed chunk
 * envelope as an EVIDENCE payload. The relay's own checks apply unchanged:
 * BOUND gate for the bundle's unity_id, no secret-like keys, testnet only.
 *
 * Usage:
 *   node wrap-chunk.mjs wrap <chunk-envelope.json> <gate.json> <unity-id> [reason]
 *   node wrap-chunk.mjs verify <bundle.json>
 *
 * TESTNET ONLY.
 */
import fs from 'node:fs'
import { createBundle, parseBundle, ENVELOPE_TYPES } from './relay-unity.mjs'

if (!ENVELOPE_TYPES.includes('EVIDENCE')) {
  console.error('REJECTED · relay has no EVIDENCE envelope type')
  process.exit(1)
}

function readJson(path) {
  return JSON.parse(fs.readFileSync(path, 'utf8'))
}

/** Structural check of a DCLM-signed chunk envelope (same discipline as
 *  checkDclmEnvelope: structure only — the signature itself verifies via
 *  dclm/compute.py verify_envelope or relay verifyWorldState). */
function checkChunkEnvelope(env) {
  if (!env || typeof env !== 'object' || Array.isArray(env)) {
    return 'REJECTED · chunk envelope is not an object'
  }
  const s = env.state
  if (!s || typeof s !== 'object' || Array.isArray(s)) {
    return 'REJECTED · chunk envelope missing `state` dict'
  }
  if (!String(s.chunk_id || '').includes('@shard-')) {
    return 'REJECTED · chunk envelope state is not a chunk (missing chunk_id)'
  }
  if (!Number.isInteger(s.world_epoch) || s.world_epoch < 1) {
    return 'REJECTED · chunk envelope missing valid world_epoch (rollback defense needs it)'
  }
  if (!Number.isInteger(s.schema_version) || s.schema_version < 1) {
    return 'REJECTED · chunk envelope missing valid schema_version'
  }
  if (!s.freshness || !['long', 'short'].includes(s.freshness.tier)) {
    return 'REJECTED · chunk envelope missing freshness tier (P0-3)'
  }
  if (!/^[0-9a-f]{64}$/.test(String(env.canonical_sha256 || ''))) {
    return 'REJECTED · chunk envelope missing valid canonical_sha256'
  }
  if (typeof env.signature !== 'string' || !env.signature) {
    return 'REJECTED · chunk envelope missing signature'
  }
  if (env.algorithm !== 'Ed25519') {
    return 'REJECTED · chunk envelope algorithm is not Ed25519'
  }
  return null
}

const [cmd, ...args] = process.argv.slice(2)

if (cmd === 'wrap') {
  const [chunkPath, gatePath, unityId, reason] = args
  if (!chunkPath || !gatePath || !unityId) {
    console.error('usage: wrap <chunk-envelope.json> <gate.json> <unity-id> [reason]')
    process.exit(1)
  }
  const chunk = readJson(chunkPath)
  const chunkProblem = checkChunkEnvelope(chunk)
  if (chunkProblem) {
    console.error(chunkProblem)
    process.exit(1)
  }
  const gate = readJson(gatePath)
  let bundle
  try {
    bundle = createBundle({
      envelope: 'EVIDENCE',
      payload: chunk,
      unityId,
      gate,
      reason: reason || `CHUNK · DCLM-signed data chunk ${chunk.state.chunk_id} (epoch ${chunk.state.world_epoch}) for the bound identity`,
    })
  } catch (e) {
    console.error(String(e.message || e))
    process.exit(1)
  }
  process.stdout.write(JSON.stringify(bundle))
} else if (cmd === 'verify') {
  const [bundlePath] = args
  if (!bundlePath) {
    console.error('usage: verify <bundle.json>')
    process.exit(1)
  }
  const parsed = parseBundle(readJson(bundlePath))
  if (!parsed.ok) {
    console.error(parsed.reason)
    process.exit(1)
  }
  const chunkProblem = checkChunkEnvelope(parsed.value.payload)
  if (chunkProblem) {
    console.error(chunkProblem)
    process.exit(1)
  }
  process.stdout.write(JSON.stringify({ ok: true, chunk_id: parsed.value.payload.state.chunk_id }))
} else {
  console.error('usage: wrap|verify ...')
  process.exit(1)
}
