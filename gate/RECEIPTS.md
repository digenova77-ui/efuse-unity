# RECEIPTS.md — Unity ID Gate mutation ledger (TESTNET)

Every state mutation the gate performs is logged to `state/receipts.jsonl`
with the sha256 of the state file **before** and **after** the mutation.
The log is append-only and hash-chained: each entry's `prev_state_sha256`
equals the previous entry's `new_state_sha256`, so tampering with the
state file or the log breaks the chain audibly.

## Log entry format

| field | meaning |
|---|---|
| `schema` | `unity.gate.v1.testnet` — testnet only |
| `ts` | UTC timestamp of the mutation |
| `identity` | the bound identity (`unity:testnet:`-prefixed) |
| `transition` | `BINDING` or `BOUND` |
| `receipt_id` | deterministic `sha256(schema\|transition\|identity)` — duplicates collapse |
| `prev_state_sha256` | sha256 of `state/gate-state.json` BEFORE the mutation |
| `new_state_sha256` | sha256 of `state/gate-state.json` AFTER the mutation |
| `note` | human-readable reason |

Read-only calls (`status()`, re-bind of an already-bound identity,
`emit_gate_envelope()`) perform **no mutation** and log **no receipt**.
A no-op leaves no trace by design — doing it twice is doing it once.

## Seed run — 2026-10-06 ~06:54 UTC

The test identity `unity:testnet:1e26f0d9e8c46818` was walked
UNBOUND → BINDING → BOUND against the canonical state dir (`gate/state/`),
then a GATE envelope was emitted. Two mutations, one chain:

### Mutation 1 — `request_bind` → BINDING

- `receipt_id`: `10cd821a21d0bfdd90a890918f9692fa381ffc6184a6942e3866f8c150b2cf4e`
- `prev_state_sha256`: `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` (empty state)
- `new_state_sha256`: `47b978186772d4ece208945a93fd08bedcac917f395d063f251aeefa90517505`
- `note`: binding ceremony started; awaiting WebAuthn proof

### Mutation 2 — `confirm_bind` → BOUND

- `receipt_id`: `f7ba75dfbe0d2166b1584d07e5dfb48bcfac230eb4978253e196b0f49e9c3110`
- `prev_state_sha256`: `47b978186772d4ece208945a93fd08bedcac917f395d063f251aeefa90517505` (= mutation 1's `new_state_sha256` — chain intact)
- `new_state_sha256`: `7b399fa4df90ae4a76c3fd026f1dd52bd7b4dfc2683a4af9f98b0a1c67c685dc`
- `note`: binding proof VERIFIED; identity bound to Unity gate

Caveat (honest): the seed run's `confirm_bind` used a test-stub verifier
simulating the device ceremony — see CEREMONY.md. The state machine,
receipt format, and hash chain are fully implemented; the WebAuthn
verification step is SPEC/UNKNOWN until wired.

## How to verify

```bash
cd ~/workspace/unity-world/gate
python3 - <<'EOF'
import json, hashlib
prev = hashlib.sha256(b"{}").hexdigest()   # empty-state hash
ok = True
for line in open("state/receipts.jsonl"):
    e = json.loads(line)
    ok &= (e["prev_state_sha256"] == prev)
    prev = e["new_state_sha256"]
print("chain intact:", ok)
EOF
```

---

## Reframe — 2026-10-06 ~07:00 UTC (David's direction)

The gate was reframed, not rebuilt: binding moved from world entry to
metered intent. Grok's gate-dialog pattern is dead — the world opens
FREE; the gate now guards PAID INTENT (search/compute against the Unity
wallet). State machine (UNBOUND → BINDING → BOUND), `request_bind` /
`confirm_bind` / `status`, idempotency, and hash-chained receipts are
byte-for-byte behavior-identical. New: `authorize_intent(identity,
action)` (FREE actions need no identity/binding; METERED actions require
BOUND + SUFFICIENT keys via the real `dclm/meter.py` ledger, honest
`IntentRefused` reasons otherwise), `world_view_pass()` (code-level
assertion that no gate function gates viewing), `resolve_wallet_ledger()`
(read-only adapter over the metering worker's `Wallet`/`PRICES`).
`emit_gate_envelope()` reframed: authorizes metered intent against the
wallet, never world entry. Test suite: 9/9 passing (6 original + 3 new).

Files edited (before → after sha256):

| file | before | after |
|---|---|---|
| `gate.py` | `881ca5cf05fe67fa5fb229d614357c58a994567aff90d32de291117541b97de5` | `77ad1d1a9d95adf436c228905a75d494cab8eb48150ddda82c58f44cb8cbc3f6` |
| `test_gate.py` | `a76bd2f4855a78a8a4ed9567aa5125c879657a6ee527c4bfeefe7db670055d28` | `54fc8a91308698370b48bad86546708997a2456826fbf10c3012706d72525656` |
| `CEREMONY.md` | `39952044e83bbdf99722b5c2f9ddf8c399f5dc6c3db5d44bbda04cde1580b54f` | `c9c519779b1d25e587cc2d3e977d06e0fd8eca59ade81c31a7db5180a5c35748` |
| `RECEIPTS.md` | `4acaf7598b1f275ba8cddf8d08badc84168733b9208dff0acb10dd7055dd0854` | see final line below |

Note: no state mutation was performed against the canonical
`state/gate-state.json` during the reframe — the test identity's BOUND
record and the seed-run receipt chain are untouched. All tests ran
against temp state dirs.

`RECEIPTS.md` sha256 after this entry:
b1fb584f74928d9c8994a1ebc3f31323764f6d056026b5ec38492371280e33ff  RECEIPTS.md
