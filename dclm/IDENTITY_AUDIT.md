# IDENTITY AUDIT — unity-world, 2026-10-06

**Auditor:** MAX PURITY implementation worker (purify.py).
**Standard:** David's directive — every entity, every flow, every
interaction gets a Unity-bound identity; no anonymous anything, anywhere,
at any level of the stack. Purify on entry, on exit, in flight.

**Method:** every public function in `dclm/`, `gate/`, `relay/` was
enumerated (AST walk). For each: does it require a Unity-bound identity?
For every NO — either FIXED (wired into the medium this pass) or
JUSTIFIED (with the reason). "We'll purify that later" is not an entry.

**Result: 0 unwired trust boundaries.** Every function that moves value,
mutates state, or decides touch/no-touch passes through `purify.py`.
Read-only / free-world / pure-crypto / infrastructure functions are
justified individually below.

Conventions: YES = requires (and now enforces via the medium or
pre-existing structural checks) a `unity:testnet:` identity. NO(J) =
no, justified. NO(F) would be no + fixed — all fixes are already applied
and marked YES.

---

## dclm/purify.py — the medium itself

| Function | Identity-required | Note |
|---|---|---|
| `purify_input` | YES | *Is* the identity enforcer: NO_IDENTITY / NOT_TESTNET_IDENTITY fail-closed. |
| `purify_output` | YES | Enforces identity-bound outputs; `identity_as_presented` only for refusal receipts (identity audited, not trusted). |
| `purify_transition` | YES | Enforces identity continuity across the transition. |

## dclm/meter.py

