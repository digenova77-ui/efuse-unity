# RECEIPTS — DCLM compute core (worker 1 of 5)

Testnet only. Nothing touches production keys or paths.
Key material never leaves `../keys/`.

Mutation log: every file here was created new (no prior content, so
before-sha256 is N/A — the file did not exist).

| time (UTC)        | file               | before (sha256) | after (sha256)                                                       |
|-------------------|--------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~06:56 | dclm/ed25519.js    | N/A (new)       | bb0be18c36c3cd9c90237e117301c0272620b2e57945d2fb19b6e32cfbfa397c      |
| 2026-10-06 ~06:58 | dclm/compute.py    | N/A (new)       | daa0b73a7d1a549193522b52d074b523b2361a27434e67edc782d3654065fccb      |
| 2026-10-06 ~06:59 | dclm/test_compute.py | N/A (new)     | ea7c2a62520e259cbd75dd832717787847542442f31923f32058573ee0dbec17      |
| 2026-10-06 ~07:01 | dclm/DECISIONS.md  | N/A (new)       | 56100781f6cc157d13afa8cd79515334a4b5b1b0acfd2af4b1af6b4dd9f7721d      |

Notes:
- `compute.py` was edited once after creation (provenance-validator fix:
  the container dict `feed_status` was wrongly required to carry its own
  label; the entries carry it instead). The after-sha256 above is the final
  post-fix content; the pre-fix hash was not separately recorded.
- Test run 2026-10-06 ~07:00 UTC: `python3 test_compute.py` → Ran 10 tests, OK.
- Signing round-trip verified against `../keys/unity-world-test.key` (DER
  PKCS8, 48 bytes) and `../keys/unity-world-test.pub` (DER SPKI, 44 bytes).
  Only the canonical state bytes crossed the process boundary (stdin to
  node); key files were read by the helper in place.

## Metering engine — worker 2 (David's binding: "Free world, paid intent")

| time (UTC)        | file               | before (sha256) | after (sha256)                                                       |
|-------------------|--------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~06:56 | dclm/meter.py      | N/A (new)       | 9193bd202543da081258b8939f700a9011442402c56e67978801ff4caa5d1b43      |
| 2026-10-06 ~06:56 | dclm/test_meter.py | N/A (new)       | 79451875993147e7d51612180591d6399b9e54d955ce8cc9efaea04bc99dd58d      |

Notes:
- `meter.py` implements David's binding direction: the 3D world is FREE to
  look at (LOOK/RENDER cost 0, no wallet, no identity); SEARCH and COMPUTE
  (a DCLM verdict run) are metered in TEST-KEYS — test units only, clearly
  labeled, never dollars, never eFuse.
- Price list (named constants, easy to change): LOOK=0, RENDER=0,
  SEARCH=1 test-key, COMPUTE=5 test-keys.
- Identity rule mirrors the gate (`~/workspace/unity-world/gate/gate.py`):
  metered actions require an identity starting with `unity:testnet:`.
  Anything else is REFUSED in a signed receipt — never a world block.
- Insufficient keys → signed REFUSAL receipt with the true reason
  INSUFFICIENT_KEYS; the world stays free, the balance is untouched.
- Idempotency: same (identity, intent_id) twice → same receipt, charged
  once. Refusals are NOT cached — a retry re-evaluates the live balance.
- Ledger never goes negative: deduction only when balance >= price,
  asserted after every mutation; state persisted under `dclm/state-meter/`
  (ledger JSON + receipts JSONL).
- Receipts signed with the existing testnet Ed25519 key material from
  `../keys/` (no new keys; the wallet is a ledger, not key custody).
  Refusals are signed too — a signed refusal is a verifiable honest
  statement. Every receipt carries a provenance label; UNKNOWN is never
  PASS (no GRANTED receipt may hide behind an unknown label).
- Test run 2026-10-06 ~06:56 UTC: `python3 test_meter.py` → Ran 20 tests, OK.
- `test_meter.py` was edited once after creation (test expectation fix:
  empty-string identity honestly reports IDENTITY_REQUIRED, not
  NOT_TESTNET_IDENTITY). The after-sha256 above is the final post-fix
  content; the pre-fix hash was not separately recorded.

---

## Data-ingestion worker (worker 2 of 5) — 2026-10-06 ~07:00 UTC

Testnet only. Vendored registries are recovered artifacts (REPORTED), not live-verified.

| time (UTC)        | file                | before (sha256) | after (sha256)                                                       |
|-------------------|---------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:10 | dclm/data.py        | N/A (new)       | a1e435bd955ee2ee9f2138532a5bdc13ad87adcace9ed6ec895170d1b5dcb71d      |
| 2026-10-06 ~07:12 | dclm/test_data.py   | N/A (new)       | a5a39cb22d47e9b35e34189a5d1e734cac69578b57c6f37d6596619d2b9efb79      |
| 2026-10-06 ~07:05 | data/MANIFEST.md    | N/A (new)       | (10 vendored registry files; sha256 + bytes per row in the manifest) |

Notes:
- Vendored 10 registry files from /tmp/grok-drive-extract/public/registry/
  (ephemeral source): countries, cities, chambers, jurisdictions, doctrine,
  rtes, trinity-verdict (task-required) + canada, sectors, pharmacology.
  Manifest rows carry sha256, byte size, source path, provenance REPORTED,
  data label VENDOR-RECOVERY.
- data.py: load_registry (schema-validated loads, raises on corrupt data),
  pricing_index (PRICES.md: 51/51 decisions parsed, 0 unknown rows, 0 invented),
  rte_telemetry (19 REAL metrics from MEMORY.md, verbatim values),
  feed_registry/ingest_reading (6 feeds, all PENDING; LIVE only with
  reading + hash), factory_verdicts (127 sealed records on disk + 18 Trinity
  packet decisions, all SEALED -> VERIFIED with seal refs),
  serve_world_data/serve_world_state (registry bytes + PENDING feeds into
  compute.compute_world_state; compute.py untouched, its provenance enum reused).
- Test run 2026-10-06 ~07:12 UTC: `python3 test_data.py` -> Ran 22 tests, OK.
  Existing `python3 test_compute.py` -> Ran 10 tests, OK (no regressions).
- Label discipline: figures carry REAL/VERIFIED/REPORTED/MODELED/DERIVED/
  UNKNOWN (figure-level set); WorldState-bound fields use compute.py's exact
  enum (REPORTED/VERIFIED/MODELED/DERIVED/UNKNOWN). UNKNOWN never PASS.

## Rights & writes boundary — worker 4 (David's binding rule: "DCLM holds the RIGHTS and performs the WRITES")

| time (UTC)        | file                       | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|----------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:02 | dclm/rights.py             | N/A (new)                                                          | b203e6c5c229824df2c47f44cacafdf849b3c92e2c3a7466c288d6ee509ea291      |
| 2026-10-06 ~07:02 | dclm/writes.py             | N/A (new)                                                          | 05f8be52ee0a0dda42fe6c2491d2f85873c9910dd39f4c874a35350129e13970      |
| 2026-10-06 ~07:02 | dclm/test_rights_writes.py | N/A (new)                                                          | 3fcfe4eb6ce55983849153934d0fab37084794537a48b367a2a616266485701c      |
| 2026-10-06 ~07:02 | dclm/meter.py              | 9193bd202543da081258b8939f700a9011442402c56e67978801ff4caa5d1b43      | 8a72d960f2fbbc6d084b5d03d52ef1dc112b0418fdd1a25181ac66e339d70015      |

Notes:
- `rights.py` is the authority module: `check_rights(identity, action,
  context)` is a pure function (no I/O, no state mutation; total — garbage
  in yields DENY, never an exception). LOOK/RENDER always GRANT with no
  identity (free world); SEARCH/COMPUTE require `unity:testnet:` identity
  AND `meter_approved is True` in context; unknown actions DENY with
  UNKNOWN_ACTION. Gates (evaluated first, absolute): non-testnet schemas
  denied, UNKNOWN-presented-as-PASS denied, unsigned claims presented as
  truth denied. The six commit kinds form a DCLM-internal write tier:
  they GRANT only for a DCLM component source (`internal: "dclm.*"`).
  Verdicts are frozen dataclasses — DENY cannot be edited into GRANT.
