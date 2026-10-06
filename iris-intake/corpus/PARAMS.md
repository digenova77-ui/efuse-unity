# Tokenomics Parameters — the decided-vs-held split

**Nothing ambiguous.** Every parameter in the tokenomics engine is tagged
`DECIDED` or `HELD_FOR_DAVID`, in code (`tokenomics.PARAMS`) and here.
Setting a held parameter before David's word would be decree before evidence —
so the engine **refuses** (`HeldParameterError`) instead of inventing a digit.

Source design: `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md`
(DESIGN, predicted not sealed — `ED-PREDICT-20261004-TOKENOMICS-V1`).
The eFuse hard gate stands: no minting, no distribution, no promises until
full repeated evidence.

---

## DECIDED — law, in the code

| Parameter | Value | Standing | Code ref |
|---|---|---|---|
| Lifetime emission cap | 100,000,000 eFuse | `ED-DECIDED-20261004-5050-V1` | `LIFETIME_CAP`, `PARAMS["lifetime_cap"]` |
| 50/50 split | 50M human / 50M machine, one merged rail | `ED-DECIDED-20261004-5050-V1` | `HUMAN_POOL_CAP`, `MACHINE_POOL_CAP`, `POOLS` |
| No pre-funding | Coins exist only against gated receipts; no receipts → zero emission | ratified Q4 | `Ledger.emitted` starts at 0; `emission_calculator` returns 0 on no verified merit |
| No pool-to-pool | No flow between pools — absence of machinery | ratified | **no such function exists** (tested) |
| Mesh never mints | Mesh routes, never mints; no third emission authority | ratified §3.6 | `Ledger.mesh_route` (`emission_authority: 0.0`); **no `mesh_mint` exists** (tested) |
| Merit TRANSFERABLE | Sold, gifted, transferred between Unity IDs — all receipted. Ownership moves; origin/earned-history frozen at accrual, never moves with the token; standing keys off origin, not balance. A buyer gains economic value and ZERO standing. Transfers are not interest. | **LAW, 2026-10-06 ~3:35 AM EDT** — David's word; supersedes the earlier non-transferable law (DECISIONS.md §13) | `Merit.transferable = True` → direct class transfer refuses with a TokenomicsError naming the canonical receipted path (`dclm/token_engine.py::Tokenizer.merit_transfer`, sole legal path; `wallet.transfer_merit` delegates; `Ledger.transfer_merit` for this module's owned-balance ledger) |
| Honor never converts | Donations → Honor, never Merit; no fiat→eFuse path | §7 | `Honor.redeem_for_emission` → `HonorConversionRefused`; **no fiat→eFuse function exists** (tested) |
| Unity binding | Every movement binds a `unity_id`; no anonymous flows | LAW §8 | required arg + runtime check on every movement fn (tested) |
| Merit interest refused | Merit never earns merit; grows only via gated receipts | §6 cut | **no interest machinery exists** (tested) |

---

## HELD_FOR_DAVID — his digits / his word, never invented here

| Parameter | What it would decide | Status in code | Note |
|---|---|---|---|
| `peg_ratio_E` | Energy units per eFuse (1 eFuse ≡ E) | `HeldParameter`; `emission_calculator` **refuses** without it | Most load-bearing digit: nothing emits without it |
| `merit_decay_rate` | Per-epoch merit decay rate | `HeldParameter`; `apply_decay` **refuses** without an explicit rate | Principle is law (fidelity is current); the digit is his |
| `epoch_length` | Epoch length | `HeldParameter` (registry only) | Direction: conservative = short |
| `reserve_holdback_fraction` | Peg Regulation Reserve holdback per epoch | `HeldParameter`; absorb/release machinery built and gated — per-pool, receipted (kind `reserve`), `HeldParameterError` until decided | Machinery refuses until David's digit; testnet what-if runs on an explicit `MODELED` fraction |
| `tier_weights` | friend / good friend / family / verified kin weights | `HeldParameter` (registry only) | Verified depth only; self-claimed depth earns zero |
| `bridge_premium_band` | Fixed premium band for bridge merit | `HeldParameter` (registry only) | Fixed-band, never a percentage — bridge skims refused |
| `corroboration_thresholds` | Corroboration thresholds | `HeldParameter` (registry only) | Direction: conservative = high |
| `bounty_band_floors_widths` | Receipt-anchored bounty band floors/widths | `HeldParameter` (registry only) | Direction: conservative = narrow bands, firm floors |
| `ring_depth_factor` | Ring-depth merit amplification | `HeldParameter` (registry only) | Verified depth only |
| `bridge_eligibility_threshold` | Zone M entry threshold | `HeldParameter` (registry only) | The mesh is premium work and premium-watched |
| `machine_proof_of_energy_params` | Machine proof-of-energy receipt class | `HeldParameter` (registry only) | Candidate receipt class |
| `honor_class_names` | Honor class names and tiers | `HeldParameter`; `HonorCredit.class_name` = None until decided | Naming is his word as much as digits |
| `merit_definition` | Merit's precise definition ("protocol-fidelity") | `HeldParameter` (registry only) | Mechanics are definition-agnostic by construction (§6) |

**Testnet what-if rule:** a caller may pass an explicitly labeled `MODELED`
figure (e.g. a modeled peg) to run the machinery on testnet. Outputs are then
labeled `MODELED`, never `VERIFIED`/`DERIVED`. A model is not a decree —
but it is never presented as decided.

---

## Purity strip (no unsigned claims)

- Every economic figure is a `Figure(value, provenance)` — `REPORTED` /
  `VERIFIED` / `MODELED` / `DERIVED` / `UNKNOWN` (same register as
  `dclm/compute.py`; the sets are asserted identical in the test suite).
- A bare number passed into the engine is treated as **UNKNOWN** — and
  UNKNOWN never pays, never scores, never emits.
- UNKNOWN merit is excluded from emission with zero share (listed in
  `EpochEmission.excluded`) — never a pass.
- Token class metadata is labeled `MODELED`: the classes implement a DESIGN
  doc, predicted not sealed.
