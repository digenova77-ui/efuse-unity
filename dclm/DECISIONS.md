# DCLM Compute Core — build decisions (Trinity lens)

Worker 1 of 5, unified WORLD build. Oct 6, 2026.

Each build decision below was run through the three gates. **DCLM** = logic
(the rule must hold). **Iris** = truth (no fabricated claims). **Twain²** =
pragmatism (the simplest thing that actually works). Outcome noted.

## 1. Import rings, never copy them — DCLM
**Logic:** `compute.py` imports `DecisionWave`/`Parliament`/`Point` from
`~/workspace/core-rings/rings.py` via `sys.path`. One source of truth for
the collapse rule; divergence between two copies would be a logic defect
by construction.
**Iris:** core-rings is the reference behavior; the test verifies our verdict
*against the real Parliament*, not against a reimplementation — no room to
invent a different collapse and call it the same.
**Twain²:** one line of path setup beats vendoring. Outcome: **import**.

## 2. Provenance on every field, enforced at the pipeline exit — DCLM/Iris
**Logic:** a label enum with a validator (`_assert_provenance`) that raises
on any missing/invalid label means the invariant is structural, not a
comment hoping developers behave.
**Iris:** "Real data only. If you can't verify, mark UNKNOWN." The labels
REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN are the honest register —
a reported pulse claim is never upgraded to VERIFIED just because it arrived.
**Twain²:** five labels, one set, checked in one place. Outcome: **enforced**.

## 3. UNKNOWN is never PASS; no forced collapse — DCLM/Iris
**Logic:** David's deadlock law lives inside `rings.py` itself
(Parliament refuses to collapse with no survivors). The pipeline carries it
through: undecided verdicts render `decision: null`, `status: UNDECIDED`,
`provenance: UNKNOWN`. No positive claim is manufactured from absence.
**Iris:** presenting UNKNOWN as a success would be a false statement of
state. The world goes on; the state says so honestly.
**Twain²:** nothing to invent here — propagate the wave to the undecided
bucket and mark it. Outcome: **propagate, never force**.

## 4. Feed rule: LIVE needs reading + hash, else PENDING — Iris/Twain²
**Logic:** a feed without a real reading and a real hash has contributed
nothing to the state; calling it LIVE would be a positive claim with no
evidence.
**Iris:** this is Grok's 3D-world bug class (all 6 feeds PENDING, treated as
live). The rule is written as a gate in code, not documentation, so the bug
cannot recur silently.
**Twain²:** one `if`, two fields checked. Outcome: **gate in code**.

## 5. Sign via node, not a hand-rolled Ed25519 — Twain²/DCLM
**Logic:** Python here has no `cryptography` lib; a vendored pure-python
Ed25519 is new cryptographic surface area to get wrong. Node v24's
`crypto.sign`/`crypto.verify` is a tested implementation. The helper
`ed25519.js` is 20 lines of plumbing, not math.
**Iris:** key material never leaves `keys/` — the helper reads the key file
directly; only canonical state bytes travel over stdin. Testnet keys only.
**Twain²:** the round-trip test passes in ~0.6s for the whole suite.
Outcome: **shell to node**.

## 6. Canonical JSON before signing — DCLM
**Logic:** signature verification requires byte-exact reproduction of the
signed message. `json.dumps(..., sort_keys=True, separators=(",", ":"))`
makes canonicalization deterministic; the envelope also carries
`canonical_sha256` so any verifier can check bytes before checking math.
Outcome: **deterministic canonicalization, digest in the envelope**.

## 7. Strict-vs-default ring binding is a constructor choice, not a flag — DCLM
**Logic:** `compute_world_state` accepts an optional `parliament`. Tests
inject strict-binding rings to exercise the undecided path; production uses
the default three rings. Binding policy lives in the Parliament object,
exactly where `rings.py` puts it — the pipeline doesn't second-guess it.
Outcome: **inject the Parliament, don't configure it**.
