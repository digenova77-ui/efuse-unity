/**
 * UNITY-WORLD relay unit tests. TESTNET ONLY.
 * Run: node relay-unity.test.mjs
 *
 * Integration is REAL, not stubbed:
 *   - the VERDICT payload is signed by dclm/compute.py sign_state()
 *     (Ed25519, unity-world test key) via a python3 subprocess;
 *   - the GATE envelope is emitted by gate/gate.py UnityGate
 *     (request_bind -> confirm_bind -> emit_gate_envelope) in a temp
 *     state dir. confirm_bind uses a clearly-labeled TEST STUB verifier
 *     (simulated phone ceremony, NOT real WebAuthn) — the exact pattern
 *     gate.py documents for tests.
 */
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {
  UNITY_RELAY_SCHEMA,
  ENVELOPE_TYPES,
  bundleHash,
  canonicalJson,
  sha256Hex,
  findSecretKey,
  checkDclmEnvelope,
  checkGateEnvelope,
  createBundle,
  createVerdictBundle,
  parseBundle,
  verifyWorldState,
  toReceipt,
  fromReceipt,
  Outbox,
  exportRelay,
} from './relay-unity.mjs'

const RELAY_DIR = path.dirname(new URL(import.meta.url).pathname)
const WORLD_DIR = path.resolve(RELAY_DIR, '..')
const DCLM_DIR = path.join(WORLD_DIR, 'dclm')
const GATE_DIR = path.join(WORLD_DIR, 'gate')
const PUBKEY_PATH = path.join(WORLD_DIR, 'keys', 'unity-world-test.pub')

let pass = 0, fail = 0
function t(name, cond) {
  if (cond) { pass++; console.log(`  PASS ${name}`) }
  else { fail++; console.log(`  FAIL ${name}`) }
}

// --- real DCLM signed envelope (python3 + the real test key) ----------------
function realDclmEnvelope(state) {
  const py = `
import sys, json
sys.path.insert(0, ${JSON.stringify(DCLM_DIR)})
from compute import sign_state
state = json.loads(sys.stdin.read())
print(json.dumps(sign_state(state)))
`
  const out = execFileSync('python3', ['-c', py], {
    input: JSON.stringify(state),
    encoding: 'utf8',
  })
  return JSON.parse(out)
}

// --- real GATE envelope (python3 UnityGate, temp state dir, TEST STUB verifier) ---
function realGateEnvelope() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'unity-gate-test-'))
  const py = `
import sys, json
sys.path.insert(0, ${JSON.stringify(GATE_DIR)})
from gate import UnityGate, VerificationResult, THE_TEST_IDENTITY
g = UnityGate(state_dir=${JSON.stringify(tmp)})
g.request_bind(THE_TEST_IDENTITY)
# TEST STUB verifier: simulates the phone ceremony. NOT real WebAuthn.
# gate.py explicitly documents this injection pattern for tests.
stub = lambda identity, proof: VerificationResult(
    status="VERIFIED", detail="TEST STUB — simulated ceremony, not WebAuthn")
g.confirm_bind(THE_TEST_IDENTITY, {"simulated": True}, verifier=stub)
print(json.dumps(g.emit_gate_envelope(THE_TEST_IDENTITY)))
`
  const out = execFileSync('python3', ['-c', py], { encoding: 'utf8' })
  return JSON.parse(out)
}

console.log('relay-unity unit tests (testnet)')

const WORLD_STATE = {
  tick: 7,
  orbs: [{ id: 'a', hue: 174 }, { id: 'b', hue: 271 }],
  note: 'unity relay round-trip fixture',
}
const dclmEnv = realDclmEnvelope(WORLD_STATE)
t('dclm envelope signed by compute.py', dclmEnv.algorithm === 'Ed25519' && /^[0-9a-f]{64}$/.test(dclmEnv.canonical_sha256))

const gateEnv = realGateEnvelope()
t('gate envelope emitted BOUND for the test identity', gateEnv.schema === 'unity.gate.v1.testnet' && gateEnv.type === 'GATE' && gateEnv.state === 'BOUND')
const UNITY_ID = gateEnv.identity
t('test identity is a testnet unity id', UNITY_ID.startsWith('unity:testnet:'))

