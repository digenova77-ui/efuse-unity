/**
 * UNITY-WORLD relay — `dualis.relay.v1.testnet`
 *
 * Layer: PROTOCOL. The convergence architecture is LAW (core-rings) +
 * PROTOCOL (dualis.relay.v1) + WORLD (3D world) + GATES. This file is the
 * PROTOCOL layer for ~/workspace/unity-world/: it carries DCLM-computed
 * state to a thin client. It computes nothing about the world; the website
 * code runs INSIDE DCLM and spits out data — the relay only carries it.
 *
 * Mirrors ~/workspace/testnet/relay/relay-testnet.mjs exactly (schema,
 * envelope discipline, idempotency, gate discipline). Unity-world
 * specializations:
 *   - Envelope types are the protocol's six: TASK / EVIDENCE / VERDICT /
 *     QUERY / KEY_OFFER / ACK. Envelopes, not minds — anything else is
 *     REJECTED.
 *   - VERDICT payloads carry the DCLM WorldState signed envelope verbatim,
 *     exactly as produced by ~/workspace/unity-world/dclm/compute.py
 *     sign_state(): {state, canonical_sha256, signature, algorithm,
 *     key_id, provenance}. The relay never signs and never recomputes
 *     DCLM's decisions; it can PROVE the carried state is DCLM-signed via
 *     verifyWorldState() (Ed25519 over the canonical bytes, testnet key).
 *   - Every bundle carries the GATE envelope from
 *     ~/workspace/unity-world/gate/gate.py emit_gate_envelope():
 *     {schema, type:"GATE", identity, state:"BOUND", receipt_id,
 *     authorizes, issued_at}. The relay refuses any bundle whose gate is
 *     not BOUND for the bundle's own unity_id.
 *   - The Unity identity `unity:testnet:...` rides every bundle.
 *     Non-testnet identities are refused at build and at parse.
 *
 * TESTNET ONLY. The parser REJECTS any bundle whose schema does not end
 * in `.testnet`. Testnet parsers REJECT mainnet bundles and vice versa —
 * the isolation is structural, not conventional.
 *
 * Honesty invariants (same as testnet relay):
 *   - manifest_hash is the one and only idempotency key, end to end.
 *   - Malformed bundles are REJECTED with reasons — never thrown past,
 *     never trusted.
 *   - The relay carries envelopes and receipts only. Never secrets, never
 *     private keys: payloads are scanned for secret-like key names and
 *     refused on a match.
 *   - UNKNOWN is never PASS: a gate envelope that is not BOUND carries
 *     nothing, and no receipt is ever invented.
 *   - David's Unity ID binding is kept as-is: identity rides the bundle,
 *     derived `unity:testnet:` + sha256(test pubkey); the relay does not
 *     mint, alter, or re-derive identities.
 */
import crypto from 'node:crypto'
import fs from 'node:fs'

export const UNITY_RELAY_SCHEMA = 'dualis.relay.v1.testnet'
export const MAINNET_RELAY_SCHEMA = 'dualis.relay.v1' // rejected here, always
export const GATE_SCHEMA = 'unity.gate.v1.testnet'
export const UNITY_ID_PREFIX = 'unity:testnet:'
export const GATE_BOUND = 'BOUND'
export const DCLM_SIGN_ALGORITHM = 'Ed25519'

/** The protocol's envelope types. Envelopes, not minds — nothing else rides. */
export const ENVELOPE_TYPES = Object.freeze([
  'TASK',
  'EVIDENCE',
  'VERDICT',
  'QUERY',
  'KEY_OFFER',
  'ACK',
])

/** Receipt outcomes. Same discipline as the testnet relay. */
export const RECEIPT_OUTCOMES = Object.freeze(['DELIVERED', 'HOLE', 'REJECTED'])

/** Key names that must never appear in a relay payload. The relay carries
 *  envelopes and receipts only — never secrets, never private keys. */
const SECRET_KEY_PATTERN =
  /(private[_-]?key|privkey|privatekey|secret[_-]?key|client[_-]?secret|seed[_-]?phrase|\bseed\b|mnemonic|passw(or|phrase)|bearer[_-]?token|access[_-]?token|api[_-]?key)/i