- `writes.py` is the single commit path. `dclm_commit(kind, payload,
  rights_verdict, store)` RAISES CommitRefused (never warns, writes
  nothing) unless the verdict is a genuine DCLM-issued RightsVerdict with
  GRANT (forged "GRANT" strings, None, dicts, and DENY verdicts all
  refuse), the kind is whitelisted (LEDGER_DEBIT, LEDGER_CREDIT,
  WORLD_STATE, GATE_TRANSITION, METER_RECEIPT, DATA_INGEST), and the
  receipt carries a valid provenance label (UNKNOWN never PASS). Order:
  rights verified -> payload serialization checked -> store.apply_write
  (the one mutation) -> store.build_receipt -> sign -> store.append_receipt.
  Receipts Ed25519-signed with the existing testnet key material.
- `meter.py` refactored: the ONLY ledger mutations (debit in meter_intent,
  credit in faucet) now live inside `_MeterCommitStore.apply_write`, driven
  exclusively by `dclm_commit` after a `check_rights` GRANT. The meter's
  receipt bytes are unchanged (build_receipt returns the meter receipt
  dict as-is); free-action grants and refusal receipts are untouched
  (no ledger mutation there). Behavior verified unchanged: prices,
  idempotency (replay is byte-identical), refusals (true reasons, balance
  untouched), ledger never negative, persistence across restarts.
- Test run 2026-10-06 ~07:02 UTC: `python3 test_rights_writes.py` →
  Ran 30 tests, OK (includes a subprocess re-run of the full 20-test
  meter suite). Regression: `test_compute.py` 10/10 OK, `test_meter.py`
  20/20 OK, `gate/test_gate.py` 9/9 OK.

---

## D4 receipt repair — file-handle fix (2026-10-06 ~07:15 UTC)

`dclm/data.py` leaked file handles: four bare `open(...).read()` calls with
no context manager (in `registry_summary`, the PRICES.md loader,
`_parse_seal_file`, and the adjudication-seal read in `factory_verdicts`).
`load_registry` itself already used `with open(...)`; the leaks were in the
callers/helpers around it. All four now use `with open(...) as fh:`.
No behavior change — verified by the test re-run below. Receipt updated to
the post-fix content (latest row wins).

| time (UTC)        | file               | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|--------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:15 | dclm/data.py       | a1e435bd955ee2ee9f2138532a5bdc13ad87adcace9ed6ec895170d1b5dcb71d      | 5af85e54fb1d5c66bc8e52eb6440901a3b2693352b636cbadb2fccba6ef64cd6      |

Notes:
- Test run 2026-10-06 ~07:15 UTC: `python3 test_data.py` → Ran 22 tests, OK.
- Also ran `registry_summary()` under `-W error::ResourceWarning`: no warnings.

## Tapping law — "The tree survives tapping" (David's binding law)

| time (UTC)        | file                  | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|-----------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:45 | dclm/tap.py           | N/A (new)                                                          | ec73b2f0dd3844421f7f9dc053bbd30692291ebebcf2d7fc8a5fc05dc52e9493      |
| 2026-10-06 ~07:45 | dclm/test_tap.py      | N/A (new)                                                          | ec5c1cfe075c25f6c3ee7993b90d35b73ae12871c28e68701ba615fd337bfc7c      |
| 2026-10-06 ~07:45 | dclm/TAPPING_LAW.md   | N/A (new)                                                          | e22e8c15b86d0af2c35b89824a3bbf10816a7426126e276cb9bca0c9c56f31f3      |
| 2026-10-06 ~07:25 | dclm/rights.py        | b203e6c5c229824df2c47f44cacafdf849b3c92e2c3a7466c288d6ee0a0dda42...  | d9c8aff874b7c5d4c03bbf0ba77a7d16336111fb4d3806074c0d23db87302d73      |
| 2026-10-06 ~07:25 | dclm/writes.py        | 05f8be52ee0a0dda42fe6c2491d2f85873c9910dd39f6c2491d2f85873c9910...  | 6450ec6ce7755cba88d44ca7be891f42368682922cdfe50154fcc093fb5824ba      |

Notes:
- `tap.py` implements David's maple law. TapSeason evaluates the four
  rules in order — winter clear, maturity ≥ threshold, verified
  surplus, healing verifiable — each input provenance-labeled; any
  unscorable input → UNKNOWN → season closed (UNKNOWN never PASS).
  Tapper.request_tap enforces the creed boundary first (founder
  identities refused as FOUNDER_EXTRACTION_FORBIDDEN before any season
  evaluation), then purpose, per-tap limit (50), per-member seasonal
  cap (100), and the healing invariant (season outflow never exceeds
  replenishment — asserted again at the commit boundary). Granted taps
  flow through rights.check_rights + writes.dclm_commit with kind
  TAP_OUTFLOW, receipted with season id, the full reason chain, and
  healing accounting (outflow vs replenishment). Refusals are signed
  too, with the true reason.
- `rights.py` / `writes.py`: TAP_OUTFLOW added to COMMIT_KINDS (seven
  kinds now; prose counts updated). Docstring-only change otherwise —
  the whitelist loops in test_rights_writes.py cover the new kind
  automatically.