// --- build a VERDICT bundle carrying the real DCLM state ---------------------
const bundle = createVerdictBundle({
  worldState: dclmEnv,
  unityId: UNITY_ID,
  gate: gateEnv,
  reason: 'VERDICT · DCLM world state to the bound test identity',
  relaySequence: 3,
})
t('bundle has testnet schema', bundle.schema === UNITY_RELAY_SCHEMA)
t('bundle has 64-hex manifest_hash', typeof bundle.manifest_hash === 'string' && bundle.manifest_hash.length === 64)
t('bundle envelope is VERDICT', bundle.envelope === 'VERDICT')
t('bundle carries the unity id', bundle.unity_id === UNITY_ID)

// --- round-trip: DCLM state dict -> VERDICT bundle -> parse -> identical -----
const parsed = parseBundle(JSON.stringify(bundle))
t('bundle round-trips through the strict parser', parsed.ok === true)
t('parsed state identical to DCLM output',
  parsed.ok && canonicalJson(parsed.value.payload.state) === canonicalJson(dclmEnv.state))
t('parsed canonical_sha256 matches DCLM', parsed.ok && parsed.value.payload.canonical_sha256 === dclmEnv.canonical_sha256)

// --- the carried state is genuinely DCLM-signed ------------------------------
const sigCheck = verifyWorldState(parsed.value.payload, PUBKEY_PATH)
t('inner DCLM signature verifies (Ed25519, testnet key)', sigCheck.ok === true)
const tamperedState = { ...dclmEnv, state: { ...WORLD_STATE, tick: 8 } }
t('tampered state fails signature verification', verifyWorldState(tamperedState, PUBKEY_PATH).ok === false)

// --- idempotency: deliver twice -> second is a no-op -------------------------
const outbox = new Outbox()
const first = outbox.deliver(bundle)
t('first deliver delivers', first.ok === true && first.delivered === true)
const second = outbox.deliver(JSON.stringify(bundle))
t('second deliver is a no-op', second.ok === true && second.delivered === false)
t('no-op returns the original receipt', second.receipt && second.receipt.manifest_hash === first.manifest_hash)
t('outbox holds exactly one bundle', outbox.size() === 1)
t('exactly one receipt minted for two deliveries', outbox.receipts().length === 1)

// --- schema rejection --------------------------------------------------------
t('mainnet schema bundle REJECTED', parseBundle({ ...bundle, schema: 'dualis.relay.v1' }).ok === false)
t('schema not ending in .testnet REJECTED',
  parseBundle({ ...bundle, schema: 'dualis.relay.v1.testnet.evil' }).ok === false)
t('wrong testnet protocol schema REJECTED',
  parseBundle({ ...bundle, schema: 'dualis.relay.v2.testnet' }).ok === false)
t('garbage REJECTED', parseBundle('not json').ok === false)

// --- tampered payload (bad signature/hash) REJECTED ---------------------------
const tampered = JSON.parse(JSON.stringify(bundle))
tampered.payload = { ...tampered.payload, state: { ...WORLD_STATE, tick: 999 } }
const tamperedParse = parseBundle(tampered)
t('tampered payload REJECTED', tamperedParse.ok === false)
t('tamper reason names the manifest hash', /manifest_hash/.test(tamperedParse.reason || ''))

// --- non-testnet identity REJECTED --------------------------------------------
t('non-testnet identity refused at build', (() => {
  try {
    createBundle({ envelope: 'QUERY', payload: { q: 1 }, unityId: 'unity:1e26f0d9e8c46818', gate: gateEnv, reason: 'r' })
    return false
  } catch { return true }
})())
const badId = JSON.parse(JSON.stringify(bundle))
badId.unity_id = 'unity:evil'
t('non-testnet identity REJECTED at parse', parseBundle(badId).ok === false)

// --- envelope whitelist: envelopes, not minds ---------------------------------
t('all six protocol envelopes accepted', ENVELOPE_TYPES.length === 6 &&
  ['TASK', 'EVIDENCE', 'VERDICT', 'QUERY', 'KEY_OFFER', 'ACK'].every(e => ENVELOPE_TYPES.includes(e)))