// ---------------------------------------------------------------------------
// canonical JSON + hashing (byte-compatible with dclm/compute.py for
// ASCII-only states: sorted keys, no whitespace)
// ---------------------------------------------------------------------------

/** Canonical JSON: sorted keys, no whitespace. Same as mainnet chain.ts. */
export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return '[' + value.map(canonicalJson).join(',') + ']'
  const keys = Object.keys(value).sort()
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalJson(value[k])).join(',') + '}'
}

export function sha256Hex(data) {
  return crypto.createHash('sha256').update(data).digest('hex')
}

/** The idempotency key: sha256 of the canonical semantic content of the
 *  bundle. Transit fields (relayed_at, relay_sequence) are NOT hashed —
 *  re-transit of the same content is the same bundle. */
export function bundleHash({ schema, envelope, payload, unityId, gate, reason }) {
  return sha256Hex(canonicalJson({ schema, envelope, payload, unity_id: unityId, gate, reason }))
}

// ---------------------------------------------------------------------------
// structural guards
// ---------------------------------------------------------------------------

/** Fail-closed scan: no secret-like key names anywhere in the payload. */
export function findSecretKey(value, path = '$') {
  if (value === null || typeof value !== 'object') return null
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      const hit = findSecretKey(value[i], `${path}[${i}]`)
      if (hit) return hit
    }
    return null
  }
  for (const k of Object.keys(value)) {
    if (SECRET_KEY_PATTERN.test(k)) return `${path}.${k}`
    const hit = findSecretKey(value[k], `${path}.${k}`)
    if (hit) return hit
  }
  return null
}

function isNonEmptyString(v) {
  return typeof v === 'string' && v.length > 0
}

/** Structural check of the DCLM signed envelope carried in VERDICT
 *  payloads. This is structure only — cryptographic verification is
 *  verifyWorldState(). The relay never claims a forged-looking envelope
 *  is genuine. */
export function checkDclmEnvelope(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { ok: false, reason: 'REJECTED · VERDICT payload is not a DCLM envelope object' }
  }
  if (!payload.state || typeof payload.state !== 'object' || Array.isArray(payload.state)) {
    return { ok: false, reason: 'REJECTED · VERDICT payload missing DCLM `state` dict' }
  }
  if (!/^[0-9a-f]{64}$/.test(String(payload.canonical_sha256 || ''))) {
    return { ok: false, reason: 'REJECTED · VERDICT payload missing valid DCLM `canonical_sha256`' }
  }
  if (!isNonEmptyString(payload.signature)) {
    return { ok: false, reason: 'REJECTED · VERDICT payload missing DCLM `signature`' }
  }
  if (payload.algorithm !== DCLM_SIGN_ALGORITHM) {
    return { ok: false, reason: `REJECTED · VERDICT payload algorithm is not ${DCLM_SIGN_ALGORITHM}` }
  }
  return { ok: true }
}

/** Structural check of the GATE envelope authorizing flow to the bound
 *  identity. Comes from gate.py emit_gate_envelope(); must be BOUND and
 *  must name the bundle's own unity_id. UNKNOWN / UNBOUND / BINDING /
 *  mismatched identity → refused. UNKNOWN is never PASS. */
export function checkGateEnvelope(gate, unityId) {
  if (!gate || typeof gate !== 'object' || Array.isArray(gate)) {
    return { ok: false, reason: 'REJECTED · bundle missing GATE envelope' }
  }
  if (!String(gate.schema || '').endsWith('.testnet') || gate.schema !== GATE_SCHEMA) {
    return { ok: false, reason: `REJECTED · GATE envelope schema must be ${GATE_SCHEMA}` }
  }
  if (gate.type !== 'GATE') {
    return { ok: false, reason: 'REJECTED · GATE envelope type is not GATE' }
  }
  if (gate.state !== GATE_BOUND) {
    return { ok: false, reason: `REJECTED · gate is ${gate.state || 'UNKNOWN'}, not BOUND — no flow without a completed binding` }
  }
  if (gate.identity !== unityId) {
    return { ok: false, reason: 'REJECTED · GATE envelope identity does not match bundle unity_id' }
  }
  if (!isNonEmptyString(gate.receipt_id)) {
    return { ok: false, reason: 'REJECTED · GATE envelope missing receipt_id' }
  }
  return { ok: true }
}

