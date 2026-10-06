# RECEIPTS — tokenomics engine (worker 2 of the unified WORLD build)

Testnet only. Nothing touches production keys or paths.
No eFuse implementation exists; the eFuse hard gate stands.

Mutation log: every file here was created new (no prior content, so
before-sha256 is N/A — the file did not exist).

| time (UTC)        | file                  | before (sha256) | after (sha256)                                                        |
|-------------------|-----------------------|-----------------|-----------------------------------------------------------------------|
| 2026-10-06 ~07:05 | economics/tokenomics.py      | N/A (new) | 94124eb2d5b52a82a432e13c3fd4cc644996201012166502607d092092bcd4df |
| 2026-10-06 ~07:05 | economics/test_tokenomics.py | N/A (new) | b20fea3b440aebceb847b5ca6948aec6e2391672483abb66b1eb4da2ea45c3e9 |
| 2026-10-06 ~07:06 | economics/PARAMS.md          | N/A (new) | b7d6dc3a55dbcf26de33cff33b4bd4aef0de61375e8e2e95c9d648bbf1cad2ce |
| 2026-10-06 ~07:06 | economics/DECISIONS.md      | N/A (new) | 11d1a6404d3bb4ac58b33a2065bf5c43c49f3e68b60b6039edecb1b6970ae30c |

Notes:
- Test run 2026-10-06 ~07:05 UTC: `python3 test_tokenomics.py` → Ran 55 tests, OK.
- Provenance register asserted identical to `dclm/compute.py PROVENANCE_LABELS`
  (mirrored, not imported — see DECISIONS.md §9).
- Files edited after creation: DECISIONS.md (edited after its ~07:06 receipt — after-sha256 corrected in the D4 repair below). The wallet.py after-sha256 was a malformed 63-char transcription of the true hash; corrected in place. Hashes above are now final.

---

# RECEIPTS — wallet + fuse (worker 3 of the unified economic model build)

Testnet only. Nothing touches production keys or paths.
Key material never leaves `../keys/` (authorizations signed via
`../dclm/ed25519.js` with key *files*; only canonical bytes cross the
process boundary).

Mutation log: every file below was created new (no prior content, so
before-sha256 is N/A — the file did not exist).

| time (UTC)         | file                  | before (sha256) | after (sha256)                                                        |
|--------------------|-----------------------|-----------------|-----------------------------------------------------------------------|
| 2026-10-06 ~07:10  | economics/wallet.py          | N/A (new) | b35e606103f59943c5a0180737674718ddcf8db898c13d0734ad2ba5fd72f6b6 |
| 2026-10-06 ~07:10  | economics/fuse.py            | N/A (new) | 33cfaea537e28cc297dfb655cfdafccc7f15d74134c38952cc6c8579a904e75b |
| 2026-10-06 ~07:10  | economics/test_wallet.py     | N/A (new) | 14628cafe921659449a86daf610432c77fba5b46e59f5312540fc15c73f81803 |
| 2026-10-06 ~07:10  | economics/test_fuse.py       | N/A (new) | 9e7f2d2002574c1c62f71c4d29c429bd68250854ff0d973dc450b137ebf3ad27 |

Notes:
- `wallet.py` was rewritten once after creation (share/deduct/donate
  idempotency fix: a caller-supplied manifest is now the idempotency key
  verbatim — no per-call nonce is injected, so retries are true no-ops).
  The after-sha256 above is the final content.
- `fuse.py` `compute_donation_lock` was fixed once after creation:
  `receipt_id` is always the 64-char content hash (contract with
  `economic_state.py` / its test suite); a caller-supplied receipt
  reference is carried separately as `source_receipt`.
