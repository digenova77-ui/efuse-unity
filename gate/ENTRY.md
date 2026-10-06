# ENTRY.md — The Entry Gate: the doorway, not the world (TESTNET)

David's four laws of the website (2026-10-06 ~4:36 AM EDT):
1. the 2D card explains the Unity ID
2. the bind ceremony
3. the eFuse ignition
4. entry into the 3D world

**One card at the doorway — no more 2D after that.**

## The shape of the doorway

```
the card (2D, entry route)          the world (3D)
┌─────────────────────────┐
│  THE DOORWAY            │
│  One identity.          │   the entrant reads the card,
│  One seed. One world.   │   accepts the covenant, and DCLM
│                         │   performs the ceremony:
│  [what it is]           │
│  [what it does]         │     derive identity (DCLM)
│  [the covenant]         │  →  request_bind  (UNBOUND→BINDING)
│                         │  →  confirm_bind  (BINDING→BOUND)
│  [accept the covenant   │  →  issue_seed    (the one free seed)
│   and bind]             │  →  gate envelope (metered intent)
│  [look first — free]    │  →  IGNITION      (the member's spark)
└─────────────────────────┘
        │ card dissolves, light refracts through diamond geometry
        ▼
   the 3D world — no cards. The helper swarm. Iris waiting.
```

The card never withholds the world: looking costs nothing and needs no
binding (the reframe holds — David killed the gate-dialog). The card is
the doorway into *membership*, not a tollbooth in front of the view.

## The card — exact copy

The card is the ONLY 2D card in the entire experience. It lives at the
gate, never in the world. The copy below is the covenant record — the
same words travel in the signed entry/ignition envelopes
(`COVENANT_LINES` in `entry.py`).

> **THE DOORWAY — entry ceremony · testnet**
>
> **One identity. One seed. One world.**
>
> **What it is**
> Your Unity ID is your identity in the world — one per human. It is an
> obfuscated number, not a name: no name, no location, no personal
> detail, ever. It is bound to you and cannot be sold, gifted, or moved
> — not even by David. It IS you, extended.
>
> **What it does**
> It binds you to the tree. Your free seed issues to it — one seed, and
> it costs nothing. Your merit accrues to it, and your standing is yours
> alone: transferred merit moves value, never standing.
>
> **The covenant**
> — ONBOARD — take your free seed. One per Unity ID. It costs nothing.
> — STAY IN LINE — follow the law, stay pure.
> — PREACH THE GOOD WORD — bring others into the world.
>
> Looking costs nothing — the world opens free, no binding needed.
> Binding is for those who want to build: search and compute draw keys
> from your Unity wallet.
>
> [ Accept the covenant and bind ]    [ Look first — the world opens free ]

## The bind — DCLM performs it

`POST /api/world/bind`

Request:
```json
{
  "covenant_accepted": true,
  "ceremony": {
    "kind": "webauthn",
    "credential_id": "<base64url rawId>",
    "assertion": { "...opaque..." }
  }
}
```
or the testnet stub (sandbox only, explicitly labeled):
```json
{
  "covenant_accepted": true,
  "ceremony": {
    "kind": "testnet-stub",
    "testnet_ceremony": true,
    "stub_seed": "<hex>"
  }
}
```

The client supplies ceremony MATERIAL, never an identity. DCLM derives
the Unity ID server-side (`derive_entry_identity`):
`"unity:testnet:" + sha256(material)[:16]` — obfuscated by construction.

Success response (`{ok: true, entry: <envelope>}`): the serving layer wraps
DCLM's entry envelope — identity, obfuscated display, covenant record,
bind receipt (BOUND), seed receipt (price 0, cost 0), GATE envelope,
ignition receipt (signed), and the receipt list. Refusal
(`{ok: false, refused: {reason, detail, at_step}}`):
COVENANT_NOT_ACCEPTED | NO_CREDENTIAL_MATERIAL | PROOF_UNKNOWN |
BIND_REFUSED | SEED_REFUSED | ENVELOPE_FAILED | IGNITION_FAILED.

Entry is idempotent per identity: a BOUND, already-ignited identity gets
its existing record back — no new receipts, no duplicate seed, no second
spark.

## The eFuse ignition — the launch moment

Binding triggers the ignition: the energy surge into the world. Every new
member's entry echoes the genesis fuse (`economics/fuse.py`) — the
network launch in miniature. The ignition is a SIGNED event on top of
BOUND (schema `unity.gate.ignition.v1.testnet`), receipted into
`gate/state/ignitions.jsonl`, referencing the bind receipt, the seed,
and the gate envelope. It is not a state transition — the gate's
UNBOUND → BINDING → BOUND machine is untouched.

On the client the ignition is a MOMENT, not a dialog: the card dissolves,
light refracts through diamond geometry (teal → purple → gold), and the
member is IN. Reduced-motion entrants skip the theatre and go straight
in — the spark is the signed record, not the animation.

## Into the world

After ignition: no cards. Just the 3D world, the helper swarm, Iris
waiting. The gate card is gone — it was the doorway, not the destination.

## Honest boundaries (read before claiming completeness)

- **WebAuthn is SPEC/unwired.** The default verifier returns UNKNOWN and
  entry refuses at the proof step (`PROOF_UNKNOWN`). The testnet stub is
  explicitly labeled and never presented as a real device ceremony.
- **The client never generates identities** — it supplies ceremony
  material; the ID is DCLM-derived. In the testnet sandbox the material
  is synthetic; the derivation rule and bind-then-validate are still
  server-side.
- **The seeder's registry is in-memory per process** (`dclm/seed.py`'s
  design). `entry.py` caches one Seeder per gate state dir so the
  one-seed rule holds across calls in-process. Cross-process seed
  persistence is seed.py's lane — flagged, not silently fixed here.
- **The wallet indicator's bind button is unchanged**: it remains the
  world's ongoing affordance for binding before metered intent. The gate
  card is the entry ceremony; the indicator is the standing affordance.
- **No HTTP server ships in this tree.** The client posts to
  `/api/world/bind` per the existing convention; the serving layer is
  deployment infrastructure. The DCLM flow is fully exercised by
  `test_entry.py` (9/9 green, 2026-10-06).