// ---------------------------------------------------------------------------
// bundle construction (fail-closed: throws, never produces a half-bundle)
// ---------------------------------------------------------------------------

/**
 * Build a unity-world relay bundle.
 *
 * Required: envelope (one of ENVELOPE_TYPES), payload (object),
 * unityId (`unity:testnet:...`), gate (BOUND GATE envelope for unityId),
 * reason (why this bundle exists).
 */
export function createBundle({ envelope, payload, unityId, gate, reason, relayedAt, relaySequence }) {
  if (!envelope || !payload || !unityId || !gate || !reason) {
    throw new Error('REJECTED · relay bundle missing required field')
  }
  if (!ENVELOPE_TYPES.includes(envelope)) {
    throw new Error(`REJECTED · unknown envelope type ${String(envelope)} — envelopes, not minds`)
  }
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new Error('REJECTED · relay payload must be an object')
  }
  if (!String(unityId).startsWith(UNITY_ID_PREFIX)) {
    throw new Error(`REJECTED · relay requires a testnet Unity ID (${UNITY_ID_PREFIX}...)`)
  }
  const gateCheck = checkGateEnvelope(gate, unityId)
  if (!gateCheck.ok) throw new Error(gateCheck.reason)
  const secretHit = findSecretKey(payload)
  if (secretHit) {
    throw new Error(`REJECTED · payload carries secret-like key ${secretHit} — the relay never carries secrets`)
  }
  if (envelope === 'VERDICT') {
    const dclmCheck = checkDclmEnvelope(payload)
    if (!dclmCheck.ok) throw new Error(dclmCheck.reason)
  }
  const bundle = {
    schema: UNITY_RELAY_SCHEMA,
    manifest_hash: bundleHash({ schema: UNITY_RELAY_SCHEMA, envelope, payload, unityId, gate, reason }),
    envelope,
    payload,
    unity_id: unityId,
    gate,
    reason,
    relayed_at: relayedAt || new Date().toISOString(),
    relay_sequence: relaySequence ?? 0,
  }
  return bundle
}

/**
 * Convenience builder for VERDICT bundles: carries the DCLM WorldState
 * signed envelope (exactly as dclm/compute.py sign_state() produced it)
 * to the bound Unity identity.
 */
export function createVerdictBundle({ worldState, unityId, gate, reason, relayedAt, relaySequence }) {
  if (!worldState) throw new Error('REJECTED · VERDICT bundle missing DCLM worldState envelope')
  const dclmCheck = checkDclmEnvelope(worldState)
  if (!dclmCheck.ok) throw new Error(dclmCheck.reason)
  return createBundle({
    envelope: 'VERDICT',
    payload: worldState,
    unityId,
    gate,
    reason: reason || 'VERDICT · DCLM-computed world state for the bound identity',
    relayedAt,
    relaySequence,
  })
}

// ---------------------------------------------------------------------------
// strict parsing (fail-closed: returns {ok:false, reason}, never throws past)
// ---------------------------------------------------------------------------

/**
 * Parse a unity-world relay bundle. Strict: returns {ok:false, reason}
 * on anything wrong — including a MAINNET bundle (schema mismatch),
 * a non-testnet identity, a non-BOUND gate, a secret-carrying payload,
 * or a manifest_hash that does not match the content.
 */