- Test runs 2026-10-06 ~07:12 UTC: `python3 test_wallet.py` → Ran 33
  tests, OK. `python3 test_fuse.py` → Ran 19 tests, OK.
  Regression check: `python3 test_economic_state.py` (worker 4's suite) →
  Ran 41 tests, OK. `worker_modules_present()` now reports
  `wallet: True, fuse: True`.

## Refusals / honest markers (what was NOT invented)

- Genesis Unity amount: `GENESIS_UNITY_AMOUNT = None` — HELD for David.
  The fuse cannot trigger without the amount inside his signed
  authorization; no default exists anywhere.
- Tier sharing limits (`TIER_LIMITS`): MODELED conservative defaults —
  tier weights are HELD for David (TOKENOMICS §13.7). The code enforces
  the table; it does not bless the numbers.
- Honor class: `UNNAMED — HELD for David` (TOKENOMICS §13.12).
- Kin mechanism: mutual-signature bond records the principle; deeper
  mechanism flagged `KIN_MECHANISM_TBD` (WALLET_DESIGN_LAW.md §5).
- Core Cause Lock address: `{"value": "UNKNOWN"}` — no address invented.
- Epoch semantics: counters are keyed by a caller-supplied epoch label
  (default: UTC date); epoch length itself is HELD (§13.4).
- Unity transferability: Unity tokens are non-transferable between
  wallets (conservative reading of the §8 binding law). Needs David's
  word to change.

---

## D4 receipt repair — 2026-10-06 ~07:15 UTC (receipt-completeness worker)

Seven economics/ source files were created by the build workers but never
received a receipt row (flagged by the purity index D4: unreceipted files).
First receipt rows below (before = N/A, the files predate the ledger entry).
Also in this repair: wallet.py's malformed 63-char after-hash corrected to
the true 64-char sha256, and DECISIONS.md's stale after-hash recomputed —
both fixed in place above. No measured file was altered; receipts were
recomputed to match the files.

| time (UTC)        | file                               | before (sha256)                      | after (sha256)                                                        |
|-------------------|------------------------------------|--------------------------------------|-----------------------------------------------------------------------|
| 2026-10-06 ~07:15 | economics/NEW_ECONOMIC_MODEL.md    | N/A (new — first receipt, D4 repair) | 83c91a72b44b0d25f5599d8293694fc707956056c9d1639eecef21978a6456f2 |
| 2026-10-06 ~07:15 | economics/PRICES_ADDENDUM.md       | N/A (new — first receipt, D4 repair) | 8133bfa3a08fba5e1edea009f64598126390cac1f649db0e37b39ecd7373b2dc |
| 2026-10-06 ~07:15 | economics/PURITY_AUDIT.md          | N/A (new — first receipt, D4 repair) | fdd966610d473ec22d6a681b288358313fe9b3d69ceba7b4c047a6b9461f099a |
| 2026-10-06 ~07:15 | economics/economic_state.py        | N/A (new — first receipt, D4 repair) | f017c8518d47fd4c5a309ded059940d8b4ba941130fa31074c821e6d1b546a45 |
| 2026-10-06 ~07:15 | economics/pricing.py               | N/A (new — first receipt, D4 repair) | 4baa6fb1914dc4a39e7d2f3b996048a1be2e900208b7bda9c0537965cc528015 |
| 2026-10-06 ~07:15 | economics/test_economic_state.py   | N/A (new — first receipt, D4 repair) | 1efee7d9504e459b71ef258afa4d8bc7cf08b5373d2cd9db7f8ce670cc1fe738 |
| 2026-10-06 ~07:15 | economics/test_pricing.py          | N/A (new — first receipt, D4 repair) | 60a3ebed3ab968fc5961f2baad8d5e96a560ac6208fc5454636de713ebb06833 |

---

## Gauntlet E16 closure — winter throttle wired into emission (Fix Worker A2)

2026-10-06 ~07:52 UTC. `dclm/winter.py::emission_multiplier` is now wired
into `economics/tokenomics.py::emission_calculator` (new optional `winter`
arg: None | WinterSignal | WinterState — the lawful trigger source; a raw
gradient is refused, no second trigger invented). `EpochEmission` carries
`winter_gradient / winter_label / winter_multiplier / winter_reasons /
winter_provenance`, sealed in its canonical hash — every throttled epoch
receipt shows WHY emission was reduced. `Ledger.emission_close` threads
`winter` through. Summer (no/unreadable signal) = multiplier 1.0, exact
no-op; UNKNOWN never PASS. Peg calibration path untouched (refuses before
the winter resolution). winter.py itself unmodified. Testnet only.

| time (UTC)        | file                        | before (sha256)                                                  | after (sha256)                                                        |
|-------------------|-----------------------------|------------------------------------------------------------------|-----------------------------------------------------------------------|
| 2026-10-06 ~07:52 | economics/tokenomics.py     | 94124eb2d5b52a82a432e13c3fd4cc644996201012166502607d092092bcd4df  | b15b0788d5f81fb4d793b7901d537716231a61ace90fd40e4eb4f3e4ab4fe1c2 |
| 2026-10-06 ~07:52 | economics/test_tokenomics.py| b20fea3b440aebceb847b5ca6948aec6e2391672483abb66b1eb4da2ea45c3e9 | 6ebaf5919339ec1a016dc6433408525426285cb56e93fbbf4cf326358ddc2e2c |

Notes:
- "before" = last receipted hash (creation receipts above). The after-hash
  covers this worker's winter wire PLUS two concurrent workers' edits in
  the same files, applied to disjoint regions: Worker A1's Merit-transferable
  stale-law fix, and Worker A3's peg-regulation F7 machinery
  (`reserve_released` on EpochEmission, reserve holdback/release in the
  emission path). A3's F7 edit briefly broke the EpochEmission dataclass
  (default field before non-default `provenance`) — A3 repaired it
  themselves seconds later; the module imports cleanly now. Each worker
  owns its test updates.
- The A2 winter wire survived A3's emission-path rewrite intact:
  `_resolve_winter`, the `winter` parameter, and the winter receipt fields
  are all present and exercised — 76/76 tokenomics tests green at
  ~08:05 UTC, including all 9 TestWinterThrottle tests.
- Test run 2026-10-06 ~07:52 UTC: `python3 test_tokenomics.py` → 64 tests,
  62 pass at that moment. The 2 errors then were the DEAD non-transferable
  Merit law tests (`TestParamsRegistry` on the removed
  `merit_non_transferable` param; `TestTokenClasses.test_merit_non_transferable`
  on the old `Merit.transfer` refusal) — invalidated by A1's concurrent
  edit; A1 has since updated those tests (76/76 green now).
- OUT-OF-LANE FLAG for the parent: `dclm/test_winter.py` has 1 stable error
  (`StoreTests.test_non_testnet_identity_structurally_refused`) caused by
  ANOTHER worker's concurrent edit to `dclm/winter.py` (a new `purify_input`
  gate in `winter_store` raises `PurificationRefused` where the test expects
  the old refusal type). Not A2's lane (A2 was barred from redesigning
  winter.py); the throttle API A2 wires to (`evaluate_trigger`,
  `WinterSignal`, `WinterState`, `emission_multiplier`) is unaffected —
  all 9 winter-throttle tests pass against the edited winter.py.