t('unknown envelope refused at build', (() => {
  try {
    createBundle({ envelope: 'MIND', payload: { m: 1 }, unityId: UNITY_ID, gate: gateEnv, reason: 'r' })
    return false
  } catch { return true }
})())
const mindBundle = {
  ...bundle,
  envelope: 'MIND',
  manifest_hash: bundleHash({ schema: bundle.schema, envelope: 'MIND', payload: bundle.payload, unityId: bundle.unity_id, gate: bundle.gate, reason: bundle.reason }),
}
t('unknown envelope REJECTED at parse (hash valid, type wrong)', parseBundle(mindBundle).ok === false)

// --- gate discipline: not BOUND, or wrong identity, carries nothing ------------
const unboundGate = { ...gateEnv, state: 'UNBOUND' }
t('UNBOUND gate refused at build', (() => {
  try {
    createBundle({ envelope: 'QUERY', payload: { q: 1 }, unityId: UNITY_ID, gate: unboundGate, reason: 'r' })
    return false
  } catch { return true }
})())
const wrongIdGate = { ...gateEnv, identity: 'unity:testnet:deadbeef' }
t('gate identity mismatch REJECTED', checkGateEnvelope(wrongIdGate, UNITY_ID).ok === false)
const wrongIdBundle = {
  ...bundle,
  gate: wrongIdGate,
  manifest_hash: bundleHash({ schema: bundle.schema, envelope: bundle.envelope, payload: bundle.payload, unityId: bundle.unity_id, gate: wrongIdGate, reason: bundle.reason }),
}
t('gate identity mismatch REJECTED at parse', parseBundle(wrongIdBundle).ok === false)

// --- never secrets: KEY_OFFER with a private key is refused ---------------------
t('secret-like payload key found by the guard', findSecretKey({ a: { private_key: 'x' } }) !== null)
t('KEY_OFFER carrying a private key refused at build', (() => {
  try {
    createBundle({
      envelope: 'KEY_OFFER',
      payload: { pubkey_b64: 'AAA', private_key: 'SHOULD-NEVER-RIDE' },
      unityId: UNITY_ID,
      gate: gateEnv,
      reason: 'r',
    })
    return false
  } catch { return true }
})())
const pubOnlyOffer = createBundle({
  envelope: 'KEY_OFFER',
  payload: { pubkey_b64: 'AAA', key_id: 'unity-world-test' },
  unityId: UNITY_ID,
  gate: gateEnv,
  reason: 'public key offer',
})
t('KEY_OFFER with public key only accepted', parseBundle(pubOnlyOffer).ok === true)

// --- receipts ------------------------------------------------------------------
const receipt = toReceipt({ manifestHash: bundle.manifest_hash, outcome: 'DELIVERED', reason: 'ok', receipt: { r: 1 } })
t('receipt round-trips', fromReceipt(receipt).ok === true)
t('DELIVERED without receipt refused (never invented)', (() => {
  try { toReceipt({ manifestHash: 'x', outcome: 'DELIVERED', reason: 'r' }); return false }
  catch { return true }
})())
t('HOLE receipt accepted', fromReceipt(toReceipt({ manifestHash: 'x', outcome: 'HOLE', reason: 'no live kernel' })).ok === true)

// --- export dedupes by manifest_hash ---------------------------------------------
const exported = exportRelay([bundle, bundle, pubOnlyOffer])
t('export dedupes by manifest_hash', exported.bundles.length === 2)
t('export schema is testnet', exported.schema === UNITY_RELAY_SCHEMA)

// --- canonical determinism (mirrors testnet relay) -------------------------------
t('canonicalJson sorts keys', canonicalJson({ b: 1, a: 2 }) === '{"a":2,"b":1}')
t('bundleHash is stable', bundleHash({ schema: 's', envelope: 'QUERY', payload: { a: 1 }, unityId: 'u', gate: { g: 1 }, reason: 'r' }) ===
  bundleHash({ schema: 's', envelope: 'QUERY', payload: { a: 1 }, unityId: 'u', gate: { g: 1 }, reason: 'r' }))
t('sha256Hex of empty string is the known digest', sha256Hex('') === 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail === 0 ? 0 : 1)