export function parseBundle(json) {
  let obj
  try {
    obj = typeof json === 'string' ? JSON.parse(json) : json
  } catch {
    return { ok: false, reason: 'REJECTED · not valid JSON' }
  }
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
    return { ok: false, reason: 'REJECTED · not an object' }
  }
  if (obj.schema === MAINNET_RELAY_SCHEMA) {
    return { ok: false, reason: 'REJECTED · mainnet bundle in unity relay — schema mismatch, refusing' }
  }
  if (!String(obj.schema || '').endsWith('.testnet') || obj.schema !== UNITY_RELAY_SCHEMA) {
    return { ok: false, reason: `REJECTED · unknown schema ${String(obj.schema)} — unity relay accepts only ${UNITY_RELAY_SCHEMA}` }
  }
  for (const f of ['manifest_hash', 'envelope', 'payload', 'unity_id', 'gate', 'reason', 'relayed_at']) {
    if (obj[f] === undefined || obj[f] === null || obj[f] === '') {
      return { ok: false, reason: `REJECTED · missing field ${f}` }
    }
  }
  if (!ENVELOPE_TYPES.includes(obj.envelope)) {
    return { ok: false, reason: `REJECTED · unknown envelope type ${String(obj.envelope)} — envelopes, not minds` }
  }
  if (!String(obj.unity_id).startsWith(UNITY_ID_PREFIX)) {
    return { ok: false, reason: 'REJECTED · non-testnet Unity ID in unity bundle' }
  }
  const gateCheck = checkGateEnvelope(obj.gate, obj.unity_id)
  if (!gateCheck.ok) return gateCheck
  const secretHit = findSecretKey(obj.payload)
  if (secretHit) {
    return { ok: false, reason: `REJECTED · payload carries secret-like key ${secretHit} — the relay never carries secrets` }
  }
  if (obj.envelope === 'VERDICT') {
    const dclmCheck = checkDclmEnvelope(obj.payload)
    if (!dclmCheck.ok) return dclmCheck
  }
  // Tamper-evident: the manifest hash must match the semantic content.
  const recomputed = bundleHash({
    schema: obj.schema,
    envelope: obj.envelope,
    payload: obj.payload,
    unityId: obj.unity_id,
    gate: obj.gate,
    reason: obj.reason,
  })
  if (recomputed !== obj.manifest_hash) {
    return { ok: false, reason: 'REJECTED · manifest_hash does not match bundle content' }
  }
  return { ok: true, value: obj }
}

// ---------------------------------------------------------------------------
// cryptographic proof that the carried VERDICT state is DCLM-signed
// ---------------------------------------------------------------------------

/**
 * Verify the Ed25519 signature on the DCLM envelope carried in a VERDICT
 * payload, against a DER SPKI public key file (testnet only — the
 * unity-world test key). Returns {ok:true} only when the signature
 * verifies over the canonical bytes of `payload.state`.
 *
 * Note: canonical bytes here are byte-identical to dclm/compute.py's
 * _canonical_bytes for ASCII-only states (sorted keys, compact
 * separators, same string escaping). For states with non-ASCII content,
 * use dclm/compute.py verify_envelope() instead — this function will
 * honestly report a mismatch rather than claim verification.
 */
export function verifyWorldState(payload, pubkeyPath) {
  const structural = checkDclmEnvelope(payload)
  if (!structural.ok) return structural
  let pubkey
  try {
    pubkey = crypto.createPublicKey({ key: fs.readFileSync(pubkeyPath), format: 'der', type: 'spki' })
  } catch {
    return { ok: false, reason: 'REJECTED · cannot load DCLM public key' }
  }
  const canonical = Buffer.from(canonicalJson(payload.state), 'utf8')
  const expected = sha256Hex(canonical)
  if (expected !== payload.canonical_sha256) {
    return { ok: false, reason: 'REJECTED · payload canonical_sha256 does not match the carried state' }
  }
  let sig
  try {
    sig = Buffer.from(String(payload.signature), 'base64')
  } catch {
    return { ok: false, reason: 'REJECTED · payload signature is not valid base64' }
  }
  const ok = crypto.verify(null, canonical, pubkey, sig)
  return ok
    ? { ok: true }
    : { ok: false, reason: 'REJECTED · DCLM signature does not verify over the carried state' }
}

// ---------------------------------------------------------------------------
// receipts (mirror the testnet relay: never invented)
// ---------------------------------------------------------------------------

export function toReceipt({ manifestHash, outcome, reason, receipt, answeredAt }) {
  if (!RECEIPT_OUTCOMES.includes(outcome)) {
    throw new Error('REJECTED · invalid receipt outcome')
  }
  if (!isNonEmptyString(manifestHash)) {
    throw new Error('REJECTED · receipt missing manifest_hash')
  }
  if (outcome === 'DELIVERED' && receipt === undefined) {
    throw new Error('REJECTED · DELIVERED without a receipt is malformed — receipts are never invented')
  }
  return {
    schema: UNITY_RELAY_SCHEMA,
    manifest_hash: manifestHash,
    outcome,
    reason: reason || '',
    ...(receipt !== undefined ? { receipt } : {}),
    answered_at: answeredAt || new Date().toISOString(),
  }
}