---

## Price-per-decision re-derivation fix — 2026-10-06 ~08:18 UTC (pricing-code-fix worker)

Per `../PRICE_PER_DECISION_REINVESTIGATION.md`: the old model was dimensionally
wrong (F1: priced the object measured, not the act of deciding; F2: USD instead
of test-keys; F3: a second meter) and carried a live billing bug (F4: the false
USD `billable_amount_m` fused into the SIGNED EconomicState with pays=true —
the mislabeled surface figure would actually authorize payment). Net effect:
decision charges move DOWN — from USD-billion-scale surface figures to a flat
**5 test-keys** per decision (the canon meter's COMPUTE price, SET in
`dclm/meter.py`, canon XIII — imported as `PRICE_COMPUTE`, never re-hardcoded).

The USD surface figures ($637B-style numbers) REMAIN as labeled data
(REPORTED/MODELED/DERIVED per figure, billable 0) — facts, not bills. The 53
decisions' surface data is untouched; only what is billed changed. The
proposed friction-kill rebate (refund 5 test-keys from PLAYGROUND_FUEL on
verified kills) is HELD for David — implemented as the inert
`REBATE_PENDING_DAVID` flag + `friction_kill_rebate()` stub (raises
NotImplementedError), with the plug point named in `price_decision` and in
`economic_state._meter_price_entry` (inert `"rebate": "REBATE_PENDING_DAVID"`
marker on fused entries).

