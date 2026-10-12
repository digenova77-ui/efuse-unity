"""DualisCapax offline signing regime.

Closes C1 (unsigned code enters lanes) and C2 (unsigned history rewritable),
plus S1/S4/S5/S7/S13 where they touch signing.

Layout:
  ed25519_pure.py  pure-Python Ed25519 (stdlib only; correctness proven by
                   cross-verification against pycryptodome in tests)
  backend.py       backend selection (vetted `cryptography` if present,
                   else ed25519_pure); deterministic RFC 8032 throughout
  keys.py          fingerprints, armor, secret-file writing
  envelope.py      signed envelopes over canonical JSON (the unit of proof)
  manifest.py      manifest + bundle signatures, downgrade protection (S1)
  intent.py        go-live as signed intent (S5), replay-protected
  lane.py          lane keypairs born on-lane; signed attestations (C2)
  allowlist.py     signed allowlists for oracle event sources (S4)
  orders.py        standing orders as a hash-chained, countersigned ledger (S7)
  ceremony.py      THE KEY CEREMONY — David's hand, offline machine, once
  tools/           offline signing helpers (sign_manifest.py)

The offline root key is NEVER generated here, never in git, never on a
lane, never in chat. Tests use throwaway keypairs only.
"""