| Function | Identity-required | Note |
|---|---|---|
| `Wallet.meter_intent` | YES | **Wired this pass**: `purify_input` on entry (anonymous → PurificationRefused, before the module's own checks), `purify_transition` on the LEDGER_DEBIT, `purify_output` on every return (free/refusal/grant). Free-world actions (LOOK/RENDER) pass `free_world` — identity optional, forgery still refused. |
| `Wallet.faucet` | YES | **Wired this pass**: entry + LEDGER_CREDIT transition + signed exit. (Not in the original wiring list — wired anyway: it mints test-keys, so it is an economic path. No path bypasses.) |
| `Wallet.balance` | NO(J) | Read-only. Returns 0 for unknown identities; mutates nothing, decides nothing. A balance read is not a trust boundary. |
| `MeritReader.verified_merit` / `TokenizeMeritReader.verified_merit` | NO(J) | Read-only merit reads; malformed → None (UNKNOWN, never PASS). No mutation, no authorization. |
| `bind_merit_reader` / `unbind_merit_reader` | NO(J) | Infrastructure wiring (which reader object), not an identity flow. Test/admin surface. |
| `emission_eligibility` | YES | Pre-existing structural check: non-testnet identity → honest labeled closed verdict (no exception). Read-only gate; behavior preserved deliberately — the medium would turn its honest verdicts into exceptions, which is not what a gate is for. |
| `sign_receipt` / `verify_receipt` | NO(J) | Pure cryptography. Identity-agnostic by design — the signature binds the receipt bytes, which carry the identity. |

## dclm/token_engine.py (+ tokenize.py shim)

| Function | Identity-required | Note |
|---|---|---|
| `Tokenizer.tokenize` | YES | **Wired this pass**: `purify_input` on entry (identity + labels + presented signatures verified), `purify_output` on the TokenBundle (minted envelopes' signatures verified; genesis path carries the DERIVED binding proof, unsigned by contract). |
| `Tokenizer.merit_transfer` | YES | **Wired this pass**: `purify_input` on entry (both identities), `purify_transition` with `identity_moves` (declared ownership move), signed exit via `_commit`. |
| `Tokenizer._commit` | YES | Internal choke point: `purify_transition` (real balance/count markers from each caller) + `purify_output` on the signed envelope. |
| `Tokenizer.set_peg_ratio` | NO(J) | Trust boundary but NOT a Unity-identity flow: authority is David's word via the testnet stand-in `{"authority": "david"}`, explicitly labeled REPORTED-not-VERIFIED. **Named gap G-1**: no cryptographic David authorization exists in testnet; production setter must require his signature (the module says so itself). Not "fixed" because inventing a signature scheme here would be theater. |
| `Tokenizer.peg_ratio` | NO(J) | Read-only. |
| `Tokenizer.merit_balance` / `standing` / `merit_score` | NO(J) | Read-only aggregations over the slice registry. They take an identity parameter (the query subject) but perform no trust decision and mutate nothing. `standing()` is origin-based by construction. |
| `Tokenizer.honor_records` / `unity_holder` | NO(J) | Read-only. |
| `mint_paths` / `unity_transfer_paths` / `merit_transfer_paths` / `assert_single_mint_path` / `assert_no_unity_rebind` / `assert_single_merit_transfer_path` | NO(J) | AST introspection — proofs about the code's own structure, not runtime flows. No identity exists at this level. |
| Module-level shims (`tokenize`, `merit_transfer`, `standing`, `merit_balance`, `set_peg_ratio`, `peg_ratio`) | inherit | Delegate to the default engine; covered above. |
| `tokenize.py` (shim) | n/a | PEP-562 lazy shim, no logic. |

**Named gap G-2:** `Tokenizer._bind_genesis` mutates the Unity registry
*directly* (write-once, idempotent) instead of through `dclm_commit` —
pre-existing architecture (the fuse trigger owns the mint; no COMMIT_KIND
covers the fuse-owned genesis bind). `purify_transition` is therefore not
applied to the bind itself; the bind IS covered by `purify_input`/`purify_output`
on the `tokenize` path (identity-bound in, DERIVED binding proof out).
Routing the bind through `dclm_commit` would require inventing a commit
kind for someone else's mint — refused as dishonest.

## dclm/share.py

| Function | Identity-required | Note |
|---|---|---|
| `issue_grant` | YES | **Wired this pass**: entry + GRANT_ISSUE transition (registry-growth markers) + signed exit. |
| `revoke_grant` | YES | **Wired this pass**: entry + GRANT_REVOKE transition + signed exit. (Not in the original wiring list — wired anyway: revocation is a trust boundary.) |
| `check_access` | YES | **Wired this pass**: `purify_input` on entry (anonymous → PurificationRefused; previously returned a deny verdict), `purify_output` on the verdict (now carries `provenance="DERIVED"` — **fixed**: verdicts were unlabeled). Read-only, so no transition. Output uses `require_identity=False`: the verdict names the grant, not the identity; the identity was bound at input. |
| `access` | YES | **Wired this pass**: entry + three transitions (LEDGER_DEBIT, LEDGER_CREDIT, SHARED_ACCESS) + signed exit. |
| `verify_kin` | YES | Takes granter+grantee; enforced at the `issue_grant` boundary (FAMILY tier). Standalone it delegates to the registered L2 authority. |
| `register_kin_authority` / `clear_kin_authority` | NO(J) | L2-umpire wiring slots, not identity flows. |
| `ShareStore.*` / `_ShareWalletAdapter.*` | NO(J) | DCLM-internal commit-protocol implementations. Unreachable except through `dclm_commit` behind a DCLM-issued GRANT verdict. |

## dclm/tap.py

| Function | Identity-required | Note |
|---|---|---|
| `Tapper.request_tap` | YES | **Wired this pass**: `purify_input` on entry (purpose travels as a REPORTED claim), `purify_transition` on TAP_OUTFLOW (season+member outflow markers), `purify_output` on the grant; refusals purified in `_signed_refusal` (`identity_as_presented`). |
| `TapSeason.evaluate` / `maturity_score` / `verified_surplus` | NO(J) | Pure computations over labeled measures. No identity flow — identity enters at `request_tap`. |

## dclm/winter.py

| Function | Identity-required | Note |
|---|---|---|
| `winter_store` | YES | **Wired this pass**: entry + WINTER_STORE transition (circulation/reserve markers) + signed exit; refusals purified (`identity_as_presented`). |
| `winter_release` | YES | **Wired this pass**: entry + WINTER_RELEASE transition + signed exit. |
| `winter_aware_faucet` | YES | Delegates to `Wallet.faucet` — covered by faucet's `purify_input`. Identity flows through, unmodified. |
| `WinterReserve.holding` | NO(J) | Read-only. |
| `peg_tilt` / `activity_tilt` / `crisis_tilt` / `evaluate_trigger` / `emission_multiplier` / `WinterSignal.readable` / `snapshot` | NO(J) | Pure signal mathematics over labeled inputs. No identity, no state, no trust decision. |

## dclm/onboard.py

| Function | Identity-required | Note |
|---|---|---|
| `OnboardPipeline.onboard` | YES | **Wired this pass**: entry + ONBOARD transition (onboarder-count markers) + exit via `_commit`; idempotent replay re-purified. |
| `OnboardPipeline.record_residual` | YES | **Wired this pass**: entry (figure travels as REPORTED claim) + RESIDUAL_INTAKE transition + exit; replay re-purified. |
| `OnboardPipeline.execute_split` | YES | **Wired this pass**: entry + SPLIT_EXECUTE transition + exit; replay re-purified. |
| `OnboardPipeline.route_19` | YES | **Wired this pass**: entry + NINETEEN_ROUTE transition + exit via `_commit`. |
| `OnboardPipeline.accrue_recovery_merit` | YES | **Wired this pass**: entry + consumption-commit transition + all four summary exits labeled (`provenance="DERIVED"` — **fixed**: three summaries were unlabeled) and purified. |
| `OnboardPipeline._commit` | YES | Internal choke point: `purify_transition` + signed `purify_output`. |
| `OnboardPipeline._refuse` | YES | Refusal exits purified (`identity_as_presented`, signed). |
| `OnboardPipeline.escrow_balance` / `flywheel_state` / `merit_path_status` | NO(J) | Read-only aggregates. Labeled outputs, no mutation, no trust decision. |
| `OnboardPipeline.merit_band_for` | NO(J) | Pure static mapping (work class → band). |
| Module-level shims (`onboard`, `record_residual`, `execute_split`, `route_19`, `accrue_recovery_merit`, `flywheel_state`, `escrow_balance`) | inherit | Delegate to the default pipeline; covered above. |

## dclm/data.py

| Function | Identity-required | Note |
|---|---|---|
| `ingest_reading` | YES | **Wired + fixed this pass**: feed sources are now Unity-bound. New `register_feed_source(feed, source_identity)` (ValueError on non-testnet); `ingest_reading(..., source_identity=...)` resolves explicit-or-bound source, refuses unbound (`NO_IDENTITY`) and mismatched (`SOURCE_MISMATCH`) sources as PurificationRefused. LIVE entries now carry `source_identity` — the entry records WHO reported it. `purify_input` on entry, `purify_output` on the entry (LIVE requires identity-bound). |
| `register_feed_source` | YES | Validates Unity-bound; the binding ceremony for feeds. |
| `feed_source` / `clear_feed_sources` | NO(J) | Read / test-admin of the binding registry. |
| `load_registry` / `registry_summary` / `pricing_index` / `rte_telemetry` / `feed_registry` / `factory_verdicts` / `serve_world_data` / `serve_world_state` | NO(J) | Read-only serving of vendored/labeled data. Every served fact carries its provenance label (the modules' own law). The world data is the free world: labeled, signed where it matters, identity-free by design (cf. `world_view_pass`). |

## dclm/seed.py (one-seed issuer — sibling worker's module, same medium)

| Function | Identity-required | Note |
|---|---|---|
| `Seeder.issue_seed` | YES | Wired against this medium (sibling worker): `purify_input` on entry, `purify_transition` (False→True), signed `purify_output`. **Fixed this pass**: the medium now genuinely runs first (the code ran the structural check first despite its own "medium first" comment) — anonymous → PurificationRefused uniformly. |
| `Seeder.has_seed` / `seed_record` / `seeds_issued` / `refusal_log` | NO(J) | Read-only. |
| `seed_paths` / `seed_transfer_paths` / `assert_no_seed_market` | NO(J) | AST introspection, no runtime flow. |
| Module shims | inherit | |

## dclm/chunks.py

| Function | Identity-required | Note |
|---|---|---|
| `ChunkServer.handle` (+ `_gen`, `_chunk_index`, `_stream`, `_shard_page`) | NO(J) | Read-only content distribution over GET/HEAD. Serves signed, epoch-pinned chunks — the free world: labeled content, no trust decision, no identity needed. (Same law as `world_view_pass`.) |
| `build_dataset_chunks` / `build_manifest` / `build_head` / `build_shard_manifest` / `read_epoch` / `read_schema_version` / `bump_epoch` / `bump_schema_version` / `build_all` / `ChunkServer.regenerate` / `export_tree` / `relay_wrap` | NO(J) | Build/publish pipeline for signed content. No per-request identity — the chunks are content-addressed and signed; trust is in the signature and epoch, not the fetcher. |

## dclm/compute.py

| Function | Identity-required | Note |
|---|---|---|
| `compute_world_state` / `sign_state` / `WorldState.to_dict` | NO(J) | The world-state pipeline: pure computation over waves/feeds/registry, then signed. The world state is identity-agnostic BY DESIGN — the world is the world; identity binds at intent (meter) and binding (gate), not at world-rendering. Every field carries provenance; the envelope is signed. |
| `verify_envelope` | NO(J) | Pure crypto verification. |

## dclm/rights.py / dclm/writes.py

| Function | Identity-required | Note |
|---|---|---|
| `rights.check_rights` | YES | The authority: takes identity, action, context. (Pre-existing.) |
| `writes.dclm_commit` | YES | Requires a DCLM-issued GRANT `RightsVerdict` (which carries the audited identity) + whitelisted kind. (Pre-existing.) |
| `writes.sign_commit` / `verify_commit` / `CommitStore.*` / `MemoryCommitStore.*` | NO(J) | Crypto + store protocol. Identity travels inside the receipt/verdict, not as a parameter. |

## gate/gate.py (audited; not rewritten — outside this worker's mandate)

| Function | Identity-required | Note |
|---|---|---|
| `verify_webauthn_assertion(identity, proof)` | YES | Pre-existing: the biometric ceremony binds the identity. |
| `UnityGate.request_bind` / `confirm_bind` | YES | Pre-existing: `_require_testnet` + WebAuthn proof; the binding ceremony. |
| `UnityGate.status` | YES | Takes identity; reads server-side binding truth. Read-only. |
| `UnityGate.emit_gate_envelope` | YES | Pre-existing: BOUND-only. |
| `UnityGate.authorize_intent` | YES | Pre-existing: BOUND identity + wallet for metered actions; FREE actions short-circuit with no identity BY DESIGN (David's reframe — the world opens free; only wanting costs). |
| `UnityGate.derive_identity` | YES | Identity-producing: derives `unity:testnet:` from the device pubkey. |
| `world_view_pass` | NO(J) | **Explicitly identity-free by David's law** (2026-10-06 reframe): "THE REFRAME: David killed the gate-dialog. The world does not ask permission to be seen." Its no-identity contract is the structural guarantee, not a gap. |
| `resolve_wallet_ledger` | NO(J) | Infrastructure: locates the meter's wallet adapter. No identity flow. |

## relay/relay-unity.mjs (audited; not rewritten — outside this worker's mandate)

| Function | Identity-required | Note |
|---|---|---|
| `createBundle` / `createVerdictBundle` | YES | Pre-existing: `unityId` (`unity:testnet:...`) + BOUND GATE envelope required; fail-closed. |
| `checkGateEnvelope` / `checkDclmEnvelope` | YES | Pre-existing: validates the GATE envelope's identity matches the bundle's `unity_id`. |
| `Outbox.deliver` | YES | Pre-existing: parses the bundle (which carries `unity_id`) and receipts per-identity. |
| `bundleHash` | YES | Takes `unityId`; the hash commits to the identity. |
| `canonicalJson` / `sha256Hex` / `findSecretKey` | NO(J) | Pure utils. `findSecretKey` is a secret-leak guard (fail-closed on key material in payloads) — identity-agnostic by design. |
| `parseBundle` / `fromReceipt` | NO(J) | Pure parsers; validation happens in the check functions. |
| `verifyWorldState` | NO(J) | Pure crypto verification against the test key. |
| `toReceipt` | NO(J) | Receipt formatter; identity travels inside the receipt body. |
| `exportRelay` | NO(J) | Portable export of already-bound bundles. |
| `Outbox` constructor / `size` / `has` / `receipts` | NO(J) | Bookkeeping. |

---

## Named gaps (standard not reached — stated plainly)

- **G-1** (`token_engine.set_peg_ratio`): the peg authority is David's word
  via testnet stand-in, labeled REPORTED-not-VERIFIED. No cryptographic
  David authorization exists in testnet. Production must require his
  signature. Not fixable honestly in testnet.
- **G-2** (`token_engine._bind_genesis`): the Unity genesis bind mutates
  the registry directly (write-once, idempotent), outside `dclm_commit` —
  no whitelisted kind covers the fuse-owned mint. Covered by purify
  in/out on the `tokenize` path, but `purify_transition` is not applied
  to the bind itself.
- **G-3** (relay transport): the relay's `Outbox.deliver` accepts bundles
  over whatever transport carries them; transport-level authentication
  (who may submit a bundle) is outside `relay-unity.mjs`. Bundle-level
  identity (unity_id + BOUND gate envelope + signature) is enforced;
  transport-level is not in scope.

## Fixes applied this pass (beyond the wiring list)

1. `share.AccessVerdict` now carries `provenance="DERIVED"` — verdicts
   were unlabeled.
2. `onboard.accrue_recovery_merit` summaries now carry
   `provenance="DERIVED"` — three of four summaries were unlabeled.
3. `share` commit payloads (`GRANT_ISSUE`, `GRANT_REVOKE`) now carry
   `provenance="DERIVED"` — transition receipts were unlabeled.
4. `data.ingest_reading`: feed sources are now Unity-bound
   (`register_feed_source` + `source_identity`); LIVE entries record
   their source.
5. `seed.issue_seed`: the medium now genuinely runs first (was second
   despite its own comment).
6. `meter.Wallet.faucet`, `share.revoke_grant`, `share.check_access`:
   wired although not in the original list — economic/trust paths don't
   get to bypass the medium.

## Contract changes (pre-existing tests updated — the medium is stricter)

Anonymous/forged input now raises `PurificationRefused` at the medium
*before* the modules' own refusal paths run. Tests asserting the old
signed-refusal-for-anonymous behavior were updated to the new contract:
`test_meter.py::test_non_testnet_identity_refused`,
`test_tap.py::test_non_testnet_identity_refused`,
`test_share.py::test_issue_rejects_non_testnet_identities` +
`test_check_access_validates_inputs`,
`test_onboard.py::test_non_testnet_identity_refused_all_stages`,
`test_tokenize.py::test_missing_unity_id_refused` +
`test_malformed_receipt_refused`,
`test_winter.py::test_non_testnet_identity_structurally_refused`,
`test_data.py` feed-ingest tests (now register sources).
The modules' own identity checks remain as defense in depth.