| time (UTC)        | file                                  | before (sha256)                                                  | after (sha256)                                                   |
|-------------------|---------------------------------------|------------------------------------------------------------------|------------------------------------------------------------------|
| 2026-10-06 ~08:18 | economics/pricing.py                  | 4baa6fb1914dc4a39e7d2f3b996048a1be2e900208b7bda9c0537965cc528015  | cc49b7150bc2f2c5ca7e60c2da6591d3f043e45e86c8137e418d4339d1862525 |
| 2026-10-06 ~08:18 | economics/economic_state.py           | f017c8518d47fd4c5a309ded059940d8b4ba941130fa31074c821e6d1b546a45  | ae28ea7a74f4ad30c3a2d9d4d92b7ea1326d46613db1271911619bac02583c91 |
| 2026-10-06 ~08:18 | economics/test_pricing.py             | 60a3ebed3ab968fc5961f2baad8d5e96a560ac6208fc5454636de713ebb06833  | 43f972c99e3efde0462cce6c841dec1a8797777b772383de4022b61818e17dd8 |
| 2026-10-06 ~08:18 | economics/test_economic_state.py      | 1efee7d9504e459b71ef258afa4d8bc7cf08b5373d2cd9db7f8ce670cc1fe738  | 1be753f885584fbc0f1d9774082902bbfaabe3c4c90bddceeea8b44f84a3279f |
| 2026-10-06 ~08:18 | economics/test_pricing_fix.py         | N/A (new — the new-law test suite)                               | 52ef0dad7eaf4eb5a26a0ccef5f6315923e581c94e9be7a2897cdaa1f9238759 |
| 2026-10-06 ~08:18 | economics/NEW_ECONOMIC_MODEL.md       | (narrative; unreceipted prior)                                   | 5b6e18eceece5abf57a31b9b983e793a5803d1857edbf762de0aa97bf1cbcd3a |
| 2026-10-06 ~08:18 | KEY_FUSION_MAP.md                     | (narrative; unreceipted prior)                                   | 1892f3555464a1c86e4f29eda4d88e581da0adaeb349eba7af30009dffaf118b |

Notes:
- "before" = the D4-repair receipted hashes (same values as above); the
  before-hashes were captured immediately prior to this fix's first edit.
- `pricing.py`: `billable_amount_m` (USD) retired; `billable_amount`
  (test-keys, flat 5) introduced; `price_decision` returns
  `{billable_amount, currency: "test-keys", price_basis,
  price_provenance: "SET", price_surface (labeled, billable 0)}`; the
  RTE-HEALTH F8 unit error corrected (cost-per-ED-visit stored as
  `amount_usd: 215.0 / 340.0`, unit "USD/visit", no longer `amount_m`);
  F9 addressed in the module docstring (the "51 decisions" count belongs
  to the source document PRICES.md; the engine index holds 53 rows).
- `economic_state.py`: `_meter_price_entry` no longer fuses any USD value
  — fused entries carry `price: 5, currency: "test-keys",
  pays: <engine pass>`, the labeled `price_surface` separately, and the
  inert rebate marker. The old fusion docstrings (worker-1 interface
  paragraph, `_build_price_index` rule, honesty-laws line) rewritten.
- `NEW_ECONOMIC_MODEL.md` App. A and `KEY_FUSION_MAP.md` §2–3 narrative
  corrected to the new model (doc callers of the old USD billable).
- Test runs 2026-10-06 ~08:18 UTC, all green: `test_pricing_fix.py` → 18
  OK (new law); `test_pricing.py` → 20 OK; `test_economic_state.py` → 41
  OK; `test_tokenomics.py` → 89 OK; `test_wallet.py` → 41 OK;
  `test_fuse.py` → 19 OK; `test_mesh_escrow.py` → 17 OK. Total 245, zero
  failures. Testnet only.
- F4 is closed: a repo-wide sweep finds no `billable_amount_m` or
  `CURRENCY_DEFAULT` outside the reinvestigation's historical record and
  comments describing the retired bug.