export function fromReceipt(json) {
  let obj
  try {
    obj = typeof json === 'string' ? JSON.parse(json) : json
  } catch {
    return { ok: false, reason: 'REJECTED · not valid JSON' }
  }
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
    return { ok: false, reason: 'REJECTED · not an object' }
  }
  if (obj.schema !== UNITY_RELAY_SCHEMA) {
    return { ok: false, reason: 'REJECTED · schema mismatch on receipt' }
  }
  if (!obj.manifest_hash || !obj.outcome) {
    return { ok: false, reason: 'REJECTED · receipt missing fields' }
  }
  if (!RECEIPT_OUTCOMES.includes(obj.outcome)) {
    return { ok: false, reason: 'REJECTED · unknown receipt outcome' }
  }
  if (obj.outcome === 'DELIVERED' && obj.receipt === undefined) {
    return { ok: false, reason: 'REJECTED · DELIVERED without receipt — never invented' }
  }
  return { ok: true, value: obj }
}

// ---------------------------------------------------------------------------
// outbox: deliver() with idempotency by manifest_hash
// ---------------------------------------------------------------------------

/**
 * The relay outbox. deliver() parses strictly, then:
 *   - parse failure            → REJECTED receipt, nothing stored
 *   - manifest_hash seen before → no-op: returns the ORIGINAL receipt,
 *                                 no new receipt minted, nothing stored
 *   - otherwise                 → stores the bundle, mints one DELIVERED
 *                                 receipt
 *
 * Doing it twice = doing it once. An optional receiptLogPath appends
 * every minted receipt as JSONL (mutation log with before/after bundle
 * count); without it the ledger is in-memory only.
 */
export class Outbox {
  constructor({ receiptLogPath = null } = {}) {
    this._bundles = new Map() // manifest_hash -> bundle
    this._receipts = new Map() // manifest_hash -> receipt
    this._receiptLogPath = receiptLogPath
  }

  size() {
    return this._bundles.size
  }

  has(manifestHash) {
    return this._bundles.has(manifestHash)
  }

  receipts() {
    return [...this._receipts.values()]
  }

  _logReceipt(receipt) {
    if (!this._receiptLogPath) return
    const entry = { ...receipt, outbox_size_after: this._bundles.size }
    fs.appendFileSync(this._receiptLogPath, JSON.stringify(entry) + '\n')
  }

  deliver(input) {
    const parsed = parseBundle(input)
    if (!parsed.ok) {
      const receipt = toReceipt({
        manifestHash: 'UNKNOWN',
        outcome: 'REJECTED',
        reason: parsed.reason,
      })
      return { ok: false, delivered: false, manifest_hash: 'UNKNOWN', receipt, reason: parsed.reason }
    }
    const bundle = parsed.value
    const hash = bundle.manifest_hash
    if (this._bundles.has(hash)) {
      // Idempotent no-op: the original receipt stands. Nothing new minted.
      return {
        ok: true,
        delivered: false,
        manifest_hash: hash,
        receipt: this._receipts.get(hash),
        reason: 'no-op · bundle already delivered (idempotent re-delivery)',
      }
    }
    this._bundles.set(hash, bundle)
    const receipt = toReceipt({
      manifestHash: hash,
      outcome: 'DELIVERED',
      reason: 'bundle accepted by the unity relay',
      receipt: { unity_id: bundle.unity_id, envelope: bundle.envelope, relay_sequence: bundle.relay_sequence },
    })
    this._receipts.set(hash, receipt)
    this._logReceipt(receipt)
    return { ok: true, delivered: true, manifest_hash: hash, receipt }
  }
}

// ---------------------------------------------------------------------------
// portable export: what gets pinned under a TEST CID
// ---------------------------------------------------------------------------

export function exportRelay(bundles, exporter = 'dualis.unity.v1.testnet') {
  const seen = new Set()
  const deduped = []
  for (const b of [...bundles].sort((a, b2) => (a.relay_sequence ?? 0) - (b2.relay_sequence ?? 0))) {
    if (!b || seen.has(b.manifest_hash)) continue
    seen.add(b.manifest_hash)
    deduped.push(b)
  }
  return {
    schema: UNITY_RELAY_SCHEMA,
    exported_at: new Date().toISOString(),
    exporter,
    bundles: deduped,
  }
}
