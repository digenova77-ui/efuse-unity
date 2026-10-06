# CEREMONY.md — The Unity Binding Ceremony (TESTNET)

## What the ceremony is

Binding a Unity identity to the WORLD is a two-step server-side ceremony:

1. **Request** — `request_bind(identity)` moves the identity
   UNBOUND → BINDING and mints a BINDING receipt. This says: *someone
   claims this identity and has started the ceremony.* Nothing is granted.
2. **Confirm** — `confirm_bind(identity, proof)` moves BINDING → BOUND,
   but **only** after the binding proof verifies. This says: *the device
   in this person's hand proved it is theirs.* Only then does the gate
   emit the GATE envelope authorizing DCLM-computed state to flow to
   that identity via the relay.

The client — the page, the browser, the button — decides nothing at any
point. It can request, and it can present a proof, but the transition
happens in `gate.py`, on the server, in the server's state file.

## The WebAuthn concept

"Your face or your finger opens it, the page never sees either one, the
phone does."

- The ceremony uses a **WebAuthn platform authenticator**: the biometric
  (face, fingerprint) never leaves the user's device. It unlocks the
  authenticator; the authenticator signs the gate's challenge.
- The page sees neither the face nor the finger — only that an assertion
  was produced. The server sees the assertion and verifies it: challenge
  freshness, origin/RP ID, signature over the authenticator data, and
  credential binding to the `unity:testnet:` identity.
- No passwords, no SMS codes, nothing phishable crossing the wire.

## SPEC vs implemented

| Piece | Status |
|---|---|
| State machine UNBOUND → BINDING → BOUND, server-side | **Implemented** (`gate.py`) |
| Structural refusal of non-`unity:testnet:` identities | **Implemented** — every entry point |
| Idempotent re-bind (same receipt, no duplicate) | **Implemented** — deterministic receipt IDs |
| Hash-chained mutation receipts (before/after sha256) | **Implemented** (`state/receipts.jsonl`, `RECEIPTS.md`) |
| GATE envelope emission on BOUND | **Implemented** — consults server state only |
| WebAuthn assertion verification | **SPEC / UNKNOWN** — the slot exists in `confirm_bind()` (`verify_webauthn_assertion`); the default verifier returns UNKNOWN and the gate **refuses** to transition on UNKNOWN. Never faked as working. |
| Real device ceremony (phone, platform authenticator) | **Not wired** — no device, no browser ceremony in this sandbox |

The test suite's happy path injects a clearly-labeled TEST STUB verifier
to exercise the state machine. The stub is a simulation for testing
transitions — it is never presented as real WebAuthn.

## Why Grok's dead-button class is impossible here

Grok's live world broke at the entry gate: the "Look at the Earth"
button's JS click handler died, the gate overlay never dismissed, and
users were stuck on the first screen with no workaround. The failure
class is: **the client was responsible for deciding entry.**

This gate removes the class structurally:

- **No client-side gate logic exists to break.** There is no JS handler
  that must fire, no overlay the browser must dismiss, no client state
  that must flip. The page is a dumb display of `status()` — if the
  page's script dies entirely, the gate still works; the worst case is a
  stale display, never a stuck user, because entry is not a client event.
- **Transitions are computed server-side.** `request_bind` and
  `confirm_bind` run in `gate.py`. A dead button cannot strand anyone
  because no button press is load-bearing — the ceremony is two server
  calls, retryable independently, idempotent by construction.
- **The client cannot forge entry.** There is no token, cookie, or flag
  the client can set to become BOUND. `emit_gate_envelope` consults only
  the server's binding record. Stealing or inventing a receipt buys
  nothing (proven by `test_server_side_truth_unforgeable`).
- **Refusals are structural, not advisory.** A non-testnet identity is
  refused with an exception at every entry point — not a warning the
  client could ignore.

The button can die. The page can fail to load. The gate does not care:
entry was never theirs to grant.

---

## THE REFRAME (2026-10-06, David's direction)

**The gate-dialog is dead.** Grok's entry-gate pattern — a dialog standing
in front of the world, blocking the view until someone binds — was killed
by David. The world opens FREE. No entry gate, no dialog, no button the
browser must dismiss for anyone to see anything. Looking costs nothing and
needs no binding, no identity, no keys.

**Binding moved from entry to intent.** The Unity ID binding no longer
authorizes *getting in* — there is nothing to get into. It authorizes
**paid intent**: search and compute draw keys from the Unity wallet. The
state machine is unchanged (UNBOUND → BINDING → BOUND, server-side,
idempotent, hash-chained); what changed is the guarded resource:

| Before | After |
|---|---|
| `emit_gate_envelope()` authorized world entry / DCLM state flow | authorizes **metered intent** (search/compute) against the wallet |
| binding = permission to be let in | binding = permission to **want** (paid intent) |
| viewing gated behind the ceremony | viewing is free; `world_view_pass()` is the code-level assertion |

**New surface in `gate.py`:**

- `world_view_pass()` — takes no identity, requires no binding, consults
  no state, logs nothing. Its existence, and the deliberate absence of any
  view-gating function in the module, is the structural guarantee that no
  function in `gate.py` can revoke or gate world-view state.
  `WORLD_VIEWING_REQUIRES_BINDING` is `False`, grep-able and importable.
- `authorize_intent(identity, action)` — FREE actions (`view`, `look`,
  `render`, `explore`) authorize with no identity and no binding, touching
  no state. METERED actions (`search`, `compute`) require a BOUND identity
  plus a wallet ledger reporting SUFFICIENT keys; otherwise an honest
  `IntentRefused` carrying `.reason`: `UNBOUND`, `WALLET_LEDGER_PENDING`,
  `KEYS_UNKNOWN`, or `INSUFFICIENT_KEYS`. Read-only: no mutation, no receipt.
- `IntentRefused` — the honest refusal for paid intent. A refusal is about
  *wanting*, never about *seeing*: the gate cannot refuse what it does not
  gate, and it does not gate the world.
- `resolve_wallet_ledger()` — a read-only adapter over the DCLM metering
  worker's own `Wallet` class and `PRICES` in `dclm/meter.py` (landed
  2026-10-06 ~06:56 UTC, after the gate's first build). The metering worker
  owns the ledger and prices; the gate reads the live balance and compares
  it against the meter's price list — prices are never hardcoded in the
  gate. If the module is ever missing or broken, the integration degrades
  to honest `WALLET_LEDGER_PENDING`: the gate cannot fabricate a key
  balance, and UNKNOWN is never PASS.

**Why this is purer.** The old framing made the gate a bouncer in front of
reality: the world had to ask the gate's permission to be *seen*. That is
backwards — a world that needs permission to be looked at is not a world,
it is a lobby. The reframe puts the gate where cost actually lives. Seeing
is free because seeing costs the machine nothing; wanting is metered
because search and compute spend real keys from a real wallet. The gate no
longer stands between the person and the world. It stands between the
person and the wallet — exactly where a gate belongs. **The world doesn't
ask permission to be seen; only wanting costs.**

The structural guarantees from the original build all survive the reframe:
server-side truth (test 5), idempotent re-bind (test 3), UNKNOWN never
PASS (test 6), structural testnet refusal (test 2). New tests 7–9 prove
the reframe: no gate function gates viewing; `authorize_intent` requires
BOUND; unbound intent and empty wallets are refused honestly, against the
real ledger.