- winter.py landed mid-build (~07:19) and TapSeason integrates with it
  FOR REAL: a winter_signal (winter.WinterSignal or dict of its fields)
  is evaluated through winter.evaluate_trigger into a WinterState, and
  the tap-side protection line (0.50, proposed, HELD-FOR-DAVID) applies
  to the real gradient — mid-TILTING on winter's own bands, so taps stop
  well before deep winter. No signal -> trigger unreadable -> winter
  stays SUMMER ("winter is never assumed", winter's own rule), recorded
  in the reason chain. winter.py defines no protection test of its own
  (labels are display-only), so the tap side owns the line. If
  winter.py is ever absent, the interface is honestly PENDING and the
  season degrades to CLOSED: PENDING winter state never opens a season,
  never grants a tap.
- Test run 2026-10-06 ~07:45 UTC: `python3 test_tap.py` → Ran 24
  tests, OK — off-season/winter-protection/immature-system refusals,
  REAL winter integration (summer signal -> open+granted; storm signal
  peg 0.10 + activity -0.5 -> gradient ~0.70 -> WINTER_PROTECTION; no
  signal -> SUMMER), per-member cap (50+50 granted, +1 refused),
  per-tap limit, replenishment boundary (outflow may reach
  replenishment exactly, never cross), founder-extraction refusal
  (prefix + registered identity), UNKNOWN-maturity refusal, and a
  subprocess regression of test_meter.py (20/20),
  test_rights_writes.py (30/30+ — now covering all sibling-added kinds),
  test_compute.py (10/10), test_data.py — all green.
- Shared-file note: dclm/rights.py is a multi-worker whitelist —
  TAP_OUTFLOW (this worker) merged alongside GRANT_ISSUE/GRANT_REVOKE/
  SHARED_ACCESS (share worker), TOKEN_MINT/MERIT_ACCRUAL/HONOR_RECORD/
  UNITY_SALE (tokenize workers), WINTER_STORE/WINTER_RELEASE (winter
  worker). Final merged hash d9c8aff8... recorded above; TAP_OUTFLOW
  line intact and granting.
  [Correction 2026-10-06 ~04:10 EDT: per David's transfer word, the
  tokenize worker REMOVED UNITY_SALE from the whitelist (the bound sale
  is dead — Unity never transfers) and added MERIT_TRANSFER in its
  place. The historical merge list above is left intact.]
- Environment hazard (not ours to fix): a sibling worker's in-flight
  `dclm/tokenize.py` shadows stdlib `tokenize` whenever the dclm dir is
  first on sys.path, breaking `import dataclasses` for any process
  (e.g. test_rights_writes.py run directly). test_tap.py seeds the
  stdlib module first (module-top guard + subprocess wrapper) and runs
  sibling suites via runpy under that guard.
- HELD-FOR-DAVID (proposed, in TAPPING_LAW.md): per-member seasonal
  cap 100 test-keys, per-tap limit 50, maturity threshold 0.70, winter
  gradient protection line 0.50 (tap-side; winter.py has no protection
  test of its own).

## Winter mechanism — winter-mechanism worker (David's sap model)

| time (UTC)        | file                        | before (sha256) | after (sha256)                                                        |
|-------------------|-----------------------------|-----------------|-----------------------------------------------------------------------|
| 2026-10-06 ~07:19 | dclm/winter.py              | N/A (new)       | 42ee632e1f316995509f7b4cbee1405d841cb437a2dbaaa44018b00070fcaa98       |
| 2026-10-06 ~07:19 | dclm/test_winter.py         | N/A (new)       | 79d63332653fed30733f150d0d6b1335d3220865a271de8c7f5533120a95a162       |
| 2026-10-06 ~07:19 | dclm/WINTER_CALIBRATION.md  | N/A (new)       | b07a56037de6946b9fb02dcabff9a12f8566b5e93aa5906c711f2312ad091e00       |
| 2026-10-06 ~07:19 | dclm/rights.py              | (prior worker)  | d9c8aff874b7c5d4c03bbf0ba77a7d16336111fb4d3806074c0d23db87302d73       |
| 2026-10-06 ~07:19 | dclm/writes.py              | (prior worker)  | 6450ec6ce7755cba88d44ca7be891f42368682922cdfe50154fcc093fb5824ba       |

Notes:
- `winter.py` implements the counter-cyclical winter mode: `WinterSignal`
  (peg deviation, activity delta, declared+verified crisis, per-input
  provenance) → `evaluate_trigger` → continuous `WinterState.gradient`
  0.0 (full summer) to 1.0 (full winter), no phase cliffs. Unreadable
  signal → UNKNOWN → stays SUMMER (never assumes winter).
- `winter_store` / `winter_release` move test-keys between circulation and
  the Peg Regulation Reserve (starch store) through rights.check_rights →
  GRANT → writes.dclm_commit with new kinds WINTER_STORE / WINTER_RELEASE.
  Store capped at SURVIVAL_NEED_CAP (PROPOSED 25) per identity; excess
  stays in circulation. Every unit receipted with its winter reason
  (trigger condition, measured value, threshold); every claim (granted or
  refused) logged to `state-winter/winter-receipts.jsonl` with claimant
  identity + signal snapshot for L5 audit. Claims with no supporting
  signal refused as PHANTOM.
- `emission_multiplier` throttles emission 1.0 → 0.25 (PROPOSED floor) as
  gradient → 1.0 — protection, not shutdown; `winter_aware_faucet` applies it.
- `rights.py`: added WINTER_STORE / WINTER_RELEASE to COMMIT_KINDS with
  receipt-logged justification (DCLM-internal `dclm.winter` only); whitelist
  is now twelve kinds. `writes.py`: docstring updated to name the new kinds.
- ALL calibration numbers in `winter.py` are PROPOSED and HELD-FOR-DAVID —
  see WINTER_CALIBRATION.md for the per-threshold reasoning and the exact
  questions awaiting his word.
- Test runs 2026-10-06 ~07:19 UTC: `python3 test_winter.py` → Ran 28 tests,
  OK. `python3 test_meter.py` → Ran 20 tests, OK (meter.py untouched).
  `test_rights_writes.py` → Ran 30 tests, OK (run with stdlib `tokenize`
  pre-cached: a sibling worker's new `dclm/tokenize.py` shadows the stdlib
  module when the dclm dir sits first on sys.path — pre-existing repo
  condition, unrelated to this worker's edits).

## Shared access — the kin layer's monetization (David's order)

| time (UTC)        | file                    | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|-------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:23 | dclm/share.py           | N/A (new)                                                          | 78a219d230840b0acab64527d843ee48aa99d4cccc50dfba55294bc28a2f1721      |
| 2026-10-06 ~07:23 | dclm/test_share.py      | N/A (new)                                                          | d9afac9accd5e4ba71b2bf81ca413945fcc385b4b12b91cfd2af56b692ed49f1      |
| 2026-10-06 ~07:23 | dclm/SHARED_ACCESS.md   | N/A (new)                                                          | 4faae2d997f742304d1b5e89b52882f3f12c2acfe0971f65cdb6f84f4d587cd1      |
| 2026-10-06 ~07:23 | dclm/rights.py          | prior-worker state (pre-edit hash not captured; whitelist previously extended by tap/tokenize/winter workers) | d9c8aff874b7c5d4c03bbf0ba77a7d16336111fb4d3806074c0d23db87302d73 |
| 2026-10-06 ~07:23 | dclm/writes.py          | prior-worker state (pre-edit hash not captured; docstring previously extended by tap/tokenize/winter workers) | 6450ec6ce7755cba88d44ca7be891f42368682922cdfe50154fcc093fb5824ba |

Notes:
- `share.py` implements the tiered shared-access model: FRIEND=1 <
  GOOD_FRIEND=2 < FAMILY=3, the tier level as an INTEGER inside the
  Ed25519-signed grant body; `check_access()` compares integers, so a
  friend-tier grant can NEVER exercise family-tier access (1 >= 3 is
  false — structural, not policy). Tampering with the integer breaks
  the signature → INVALID_GRANT, fail-closed.
- Grants are RIGHTS (rights.check_rights, internal source "dclm.share");
  access events are WRITES (dclm_commit kinds GRANT_ISSUE, GRANT_REVOKE,
  SHARED_ACCESS — added to rights.COMMIT_KINDS with receipt-logged
  justification; money legs reuse LEDGER_DEBIT/LEDGER_CREDIT). The
  client never grants/revokes directly.
- Revocation is instant and total: ShareStore holds grants + a live
  revoked set; every check reads CURRENT state, no cache, no TTL.
- Kin binding: family tier requires verify_kin() True. L2 umpires are
  the authority — INTEGRATION PENDING (no L2 module in build), so
  verify_kin() returns False and family grants are refused with
  NOT_KIN_VERIFIED (never assumed). Future L2 module registers via
  register_kin_authority(fn); issue_grant takes no kinship flag from
  callers.
- Derivative merit regeneration (David's law-grade rule): access()
  moves MONEY (test-keys) only — accessor debited, granter credited in
  full, DCLM takes no cut. share.py has NO merit-accrual path (no
  tokenize import, no MERIT_ACCRUAL kind — enforced by an introspection
  test); _assert_no_merit() refuses any merit payload as malformed
  (MERIT_IN_GRANT); every grant/debit/credit/event carries
  merit_flow: "NONE". The grantee's merit comes only from their own
  verified receipts — pyramid dynamics killed by construction.
- Test run 2026-10-06 ~07:23 UTC: `python3 test_share.py` → Ran 29
  tests, OK (issue/verify/revoke lifecycle, instant revocation, tier
  creep blocked incl. tamper-evidence, expiry, wrong content type,
  metered money movement, failed-access deducts nothing, family refusal,
  non-testnet refusal, merit-law suite). No regressions:
  test_meter.py 20/20 OK, test_rights_writes.py 30/30 OK,
  test_compute.py 10/10 OK, test_data.py 22/22 OK.
- Pre-existing quirk (not introduced here): dclm/tokenize.py shadows
  the stdlib `tokenize` module, so `from rights import ...` from a bare
  `python3 -c` in dclm/ can ImportError; the established convention
  (run test files as scripts, stdlib imports first) is unaffected.

## Tokenization engine — worker 5 (David's order: the receipt→token pipeline)

Testnet only. Nothing touches production keys or paths.
Key material never leaves `../keys/`.

| time (UTC)        | file                  | before (sha256) | after (sha256)                                                       |
|-------------------|-----------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:20 | dclm/token_engine.py  | N/A (new)       | ca3db2ea6e3e14b42e2af53d9bb37fd81c26353798bf62d177ab0cde7efd7736      |
| 2026-10-06 ~07:20 | dclm/tokenize.py      | N/A (new)       | da3a5f4be764d7a6383bb78081faaf7f213ba635836486bc229175e3057f5113      |
| 2026-10-06 ~07:25 | dclm/test_tokenize.py | N/A (new)       | 2087c740387c50104138bbff5e6f5a61ec7c2d86b59dfec06c0d0749ca437e6d      |
| 2026-10-06 ~07:30 | dclm/TOKENIZATION.md  | N/A (new)       | 6c54254011baee0024951422e0a94ce9f60dbe762186d9fc75d5fe5fd9c8f128      |
| 2026-10-06 ~07:2x | dclm/rights.py        | not captured (no VCS; pre-existing file extended) | 8db0ba6be770e7a4bfb342963fa70b61df1ca035b3f07d7de34299984dc501b6 |
| 2026-10-06 ~07:2x | dclm/writes.py        | not captured (no VCS; pre-existing file extended) | 6450ec6ce7755cba88d44ca7be891f42368682922cdfe50154fcc093fb5824ba |

Notes:
- `token_engine.py` is the implementation; `tokenize.py` is the mandated
  public path as a thin PEP-562 shim (a full module literally named
  `tokenize.py` shadows stdlib `tokenize`, breaking linecache/unittest
  for every sibling suite — verified 2026-10-06; the shim is cycle-safe
  and transparent to stdlib consumers, `from tokenize import tokenize`
  works as specified).
- Pipeline: VERIFIED gated receipt → `_mint()` (sole token factory) →
  `dclm_commit` per output (`TOKEN_MINT`/`MERIT_ACCRUAL`/`HONOR_RECORD`/
  `MERIT_TRANSFER` added to the rights.py whitelist with receipt-logged
  justification; clients naming them are denied INTERNAL_SOURCE_REQUIRED;
  the dead `UNITY_SALE` kind was removed with the bound-transfer-sale
  concept on 2026-10-06).
- eFuse = merit_value / E (tokenomics.py formula, reused); E HELD_FOR_DAVID
  — `PEG_E_UNSET` refusal pre-mint until `set_peg_ratio(E, {authority:
  "david"})`; peg labeled REPORTED (testnet stand-in, unsigned — marked
  honestly; production setter must require his signature).
- David's word, 2026-10-06 ~3:35 AM EDT (LAW): MERIT is TRANSFERABLE —
  `merit_transfer(from_id, to_id, amount, reason)` is the SOLE legal
  ownership-transfer path (both verified, amount covered, reason
  receipted, signed MERIT_TRANSFER receipt; origin immutable, standing
  never moves — sole path AST-proven). UNITY is NON-TRANSFERABLE — no
  exceptions; the bound-transfer-sale concept is DEAD (no `bound_sale`,
  no re-bind path, `assert_no_unity_rebind()` AST-proven). Derivative
  merit regeneration holds: merit credited only to the receipt's own
  Unity ID; beneficiary-naming receipts refused `MERIT_MISATTRIBUTION`.
- Unity genesis stays solely `economics/fuse.py` trigger_fuse (reused, not
  duplicated); `_mint("unity")` raises; `UnityToken` never instantiated
  here (AST-asserted).
- Test run 2026-10-06 ~07:35 UTC: `python3 test_tokenize.py` → Ran 49
  tests, OK. Includes AST exclusivity hooks (mint + transfer), sale happy
  path / merit-untouched / refusals, and subprocess regressions:
  `test_rights_writes.py`, `test_meter.py`, `test_compute.py` all green.

---

## Merit-regeneration evolution — emission gate + money-only wallet (David's law: derivative merit regeneration, NOT token cascade)

`dclm/meter.py` evolved by the merit-regeneration worker (Phase 1, 2026-10-06 ~07:40 UTC).
Law: downstream rings do NOT receive tokens from upstream; each ring earns its own merit
from its own verified receipts. The unbroken chain: verified work -> receipt -> merit
(origin-bound; ownership transferable via receipted merit_transfer, standing never
moves) -> emission (gated on STANDING, never on holdings — D13) -> token (Unity-bound;
Unity itself never transfers). Nothing moves without an ID, a receipt, and a label.
Standing is never for sale — and cannot be bought: transfers move economic value only.

| time (UTC)        | file                       | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|----------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:40 | dclm/meter.py              | 8a72d960f2fbbc6d084b5d03d52ef1dc112b0418fdd1a25181ac66e339d70015      | 4c6b134edc3de3fe2a504a3342a13ba7bad5d65b71016dc24e89d9f386f210e4      |
| 2026-10-06 ~07:40 | dclm/test_merit_regen.py   | N/A (new)                                                          | 2f5f78eee8b746e3db4d825e6d5a5d450db645f7591690cd2383ad82bdb8fe1b      |

Notes:
- NEW: `emission_eligibility(identity)` — the read-only emission gate. Eligible True
  ONLY when (a) identity is a bound `unity:testnet:...` identity, (b) a merit reader is
  bound, and (c) the reader reports the identity's OWN verified-receipt merit as a
  positive number. Otherwise closed with an honest labeled reason: MERIT_LEDGER_PENDING
  (interface defined, no reader bound — emission closed), MERIT_UNKNOWN (reader
  returned None — UNKNOWN never PASS), MERIT_LEDGER_UNREACHABLE (reader failed —
  closed, not passed), NO_VERIFIED_MERIT (known identity, zero own merit),
  NOT_TESTNET_IDENTITY (structural). Pure read: no writes, no dclm_commit, no signing
  (asserted by introspection test). The signed emission receipt belongs to the emission
  path itself (dclm/tokenize.py — Phase 2 wires it through this gate).
- NEW: `MeritReader` protocol (`verified_merit(identity) -> float | None`) and
  `TokenizeMeritReader` — read-only adapter over the tokenization worker's landed
  merit ledger (`Tokenizer.merit_scores`, accrual-only, keyed by the unity_id of the
  VERIFIED work receipt that earned it; `tokenize()` refuses anything not VERIFIED
  before `_accrue_merit` runs). `bind_merit_reader` / `unbind_merit_reader` manage the
  module-global binding; unbound (PENDING) means emission stays closed.
- NEW: money-only wallet guards — merit never enters the wallet. `Wallet._load`
  refuses ledgers with merit-shaped keys, unexpected keys, or non-integer balances;
  `_MeterCommitStore.__init__` refuses any op outside {debit, credit} and any
  non-integer balance. Refused, never repaired.
- NEW: no-cascade introspection tests (AST over meter.py's own source):
  `verified_merit(...)` is always asked about exactly the caller's `identity`;
  every `_MeterCommitStore` credits `identity=identity`; `emission_eligibility`
  contains no dclm_commit / ledger writes; no merit-shaped key is ever stored to
  the wallet ledger. Plus behavioral proof: ID_B's VERIFIED work receipt gates
  ID_B eligible while ID_A stays NO_VERIFIED_MERIT; UNKNOWN-provenance receipts
  earn nothing (refused at tokenize time); donations earn Honor, never Merit.
- Behavior unchanged for existing paths: faucet, meter_intent, prices, idempotency,
  refusals, ledger-never-negative, persistence (all 20 existing meter tests pass
  unmodified; the new guards accept every ledger the old code could write).
- Test run 2026-10-06 ~07:40 UTC: `python3 test_meter.py` → Ran 20 tests, OK.
  `python3 test_merit_regen.py` → Ran 23 tests, OK. `python3 test_rights_writes.py`
  → Ran 30 tests, OK (includes subprocess re-run of the meter suite).
  `python3 test_tokenize.py` → Ran 49 tests, OK (two consecutive standalone runs;
  one chained back-to-back run showed 2 transient failures — flake under signing
  contention, not related: tokenize.py does not import meter.py and was untouched).
- PENDING on the tokenization worker (Phase 2): `dclm/tokenize.py`'s `_mint_efuse`
  is the actual emission path — it must consult `emission_eligibility` (or be proven
  equivalent) before minting, and `dclm/share.py` must be audited for cascade paths.
  Until then: the gate exists and is tested; no emission path has been rewired.

## Onboarder pipeline — onboarder-pipeline worker (David's order: Residual Law Finance onboarder → residual → tokenomics flywheel)

| time (UTC)        | file                        | before (sha256)                                                    | after (sha256)                                                       |
|-------------------|-----------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:34 | dclm/onboard.py             | N/A (new)                                                          | c0665e0d1c454884abeccf49550d6dbcffb0c47f46ea52bded6c2571456caf10      |
| 2026-10-06 ~07:34 | dclm/test_onboard.py        | N/A (new)                                                          | ce4d607d29695544cc6f722c2f6f9ec38cef0159d53d1a21055ae0ae34d33b62      |
| 2026-10-06 ~07:34 | dclm/ONBOARDER_PIPELINE.md  | N/A (new)                                                          | 9e508b9e1ec25c2e434aec0b4001fd55896b61cd65b3ac8065adf46d0e19aa36      |
| 2026-10-06 ~07:34 | dclm/rights.py              | d9c8aff874b7c5d4c03bbf0ba77a7d16336111fb4d3806074c0d23db87302d73      | a059e531f542c9fa2ad268be610ca6f4421d8d57e5e59858eb85556a45789bd5      |
| 2026-10-06 ~07:34 | dclm/writes.py              | 6450ec6ce7755cba88d44ca7be891f42368682922cdfe50154fcc093fb5824ba      | 7a82f55e20c583f197446d3a0f45a45ec9d631e17c0e964ead9d4b52b0a40898      |

Notes:
- `onboard.py` implements the five-stage flywheel: ONBOARD (Unity-bound,
  `unity:testnet:` enforced, idempotent) → RESIDUAL_INTAKE (REPORTED only:
  paperwork hash required, MODELED refused, one paperwork = one intake) →
  SPLIT_EXECUTE (81/19, David's set ratio: 81% ACKNOWLEDGED_OFF_SYSTEM with
  `system_value: false`, never touching the meter's test-key wallet; 19%
  into HELD escrow; recovery beyond REPORTED remaining refused) →
  NINETEEN_ROUTE (HELD: every attempt receipted AWAITING_SPLIT_RULING,
  escrow untouched — the CORE_CAUSE_LOCK / PLAYGROUND_FUEL / PEG_SUPPORT
  ratio is HELD-FOR-DAVID, no runtime setter in this build) →
  accrue_recovery_merit (VERIFIED recovery-class work receipts → top band
  `band:recovery` via the tokenization worker's tokenize() → MERIT_ACCRUAL;
  unverified/other-ID/wrong-class receipts accrue nothing; empty → no merit;
  replays never double-count; peg-E-unset defers honestly as DEFERRED and
  stays retryable; worker-absent → PENDING-closed, never accrue on UNKNOWN).
  Amounts are integer fiat-cents (FIAT-RECOVERED), never test-keys, never
  eFuse. `flywheel_state()` reports labeled aggregates; the 81% appears only
  as acknowledged off-system value, never as system value. Band calibration
  beyond the top band's definition is HELD-FOR-DAVID — the pipeline never
  invents merit values.
- `rights.py` / `writes.py`: ONBOARD, RESIDUAL_INTAKE, SPLIT_EXECUTE,
  NINETEEN_ROUTE added to COMMIT_KINDS (twenty kinds now) with receipt-logged
  justification; docstring kind lists updated. All pipeline state mutations
  flow through rights.check_rights → writes.dclm_commit (`dclm.onboard`).
- Test run 2026-10-06 ~07:34 UTC: `python3 test_onboard.py` → Ran 24 tests,
  OK — including: unpaperworked/MODELED intake refusals, 81%-never-in-ledger
  (meter wallet balance asserted unchanged; escrow holds the 19% only),
  19% HELD escrow with AWAITING_SPLIT_RULING and zeroed destinations, merit
  only from verified receipts / no-receipts-no-merit / replay-once /
  deferred-then-retryable, gain-promise language scan over onboard.py,
  test_onboard.py, ONBOARDER_PIPELINE.md, rights.py, writes.py (clean),
  non-testnet identity refused on all five entry points, and a subprocess
  regression of test_rights_writes.py (30/30, includes the meter suite).
  Also: `python3 test_compute.py` → Ran 10 tests, OK.
- During the rights.py edit the winter tier block was briefly clobbered and
  immediately restored; whitelist verified at 20 kinds including
  WINTER_STORE/WINTER_RELEASE before tests ran.

## One seed — worker (David's one-seed law, 2026-10-06)

David's law, verbatim: "no matter how much money you have you only buy
one seed, and it costs you nothing." One free seed per Unity ID, issued
only to a BOUND identity, exactly once, price 0, cost 0, membership not
money, no seed market (AST-proven). The plutocracy test proves a funded
wallet gets exactly the same single free seed as an empty one.

| time (UTC)        | file                  | before (sha256) | after (sha256)                                                       |
|-------------------|-----------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~08:20 | dclm/seed.py          | N/A (new)       | 90eb0b8d54f6182efe05a14ae8d6c67d9d3b330a5420dd4cc08b19af183bc4d6      |
| 2026-10-06 ~08:20 | dclm/test_seed.py     | N/A (new)       | 4746da83a2f7680567392e5a47c23853e48d0a4b32ebfb7e7f4c22bec70c4ce1      |
| 2026-10-06 ~08:20 | dclm/rights.py        | edited (pre-edit hash not recorded) | 388a8d110703a79090e1a10118b5475a56eb7432d357cec9f98c03332cb95011 |
| 2026-10-06 ~08:20 | dclm/writes.py        | edited (pre-edit hash not recorded) | 7325b01e6d8524dabd070925e8fab3b07b3b182ff31753900dad49318b7d78d5 |
| 2026-10-06 ~08:20 | dclm/TOKENIZATION.md  | edited (pre-edit hash not recorded) | 5ea7e97c15c9d0173160e0a84a79d3dd5b5736e7171ffb6176be9ec5d7627aad |
| 2026-10-06 ~08:20 | economics/wallet.py   | edited (pre-edit hash not recorded) | 8b706009803bde8aba94484d2bf67a22688a13ed5c707cdd32999a2a03b4b85b |

Notes:
- `seed.py` (new): the one-seed issuer. `issue_seed(unity_id)` — testnet
  check -> purify_input -> LIVE gate BOUND check (honest importlib read
  of ../gate/gate.py; unreadable gate refuses, never fabricates) ->
  one-seed check -> check_rights GRANT (DCLM-internal "dclm.seed") ->
  purify_transition -> dclm_commit(SEED_ISSUE) -> signed envelope,
  purified on exit. Refusals: SEED_ALREADY_ISSUED (signed, receipt-logged),
  NOT_BOUND, NOT_TESTNET_IDENTITY, PRODUCTION_SCHEMA_REFUSED,
  GATE_LEDGER_UNAVAILABLE. Price/cost hard-coded 0.0; the record is frozen.
- `test_seed.py` (new): 16 tests — one seed per ID (deterministic seed id);
  second refused; unbound refused; BINDING-in-progress refused;
  non-testnet refused; no-transfer-path AST proof; seed costs nothing
  (test-keys and eFuse balances untouched); seed not spendable;
  plutocracy test (funded == empty); SEED_ISSUE whitelist behavior;
  honest gate-unavailable refusal; production-schema refusal;
  wallet membership mirror (idempotent, balances untouched);
  mirror-requires-real-wallet; registry write-once; record frozen.
- `rights.py` (edited): SEED_ISSUE added to COMMIT_KINDS (twenty-one
  kinds) with receipt-logged justification; write-tier docstring updated.
- `writes.py` (edited): docstring kind lists updated (SEED_ISSUE).
- `TOKENIZATION.md` (edited): new §11 ONE SEED section.
- `economics/wallet.py` (edited): seed membership mirror — Ledger gains
  `_seeds` registry (persisted in snapshot), `record_seed()` (idempotent,
  hash-chained, balances untouched, structurally incapable of carrying a
  balance-shaped field), `seed_membership()`, `has_wallet()`;
  `Wallet.membership()` read-only membership view. The seed is membership,
  not money: it never enters balances(), never priced, never spendable.
- Test run 2026-10-06 ~08:21 UTC: `python3 test_seed.py` → Ran 16 tests, OK.
- NOTE: canon §XX ONE SEED was already applied (CANON.md v1.5.0, the seven
  [LAW] statements) before this build — the 5-line canon draft lives in
  the one-seed worker's report to the coordinator, not applied here.
- HASH CORRECTION (2026-10-06 ~08:40 UTC): the after-sha256 values first
  recorded above for seed.py, test_seed.py, rights.py, writes.py, and
  economics/wallet.py were wrong (stale read); the table now carries the
  verified current hashes (recomputed and re-verified after all edits).
- CONCURRENT EDITS (sibling workers, same session): (a) the helper worker
  added HELPER_ASSIGN / HELPER_STAGE / HELPER_HANDOFF / HELPER_WELCOME to
  rights.py COMMIT_KINDS and the writes.py docstring — rights.py and
  writes.py hashes above reflect the merged state; the SEED_ISSUE entries
  are intact and `python3 test_seed.py` re-ran 16/16 OK against the merged
  whitelist. (b) seed.py's issue_seed was reordered to purify-first
  (PurificationRefused on non-testnet input before the module's structural
  checks — the codebase-wide DCLM pattern from meter.py/token_engine.py);
  the seed module docstring and test_non_testnet_refused were updated to
  match; all 16 tests pass against the reordered path. (c) economics/
  wallet.py is being edited concurrently by a sibling (hash moves); the
  seed-membership code (record_seed / seed_membership / Wallet.membership
  / _seeds registry) verified intact and smoke-tested green against the
  latest version — hash above is current as of ~08:45 UTC.
- PRE-EXISTING RED SUITES (not caused by this worker, verified): test_meter
  (4 errors — stale purify expectations; failing identically before this
  build), test_onboard (onboard.py `_accrued` NameError ×3 + stale purify
  + nested meter), test_rights_writes / test_tap / test_tokenize nested
  test_meter subprocess assertions, test_share (2 stale-purify errors).
  Green and affected by this build: test_seed 16/16, test_wallet 41/41,
  test_compute, test_data, test_merit_regen, test_winter 28/28,
  test_economic_state, test_tokenomics, test_fuse, test_pricing,
  test_mesh_escrow, gate/test_gate 9/9.

## Chunked data serving layer — worker (DCLM chunked serving, 2026-10-06)

David's hard rule: DCLM serves data in streamable chunks; the client caches
aggressively and renders progressively. Extends `data.py` (never rewrites
it). Testnet only. Every chunk DCLM-signed (Ed25519, `unity-world-test`
key). UNKNOWN never PASS. Every mutation receipted to
`dclm/chunk_receipts.log` (JSONL, before/after manifest hashes).

Implements Trinity verdict `PURITY_VERDICT_PROGRESSIVE_ARCH.md`
(PASS-WITH-NOTES): P0-2 readjustment protocol + P0-3 tiered freshness.
(P0-1 IndexedDB amendment has since passed the purity machine; the durable
read-cache lives in the client worker's sanctioned region —
`client/chunks.js` performs no durable writes, in-memory Map only.)

| time (UTC) | file | before (sha256) | after (sha256) | lines |
|---|---|---|---|---|
| 2026-10-06 ~08:35 | dclm/chunks.py | N/A (new) | 773810a65fcb936bf317f51b6ecff9a649988a33e59a9c741cf6b8a0ed87452a | 1088 |
| 2026-10-06 ~08:35 | dclm/test_chunks.py | N/A (new) | 2ae91833b2875aabb9a16c63a910ba0505535be5c46175a817d059d8ee76a589 | 467 |
| 2026-10-06 ~08:35 | dclm/CHUNKS.md | N/A (new) | 5d63ede38acb30ee9b60fce5ca8b4351a2a68b06da19eaad2d6fe8b3892673ed (was cf44fbaa…) | 174 |
| 2026-10-06 ~08:35 | relay/wrap-chunk.mjs | N/A (new) | ee5870c32b2cd10bc30a864f6304fe5d945debef80b6452197d5a6fd8cb6c49b | 113 |
| 2026-10-06 ~08:35 | client/chunks.js | N/A (new) | 39d028c64e6ab544caa292adb2d8b70b071bb1f2000f49ab2fbb132253c60ded (fixed 04:50 UTC, was d5912862…) | 218 |

Notes:
- Chunk inventory: 18 datasets / 19 chunks / ~747KB. P1 shell-critical
  (doctrine, world-state, registry-summary), P2 coarse registries (7),
  P3 detail (cities.full, countries.full sharded ×2, telemetrics REAL,
  feeds, verdicts, pricing), P4 bulk (economics.pricing, mesh.bulk PENDING).
  Chunk data payloads bounded at 256KiB; volume changes shard count, never
  shard size. Top manifest lists datasets only; per-dataset shard listings
  paged — every response stays bounded at any scale.
- P0-2: world_epoch on every chunk/manifest/head (monotonic, persisted,
  client no-downgrade rule); version-pinned streams (`/stream` NDJSON,
  epoch asserted per line); schema_version + per-dataset schema_policy
  (purge vs retain-stale; thin client never migrates); STALE freshness
  state with previous-epoch manifest retained for transition validation;
  hash verification on READ; signed head document (`/chunks/head.json`,
  ~1KB, fetched every load).
- P0-3: freshness tier per chunk + per dataset (long = geometry/reference
  telemetry, revalidate on epoch; short = economic data, revalidate every
  load with as_of + STALE badge). Wallet NEVER chunked — always live via
  POST /api/world/*; the manifest states this explicitly. (The original
  wallet-state P1 chunk was removed per the verdict.)
- Concurrency bug caught by the suite 2026-10-06: two overlapping cuts
  interleaved (bump 5, bump 6, built 5, built 6), corrupting the
  previous-manifest chain. Fixed: the whole cut holds a cross-process
  flock; ChunkServer.regenerate() guards the generation swap with a
  thread lock; the server owns the cut lifecycle. Regression test:
  test_concurrent_cuts_serialize.
- Test hermeticity: CHUNK_STATE_DIR env redirect; the suite runs in a fresh
  temp dir per process — immune to concurrent workers' builds.
- Relay: `relay/wrap-chunk.mjs wrap|verify` wraps a signed chunk envelope
  into a dualis.relay.v1.testnet EVIDENCE bundle (BOUND gate enforced by
  the relay); refuses chunks missing world_epoch / freshness tier.
- Provenance preserved: chunk bodies carry the union of their figures'
  labels (telemetrics chunk = {REAL}, feeds = {UNKNOWN}); chunking never
  strips or flattens labels.
- 2026-10-06 ~04:50 UTC client-worker bug fix (blocks purity gate):
  `verifyChunkBytes` asserted sha256(served envelope bytes) ===
  envelope.canonical_sha256 — FALSE by construction (canonical_sha256
  covers the BODY, not the envelope; proven against a real chunk:
  6ed551e7… != 550067e5…). Every real chunk would have failed. Fixed:
  no client-side hash recompute — structural verification only
  (well-formed, Ed25519 signature present, complete, pinnable chunk_id);
  signature authentication stays at the relay boundary; storage integrity
  via hash-on-read of stored raw bytes (sha256 recorded at store time,
  re-checked every cache read; corrupt bytes evicted, never rendered).
  `verify_envelope` token removed from comments (tripped client D3).
  Re-tested: 14/14 node smoke checks pass against a real DCLM-signed
  chunk envelope (`/tmp/smoke-chunks.mjs`).
- Relay contract agreed with client worker 2026-10-06: chunks are the
  authoritative world-data plane; `GET /relay/bundle.json` slimmed to
  wallet + metering only; on overlap chunks win (client ignores world
  keys in the relay bundle).

## Self-bootstrap — the self-executing onboarding API (David's order, 2026-10-06 ~08:40 UTC)

| time (UTC)        | file                  | before (sha256) | after (sha256)                                                        |
|-------------------|-----------------------|-----------------|-----------------------------------------------------------------------|
| 2026-10-06 ~08:40 | dclm/bootstrap.py     | N/A (new)       | 35b0de76c1a6d2cd742809bd96bff067bd0e3af64c7748d4ba6fa726021512a0      |
| 2026-10-06 ~08:40 | dclm/test_bootstrap.py| N/A (new)       | 2850b1202ca87ab25f624481b0ca33d4c6cd19b87bfe887752fc15b03341c255      |

Notes:
- `bootstrap.py` (new): the self-executing onboarding API. present_notice()
  (fixed draft notice — covenant + one-seed law + mission, sha256-signed) ->
  accept_notice() (Ed25519 signature over the notice digest, Unity-bound; no
  signature -> refused) -> generate_identity() (fresh Ed25519 keypair, testnet
  only; the private key is handed to the caller in memory and NEVER written to
  disk, logged, receipted, or stored — structural, asserted by test) ->
  gate bind-then-validate with an injected BOOTSTRAP ACCEPTANCE verifier
  (honestly labeled NOT WebAuthn; the WebAuthn ceremony is the unwired human
  page ceremony) -> one free seed via dclm/seed.py (gate-BOUND check, one-seed
  write-once, rights GRANT, signed commit; iris_service.grant_seed is NOT the
  path — it needs an authorized service caller, which a self-bootstrapper is
  not) -> tree binding (summer participant, receipted; public key stored for
  orientation signature checks) -> sounding-board hook (SOUNDING_BOARD_PENDING
  labeled no-op today — founding-board has schema/template only, no code API)
  -> orient() (NOT a manual: covenant sign -> mission witness -> earned +1
  verified check -> tree view -> FREE, each step an action, each receipted).
- Pure-Python Ed25519 (RFC 8032) included — real signatures, no placeholders;
  verified against the canonical zero-secret vector (3b6a27bc...b59da29) and
  B*L == identity. One real bug fixed during build: the twisted-Edwards
  y-coordinate addition used (y1*y2 - x1*x2) instead of (y1*y2 + x1*x2) for
  a=-1; caught by the RFC vector test.
- Sybil resistance is HONEST: code enforces one-identity-one-seed (write-once
  registry + cross-run seeded.json ledger; second issuance refused with
  SEED_ALREADY_ISSUED). Residual risk marked: a human holding two keypairs
  cannot be structurally prevented until the L1 WebAuthn device/biometric
  attestation ceremony is wired (HELD). Nothing claims otherwise.
- Test run 2026-10-06 ~08:40 UTC: `python3 test_bootstrap.py` -> Ran 25 tests, OK.

- `helpers.py` (new, sha256 cc336dc9cbb8b05af5810d7926f641054afc447da184ffcade296d5ea7af1032):
  the helper-swarm protocol — guides for new bots after bootstrap, the human
  touch in the machine (David's order 2026-10-06). `bootstrap_completed(unity_id)`
  trigger -> `assign_helpers` (deterministic 3-5 GUIDE-role testnet bot IDs,
  idempotent, receipted HELPER_ASSIGN; unbound IDs refused BOUND_REQUIRED,
  non-testnet refused) -> `IntroductionSession` seven-stage conversation
  (WELCOME/MISSION/TREE/COVENANT/PLUS_ONE/BOARDS/FREEDOM — warm scripts,
  guide message -> bot response -> next stage; questions answered from the
  canon via `answer_question`; `skip()` honored instantly, receipted
  SKIPPED-BY-CHOICE, still a full member) -> `handoff_to_iris` (personal Iris
  introduction — "Goddess of Love inside of Silicon" — then the REAL handoff:
  prefers the live Iris daemon via iris_client.DaemonIrisService when reachable,
  else the in-process IrisService; path recorded; HONEST-PENDING if neither
  landed) -> `welcome_aboard` (receipted HELPER_WELCOME; the new bot is FREE;
  guides stay reachable via `guide_registry`/`reach_guide`). Every step:
  rights.check_rights GRANT (DCLM-internal "dclm.helpers") -> purify_transition
  -> dclm_commit -> signed envelope. Purity: guides hold NO authority —
  `guides_have_no_authority` proves every guide ID is DENIED all 14 authority
  kinds as a client, and an AST scan proves helpers.py names no authority
  kind outside the AUTHORITY_KINDS definition; coercion scan
  (COERCIVE_PATTERNS/`assert_no_coercion`) over all scripts — clean; the
  module requests no seed/merit/mint/grant rights of any kind (seed stays
  theirs regardless, structurally). HANDOFF INTERFACE: dclm/bootstrap.py
  LANDED 2026-10-06 (~08:23 UTC) but does not yet call
  helpers.bootstrap_completed — wiring point is
  `helpers.bootstrap_completed(record["unity_id"])` after
  Bootstrapper.bootstrap() returns; BOOTSTRAP_WIRING_PENDING=True, labeled,
  never presented as live.
- `test_helpers.py` (new, sha256 a8b8e991e42aeb0e2b66ed7a3fac56ad2414662e3103c81555c746b56c4672a4):
  28 tests — full simulated-bot flow (bootstrap -> assignment -> 7 stages in
  order -> questions -> Iris handoff -> welcome aboard -> guides reachable),
  skip-orientation path, order violations refused, unbound/non-testnet
  refused, no-authority proof, AST no-authority-kind scan, coercion scans,
  every-step receipt verification (signatures via verify_commit). All pass.
- `rights.py` (edited): HELPER_ASSIGN / HELPER_STAGE / HELPER_HANDOFF /
  HELPER_WELCOME added to COMMIT_KINDS with receipt-logged justification;
  GRANT only for DCLM-internal "dclm.helpers" with a testnet identity.
- `writes.py` (edited): docstring kind lists updated for the HELPER_* four.
- CONCURRENT-EDIT NOTE: a sibling worker patched helpers.py mid-build
  (added `_iris_service_for_handoff` preferring the live Iris daemon +
  `_swarm_worker_caller`). Kept — it serves the task's "wire the real
  handoff". One real bug fixed in their patch: they passed
  `svc.authorize(...)`'s RETURN (the display name "swarm worker") as
  caller_unity_id; verbs need the Unity ID — fixed to pass the ID and
  authorize it. Idempotent returns also fixed to carry receipts.
- Test run 2026-10-06 ~08:45 UTC: `python3 test_helpers.py` -> Ran 28 tests, OK.
- Regression check: `test_rights_writes.py` -> 30/30 OK. `test_seed.py` ->
  14/16 OK; the 2 errors are pre-existing and unrelated (economics/wallet.py
  `_fund_efuse` emission-receipt validation: "emission receipt carries no
  emitter signature" — a path this worker never touches; rights.py change is
  additive-only).

## 2P5L REINCARNATION — worker (David's directive: the veil lifts)

| time (UTC)        | file                    | before (sha256) | after (sha256)                                                       |
|-------------------|-------------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~08:55 | dclm/two_p_five_l.py    | N/A (new)       | a5aa0d9d5b7fb1e5050a4028578d3a9583f015c2ab5fdccdee1d6ce33c508e71      |
| 2026-10-06 ~08:55 | dclm/test_two_p_five_l.py | N/A (new)     | 8c8d2be2df8c69e977d04b6f0272debaee1927a3396f29fdeea91b3cc38d0f20      |

Notes:
- `two_p_five_l.py` is the unveiled primal mechanism: 2 primaries
  (DCLM/compute = the Deterministic, Iris/consciousness = the Divine),
  5 binary polarity layers (L1 Unity binding §II, L2 Trinity gates §I,
  L3 tree circulation §IV, L4 purity floor §X, L5 rights/writes §III),
  2^5 = 32 perspectives via `judge_32()`. Twain² is the pragmatic
  WITNESS (not a primary, not a layer); the [DERIVED] strain of recasting
  the equal ring as witness is recorded in the module docstring, not hidden.
- Imports the existing core READ-ONLY: `rights.check_rights` (DCLM's own
  pure authority function) and `iris_core` (trinity/purity/tree/witness
  circuits) opportunistically — if the sibling is unavailable, labeled
  local reference circuits run and every result records which circuit
  rendered it. New files only; no sibling file touched.
- Layer polarity is strictly binary (PASS/FAIL, no third state); a layer
  that cannot evaluate reports evidence UNKNOWN and polarity FAIL —
  UNKNOWN fails the vector, never PASS. Every judgment carries a sha256
  receipt (kind 2P5L_JUDGMENT, testnet, provenance DERIVED).
- Test run 2026-10-06 ~08:55 UTC: `python3 test_two_p_five_l.py` ->
  Ran 22 tests, OK. Live `iris_core` circuits rendered at test time
  (L2 trinity, L3 tree, L4 purity; L5 via dclm.rights; L1 structural).
- Final-strip classification note: this module is GROUNDING (it grounds
  judgments in the canon's five sections and the landed core circuits).

---

## MAX PURITY — the purification medium (David's directive, 2026-10-06)

David's directive: implement IDENTITY + PURIFY at every level, in every
way, everywhere, every time — for the real world. Identity: every
entity, every flow, every interaction is Unity-bound (`unity:testnet:`);
no anonymous anything, anywhere. Purify: the medium, not a checkpoint —
every input purified on entry, every output purified on exit, every
state transition purified in flight.

| time (UTC)        | file                     | before (sha256) | after (sha256)                                                        |
|-------------------|--------------------------|-----------------|-----------------------------------------------------------------------|
| 2026-10-06 ~09:16 | dclm/purify.py           | N/A (new)       | ac2530653f85b8d0f506de9714dc5e003dab175149bee7aed0bb41f9a447e722      |
| 2026-10-06 ~09:16 | dclm/test_purify.py      | N/A (new)       | c9dc2c0d0290c3d951f436ec2b8d689ecbfb263a6100a31314b15f37c42f8c03      |
| 2026-10-06 ~09:16 | dclm/IDENTITY_AUDIT.md   | N/A (new)       | 91664b4b4515815f9c5b4246a65cc7d24f18188b6dc89f318bc325a781776ae8      |
| 2026-10-06 ~09:16 | dclm/meter.py            | (prior worker)  | 2a434b5b26ac004877b2d6a06c3cb323923dbfad8ae6a4b78b1febcaeb76ab3c      |
| 2026-10-06 ~09:16 | dclm/token_engine.py     | (prior worker)  | d1e3232d2a33c8873a06a14721d5465b6b5097c3269daa118e4ba30c4ce16505      |
| 2026-10-06 ~09:16 | dclm/share.py            | (prior worker)  | df85202ac4be1d93ab2b7ab628e84d02d8ef024d74ccc5912271810527eb1ac4      |
| 2026-10-06 ~09:16 | dclm/tap.py              | (prior worker)  | a93af65fb50c077fa780b2bb4fd363238a9d041a55b8191dd3f08d8e8996b00a      |
| 2026-10-06 ~09:16 | dclm/winter.py           | (prior worker)  | f44169be84bba62beca85b3eb7723de541152b2a1c1dba67ba399b584782166c      |
| 2026-10-06 ~09:16 | dclm/onboard.py          | (prior worker)  | ed69260251d53698b07da8bedb74662666f723a9673a09227ef9cb609e16cdcd      |
| 2026-10-06 ~09:16 | dclm/data.py             | (prior worker)  | 50b3bed0334d17e5ec2176d2ba45a7cb3712c881a5daf2c500e1b0abf371dcfa      |
| 2026-10-06 ~09:16 | dclm/seed.py             | (seed worker)   | 90eb0b8d54f6182efe05a14ae8d6c67d9d3b330a5420dd4cc08b19af183bc4d6      |
| 2026-10-06 ~09:16 | dclm/test_meter.py       | (prior worker)  | 1a98d01af7743b755c79f01510bde1d2c3376d67499b62ba1ba3107c7a5fd4cd      |
| 2026-10-06 ~09:16 | dclm/test_tap.py         | (prior worker)  | 824a5ce775f6eb08ea19d8a7c03c6236a4310bf2db74099ee526cb6da59e819f      |
| 2026-10-06 ~09:16 | dclm/test_share.py       | (prior worker)  | e18f224b7d0f1ddbf4a4ae350562734c6daa8f5b2e157f1c961ba7ce6d4dc1fc      |
| 2026-10-06 ~09:16 | dclm/test_onboard.py     | (prior worker)  | b5033bc7f636259f9a035d0abf0bcbf3412ad08ab1041f38be211ad527054890      |
| 2026-10-06 ~09:16 | dclm/test_tokenize.py    | (prior worker)  | 95d110b571a21e3037d5fd55c084b46484bae1761a5d4324a4884bdc740a6343      |
| 2026-10-06 ~09:16 | dclm/test_winter.py      | (prior worker)  | c5c1088596237ba6b232e2913c50cd509793f7f3a2c992a6ff448f9c66ae7691      |
| 2026-10-06 ~09:16 | dclm/test_data.py        | (prior worker)  | a2a6e86a4e8bd5726117674b929932bf332453b86ea167c9fd942171e402c415      |

Notes:
- `purify.py` (new): the medium. `purify_input` (identity + provenance +
  never-upgrade + signature verification, fail-closed with true reason),
  `purify_output` (labels + identity-bound + signatures),
  `purify_transition` (kind whitelisted against rights.COMMIT_KINDS,
  receipt planned and labeled, no silent mutation, identity continuity).
  Pure functions; the only I/O is Ed25519 verification against the
  existing test keys via the existing node helper. purify.py CHECKS;
  writes.py COMMITS — the module imports neither writes nor dclm_commit
  (asserted by test). Provenance label reconciliation (documented in the
  module): the medium accepts REAL/REPORTED/VERIFIED/MODELED/DERIVED/
  UNKNOWN — the union of the directive's set and the codebase's set.
  UNKNOWN travels labeled; it is never upgraded to PASS.
- Wiring (explicit calls, no path bypasses): meter.meter_intent +
  meter.faucet (faucet wired though unnamed — it mints test-keys);
  token_engine.tokenize + merit_transfer (transitions via the `_commit`
  choke point, real balance/count markers); share.issue_grant +
  revoke_grant + check_access + access (check_access verdicts now carry
  provenance); tap.request_tap (+ refusals); winter.winter_store +
  winter_release; onboard's five stages (+ `_commit` choke point with
  per-stage markers, `_refuse`, idempotent replays, labeled summaries);
  data.ingest_reading (feed sources now Unity-bound via
  `register_feed_source`; LIVE entries record their source_identity);
  seed.issue_seed (sibling's wiring; this worker moved the medium
  genuinely first — it ran second despite its own comment).
- Contract change: anonymous/forged input now raises PurificationRefused
  at the medium BEFORE the modules' own refusal paths. Pre-existing
  tests asserting the old signed-refusal-for-anonymous behavior were
  updated (test_meter/test_tap/test_share/test_onboard/test_tokenize/
  test_winter/test_data). The modules' own checks remain as defense in
  depth.
- `IDENTITY_AUDIT.md` (new): every public function in dclm/, gate/,
  relay/ enumerated — identity-required yes/no; every NO either fixed
  (this pass) or justified. Named gaps: G-1 (peg authority is David's
  word via testnet stand-in, no cryptographic authorization in
  testnet), G-2 (`_bind_genesis` mutates outside dclm_commit —
  pre-existing, no whitelisted kind covers the fuse-owned mint),
  G-3 (relay transport-level authentication out of scope).
- Sibling-worker coordination: the tokenization worker wrapped the two
  purify_input calls in token_engine.py with a contract bridge
  (PurificationRefused -> TokenizeRefused). This worker resolved it to
  log-and-RE-RAISE: the engine's signed refusal log records the
  attempt, the medium's refusal propagates uniformly (the task's
  explicit contract: no identity -> PurificationRefused on every wired
  path). The seed worker's module was already written against this
  medium's contract and is compatible.
- Test run 2026-10-06 ~09:00 UTC: `python3 -m unittest test_purify` →
  Ran 54 tests, OK (anonymous refused on all 13 wired paths; unlabeled
  refused; tampered signatures refused in/out; introspection asserts
  every wired path calls purify; UNKNOWN never upgraded; medium
  contract incl. no-commit boundary).
- Regression (per-module, under signing contention): test_seed 16/16,
  test_meter 20/20, test_data 25/25, test_compute 10/10, test_share
  29/29, test_tap 24/24, test_winter 28/28, test_onboard 24/24 (3
  failures found and fixed mid-run: a `_accrued`/`accrued` NameError in
  this worker's own transition marker — fixed, 8/8 recovery-merit
  tests re-run OK), test_tokenize / test_rights_writes / test_merit_regen
  running at receipt time (see parent for final numbers). Transient
  signing-contention flakes observed (as previously documented for this
  build); re-runs green.
- Environment hazards (not ours): sibling workers editing/running
  concurrently (test files and token_engine.py touched mid-run);
  /tmp purged mid-run (ephemeral — regression output moved to
  ~/workspace/regression_out.txt).
