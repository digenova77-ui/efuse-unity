# RECEIPTS.md — unity-world relay mutation log

Every mutation to `~/workspace/unity-world/relay/` is logged here with the
sha256 of the file BEFORE and AFTER the mutation. TESTNET ONLY.

(Same convention as `gate/gate.py`: the log records before/after hashes of
the mutated files, not of itself. The final hash of this log is delivered
in the worker handoff report.)

## Mutation log

| # | date (EDT) | file | before sha256 | after sha256 | change |
|---|------------|------|---------------|--------------|--------|
| 1 | 2026-10-06 | `relay-unity.mjs` | `(did not exist)` | `26b8612dc46c9662695fc7bfefc43c9d0381b8a24acde4601acda64343ffb4ee` | Created: unity-world relay protocol (`dualis.relay.v1.testnet`), 489 lines. Mirrors `~/workspace/testnet/relay/relay-testnet.mjs` (schema, envelope discipline, idempotency by manifest_hash, receipts never invented). Exports: `createBundle`, `createVerdictBundle`, `parseBundle` (strict), `verifyWorldState`, `toReceipt`/`fromReceipt`, `Outbox` (deliver with outbox semantics), `exportRelay`, plus structural guards `checkDclmEnvelope`/`checkGateEnvelope`/`findSecretKey`. |
| 2 | 2026-10-06 | `relay-unity.test.mjs` | `(did not exist)` | `9fbc946271759116a48609afd41c79a7b259f6697066bbf07e615d263de16b5c` | Created: 42 unit tests, 239 lines. Real integration — VERDICT payload signed by `dclm/compute.py sign_state()` (python3, Ed25519 testnet key); GATE envelope emitted by `gate/gate.py UnityGate` (request_bind → confirm_bind with a clearly-labeled TEST STUB verifier → emit_gate_envelope) in a temp state dir. All 42 passing at write time. |
| 3 | 2026-10-06 | `RECEIPTS.md` | `(did not exist)` | `see final line (self-seal)` | Created: this mutation log (mutations 1–2 recorded at write time); self-seal appended during the D4 receipt repair 2026-10-06. |

## Runtime receipt ledger

`Outbox.deliver()` keeps its receipts ledger in memory (`_receipts`,
keyed by manifest_hash; exactly one receipt per bundle — re-delivery is a
no-op that returns the ORIGINAL receipt, never mints a new one). Pass
`receiptLogPath` to the `Outbox` constructor to also append every minted
receipt as JSONL (one line per receipt, with `outbox_size_after`).

## Integration status (honest)

- **dclm/compute.py: REAL.** VERDICT payloads are the exact signed
  envelope `sign_state()` produces
  (`{state, canonical_sha256, signature, algorithm, key_id, provenance}`).
  `verifyWorldState()` proves the carried state is DCLM-signed (Ed25519
  over the canonical bytes, unity-world testnet public key) — exercised
  by the test suite, not faked.
- **gate/gate.py: REAL.** The bundle `gate` field is the exact envelope
  `emit_gate_envelope()` produces
  (`{schema: unity.gate.v1.testnet, type: GATE, identity, state: BOUND,
  receipt_id, authorizes, issued_at}`). The relay refuses any bundle whose
  gate is not BOUND for the bundle's own `unity_id`. UNKNOWN is never PASS.
- **Unity ID binding: kept as-is.** `unity:testnet:` + sha256(test pubkey);
  the relay mints no identities, derives none, alters none.

## Laws held

- Testnet only: parsers REJECT any bundle whose schema does not end in
  `.testnet`; `dualis.relay.v1` (mainnet) is REJECTED by name.
- manifest_hash is the one and only idempotency key, end to end.
- The relay carries envelopes and receipts only — never secrets, never
  private keys (payload key-name guard, enforced at build AND at parse).
- No fake receipts: DELIVERED without a receipt is malformed; re-delivery
  is a no-op.

---

## Self-seal (D4 receipt repair — 2026-10-06)

Row 3's self-hash is sealed here under the seal-line-excluded convention
(same convention as gate/RECEIPTS.md and client/RECEIPTS.md): the recorded
seal equals sha256 of this ledger with the seal line below removed.

`RECEIPTS.md` sha256 after this entry:
a3577901191742a4d05268b05459dcf74e9e20f4494d7b44f07766872998246f  RECEIPTS.md
