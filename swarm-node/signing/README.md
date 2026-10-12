# signing — the offline signing regime (deliverable 54)

One sentence: **nothing of consequence moves without a signature David's
offline key (or a lane key it blesses) produced.**

This package is the audit's closing instrument for the two CRITICAL
findings: C1 (unsigned code enters lanes) and C2 (unsigned history
rewritable). It is also where S1 (downgrade protection), S4 (oracle
authentication), S5 ("go live" as signed intent), S7 (standing-order
hash chain), and S13 (signed remote health streams) live.

## The one rule

The offline root private key is NEVER generated, stored, or handled
anywhere in this repo, in chat, or on a lane. It exists in exactly one
place: David's secure store. Every signature the root key produces is
made by **his hand on an offline machine** via `ceremony.py` /
`tools/sign_*.py`. Tests use throwaway keypairs only.

## Modules

| module | what it seals |
|---|---|
| `ed25519_pure.py` | pure-Python Ed25519 (stdlib only); cross-checked byte-identical against OpenSSL |
| `backend.py` | prefers the vetted `cryptography` package when importable, else the pure fallback; `backend_name()` reports honestly |
| `keys.py` | fingerprints, armor/dearmor (hex, base64, armored) |
| `envelope.py` | sealed envelopes: `{"alg","key_id","payload","sig"}` over canonical JSON |
| `manifest.py` | signed update manifests (C1) + bundle signatures + signed downgrade authorizations (S1) |
| `lane.py` | lane keypairs born on-lane (0600, idempotent); record signing (C2) |
| `intent.py` | "go live" as a signed, expiring, single-use intent (S5) |
| `allowlist.py` | signed oracle-key allowlists; events opened only from allowlisted keys with the right role (S4) |
| `orders.py` | standing orders hash-chained + countersigned (S7) |
| `ceremony.py` | interactive offline key ceremony — David's hand, step by step |

## Wiring (outside this package)

- `cluster/pull-agent.py` verifies the manifest signature against the
  pinned pubkey (`/etc/dualis/david-pubkey`) **before downloading anything**.
  Unsigned/bad-key manifests are refused and the refusal is attested.
  Downgrades need a signed downgrade authorization.
- `cluster/golive.py` requires a sealed `--intent` for real CUTOVER;
  dry runs need none.
- `cluster/health.py` verifies remote lane streams against pinned lane
  pubkeys (`--lane-keys-dir`): unsigned/mis-signed/unpinned → UNKNOWN,
  fail-closed (S13).
- `node/attest.py` signs every record with the lane key; `verify()` checks
  signatures, so forging a chain needs the lane private key, not file writes.
- `node/node-heartbeat.py` signs each tick with the lane key (S13).
- `x402-rail/rail/pricing.py` accepts oracle events only from allowlisted
  keys with the correct role (S4); signature proves SOURCE, not grade — a
  self-reported REAL marker without calibrated provenance is labeled
  REPORTED (S3).
- `bootstrap.sh` pins the pubkey at `/etc/dualis/david-pubkey` at the
  one-hand bootstrap moment and installs this package to
  `/opt/dualis/signing/`.

## Pre-ceremony behavior (transitional, intentional)

Until the ceremony is run and the pubkey pinned, the system WARNS and
proceeds: unsigned records are marked legacy, the pull-agent proceeds
without manifest verification. This is documented and honest — it does
not brick lanes that predate the regime. The regime activates fully the
moment the pubkey is pinned.

## Tests

`python3 -m unittest signing.tests.test_signing signing.tests.test_integration`
from `~/workspace/swarm-node`. 34 unit + 19 integration tests, all green:
bad signatures refused, forged chains detected, downgrades blocked,
unsigned manifests rejected, planted remote streams → UNKNOWN, expired /
replayed / tampered intents refused, wrong-role oracle events refused.
