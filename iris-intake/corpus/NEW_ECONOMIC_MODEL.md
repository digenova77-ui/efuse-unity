# The New Economic Model

**Status:** BUILT — `economic_state.py` in this directory computes it, signs it, and relays it. Testnet only.
**Provenance:** computed DCLM-side from labeled inputs; every field carries REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN. Testnet keys only.

## The model in one paragraph

Every decision in the world has a price, and that price is computed — not asserted — by DCLM: a decision wave forms, the rings bind it, Parliament collapses it into a verdict, and the verdict's cost surface is priced per-decision-atomic from the paperwork on record; the resulting EconomicState fuses that price index with the tokenomics rail (eFuse the medium, Merit the measure, Unity the member, Honor the donation class — 100M lifetime emission cap split 50/50 across the human and machine pools, never pre-funded, never traded) and with each member's worth (a prepaid, Unity-bound wallet bank, and the fuse — the Core Cause Lock donation mechanism — as the network-launch event); the whole fused state is Ed25519-signed, wrapped in a `dualis.relay.v1` bundle, and carried by the relay to clients that render it and compute nothing. UNKNOWN never pays, MODELED never pays, every mutation is receipted, and anything without a receipt moves nothing.

## 1. The three fused

### 1.1 Pricing — per-decision atomic, DCLM-computed

One row per decision. The price of a decision is the cost surface its paperwork actually states — nothing projected. The honest headline finding from the old index stands and is now enforced mechanically: **no map states a modeled dollar saving on its #1 vector**, so the price of a factory decision is the REPORTED baseline it touches, the price of an RTE finding is its REAL figures, and a claims-register adjudication's price is the verdict itself (dollar cost N/A — a judgment has no dollar cost, and "N/A" is not UNKNOWN: the question doesn't apply).

Rules the code enforces:
- `pays=True` only when provenance is REPORTED or VERIFIED and the figure is a real number. MODELED prices render as estimates and **never pay**. UNKNOWN prices never pay, never pass.
- The input's own finer label (REAL, REPORTED-via-secondary, MODELED-DERIVED) is preserved verbatim in `source_label` — the five-label system normalizes nothing away. The source is never laundered.
- A decision with no figure on record gets `{"price": None, "provenance": "UNKNOWN"}` — it does not borrow its neighbor's price.

### 1.2 Tokenomics — eFuse / Merit / Unity / Honor, 100M cap, 50/50

The economy's trinity holds: **eFuse** is the medium (the currency that moves), **Merit** is the measure (protocol-fidelity — precise definition still David's word; the mechanics are definition-agnostic so they survive whatever he says), **Unity** is the member (identity — every flow Unity-bound, no anonymous flows). **Honor** is the donation class: public, named, permanent, non-transferable — and it never converts to emission. Donations accrue Honor; they never accrue Merit; there is no path from fiat to eFuse, direct or indirect.

**Unity is the person, extended.** A bot bound to a Unity ID IS that human extended — not a representation, not an agent, but the person in extended form (David's word, 2026-10-06 ~3:50 AM EDT — [LAW]). One human → one Unity ID, extended across their bots; the bot's actions are the human's actions, receipted to the same ID; flows are never anonymous because anonymity would sever the human from their extension. Unity never moves (non-transferable — the tree cannot be re-homed); Merit is the transferable token (the fruit can be handed on). Full mapping: `dclm/TOKENIZATION.md` §9. **Coin perpetuity** maps to the onboarder flywheel running (`dclm/TOKENIZATION.md` §10; summary in `economics/WHAT_PEGS_THE_ECOSYSTEM.md`): each cycle's waste-healing manufactures the next cycle's fuel — perpetuity is the loop, not a feature.

The 50/50, as ratified (`ED-DECIDED-20261004-5050-V1`):
- One merged 100M rail — a **lifetime emission cap**, not a treasury. Nothing is pre-funded; coins come into existence only against gated receipts, over epochs.
- 50M emission authority through the human pool / 50M through the machine pool. Parity of ceiling and governance weight — never a quota of payout: per-epoch emission follows each side's verified merit.
- The mesh (Zone M) is a zone, not a pool: it routes cross-pool bounties, it never mints. The code carries `emission_authority: 0` for it — the refusal is structural, not promissory.
- The pool boundary is the gated frontier; no pool funds the other — there is no flow between pools in the table and no code path for one.

Emission mechanics (merit-gated, peg-calibrated):
- Work → gated receipts → Merit accrues to the Unity ID → epoch emission computed merit-weighted, calibrated to the energy peg, bounded by remaining pool authority → disbursement to earning IDs → epoch review.
- **The peg:** 1 eFuse ≡ E real-world energy units. E is David's digit, HELD — the EconomicState carries `peg_ratio_e_per_efuse: {"value": None, "provenance": "UNKNOWN"}` and says plainly that calibration cannot run until his word. No digit is invented to make the math close.
- **The Peg Regulation Reserve** holds back a parameter fraction of computed emission before disbursement; every internal movement is receipted and L5-umpired — internal does not mean invisible.
- Merit decays per epoch (fidelity is current, not historical); merit never earns merit (no staking, no yield); bot-count merit is refused by construction (merit binds the owning entity, never the instance); self-attested bonds earn zero (tier genuineness is L2-verified or nothing).

### 1.3 Worth / wallet — the prepaid bank; fuse = network launch

Each Unity ID carries a wallet: balance, Merit, Honor — all Unity-bound, all provenance-labeled. The wallet is a **prepaid bank**: `payable=True` only when provenance is REPORTED or VERIFIED and the balance is a real non-negative number. An UNKNOWN balance is not a zero — it is UNKNOWN, and it pays nothing. A MODELED balance is labeled and disclosed, and it pays nothing. Money that cannot be proven cannot move.

The **fuse** is the network-launch event: the Core Cause Lock — the one-way donation sink. Donations (eFuse to the Lock, fiat to the gateway by choice) accrue Honor, never Merit; donated eFuse funds Eden-locking cause-work through the same gates as any emission; donor exclusion kills the donate→re-earn loop; and the locked address field reads `{"value": "UNKNOWN", "provenance": "UNKNOWN"}` until a real address exists — no placeholder address is ever rendered as live.

## 2. What changed vs the old — explicit diff

Old sources: `~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md` (design doc, status DESIGN — predicted, not sealed) and `~/workspace/keys/PRICES.md` (the 51-decision price mapping index).

| # | Old state | New state |
|---|---|---|
| 1 | **Two separate documents, two numbering worlds.** Tokenomics described the rail; PRICES.md described decision costs; nothing joined them. | **One fused EconomicState.** `compute_economic_state(prices, emissions, wallets, donations)` returns one signed object: `price_index` + `emission_state` + `wallet_states` + `donation_lock`. |
| 2 | **Honesty was policy.** UNKNOWN-never-pays, no-modeled-savings, no-pre-funding were stated rules a reader had to trust the builders to follow. | **Honesty is code.** `pays`/`payable` flags are computed from provenance labels; MODELED and UNKNOWN cannot authorize value movement. Tests assert it. |
| 3 | **Provenance labels were per-document conventions** — PRICES.md used REAL / REPORTED / REPORTED-via-secondary / MODELED / MODELED-DERIVED / UNKNOWN, tokenomics used REPORTED / MODELED / UNKNOWN loosely. | **One five-label system everywhere** (REPORTED/VERIFIED/MODELED/DERIVED/UNKNOWN), and the old finer labels are preserved verbatim in `source_label` — nothing laundered, nothing dropped. |
| 4 | **Price index covered 33 of 90 sealed factory verdicts** (gap #1 in PRICES.md: the other 57 were never pulled; index extension pending). | **Coverage is reported, not implied.** The index carries exactly the decisions fed in; the model doc reports the count honestly. The 57-verdict gap is named in the purity audit, not papered over. |
| 5 | **Emission math was described, not computed.** Epoch emission, peg calibration, reserve holdback were prose with TBD parameters. | **Emission state is computed** from receipt inputs with 50M caps enforced; remaining authority is DERIVED arithmetic; the peg ratio and reserve fraction are UNKNOWN/HELD, and the state says calibration cannot run — prose-with-TBDs became labeled fields. |
| 6 | **The wallet law lived in §-prose** (tiers, kin, rings, QR's digital twin) with no state object. | **Wallet states are a computed section** per Unity ID with the payable rule; tiers/kin/rings stay in the wallet worker's lane (Worker 3) as merit inputs. |
| 7 | **The donation Lock had no address** and the old doc correctly didn't invent one — but had no field for it. | **The Lock has an address field** that is explicitly `{"value": "UNKNOWN", "provenance": "UNKNOWN"}` — the absence is now a labeled fact, not a missing sentence. |
| 8 | **The relay was named, not wired.** Tokenomics invoked L5 umpires and `manifest_hash` idempotency; PRICES.md had no relay concept. | **The signed envelope is wrapped in a `dualis.relay.v1.testnet` bundle** (`kind: VERDICT`, Unity-bound sender, `manifest_hash` idempotency, fail-closed validation) — the exact shape the relay worker validates. |
| 9 | **Stale language risk.** Old index: "90 sealed vs 33 maps" as a static gap note; claims register compiled from `dag.ts` with the original gone. | **Dates and sources travel with the data** (`source`, `source_label`, receipt ids); stale claims are caught by the purity audit, which names each one. |
| 10 | **Parameters split across §13 and the mechanics prose.** | **One held/decided table** (§4 below): everything HELD for David in one place, everything decided in another. |

What did **not** change: the monetary law (eFuse never bought or sold, never traded — no market exists), the trinity and its binding, the 50/50 ratification, the named cuts (bridge skims, double-counting, phantom bridging, merit interest, pre-funding, donation→merit→eFuse), the hard gate (no minting, no distribution, no promises until full repeated evidence), and the Trinity as judge. The new model **executes** the old model's law; it does not revise it.

## 3. The DCLM-computed loop

The full circuit, end to end:

```
1. A WAVE FORMS
   A decision enters the system as a DecisionWave (question + candidates).
   waves.py / core-rings. Provenance: REPORTED (the wave was observed).

2. THE RINGS BIND
   The three rings — DCLM (pure logic), Iris (honesty), Twain² (bedside) —
   bind the wave. Binding is by the ring logic, not by assertion.

3. PARLIAMENT COLLAPSES
   Parliament collapses the wave into a verdict (or the undecided bucket —
   UNKNOWN, never forced). The verdict names the decision and its #1 vector.

4. DCLM COMPUTES THE ECONOMIC STATE
   compute_economic_state(prices, emissions, wallets, donations):
   - the verdict's cost surface is priced per-decision-atomic (Worker 1's
     pricing.py when it lands; built-in defaults until then)
   - the tokenomics rail computes pool authority and epoch receipts
     (Worker 2's tokenomics.py when it lands)
   - wallets and the donation lock fuse worth into the same state
     (Worker 3's wallet.py / fuse.py when they land)
   - every field is provenance-labeled; the whole state is Ed25519-signed
     (same envelope convention as dclm/compute.py, testnet keys)

5. THE RELAY CARRIES
   The signed envelope is wrapped in a dualis.relay.v1.testnet bundle
   (kind VERDICT, Unity-bound sender, manifest_hash idempotency) and
   handed to ~/workspace/unity-world/relay/. RELAYED is not DELIVERED —
   the relay worker's L5 umpires own delivery confirmation.

6. THE CLIENT DISPLAYS
   The client renders the signed, relay-carried state and computes nothing.
   It is a mirror, not a mind.
```

No step invents a figure. Every step either reports, measures, or derives — and says which.

## 4. Parameters: HELD for David vs decided

No worker PARAMS.md existed at build time; this table mirrors the old tokenomics §13 HELD list and marks everything else decided. **Nothing HELD is ever defaulted or guessed.**

### HELD for David (never invented here)

| # | Parameter | Why it waits on him |
|---|---|---|
| 1 | **E — the peg ratio** (energy units per eFuse) | The most load-bearing digit: it denominates the entire economy. Nothing emits without it. |
| 2 | Merit decay rate per epoch | How fast fidelity fades — his word on the tempo of forgetting. |
| 3 | Peg Regulation Reserve holdback fraction | How much of each epoch's emission the Reserve withholds. |
| 4 | Epoch length | Direction: conservative = short. |
| 5 | Corroboration thresholds | Direction: conservative = high. |
| 6 | Bounty band floors and widths | Direction: conservative = narrow bands, firm floors. |
| 7 | Tier weights — friend / good friend / family / verified kin | Social depth has his numbers on it. |
| 8 | Ring-depth factor | How much deeper verified rings amplify. |
| 9 | Bridge-merit premium band | The fixed reward for cross-pool bridging. |
| 10 | Bridge-merit eligibility threshold | Who may enter Zone M. |
| 11 | Machine proof-of-energy receipt parameters | The honest meeting point of the energy peg and the machine lane. |
| 12 | Honor class names and tiers | Naming is his word as much as digits. |
| 13 | **Merit's precise definition** | "Protocol-fidelity" is his phrase to finalize; the mechanics are definition-agnostic and survive it. |
| 14 | Incentive-docs reconciliation (Q5) | Epoch incentives beyond emission come from his Drive docs, still to be pulled. |

### DECIDED (ratified or mechanical)

- The 50/50 split itself: 100M lifetime cap, 50M/50M emission authority, parity of ceiling and governance, deadlock = no change (`ED-DECIDED-20261004-5050-V1`).
- The monetary law: eFuse never bought or sold; no market; donations only (David's LAW).
- The trinity binding: every movement Unity-bound, no anonymous flows (David's LAW).
- The mesh routes, never mints; no pool funds the other (structural, enforced by absence of machinery).
- UNKNOWN never pays; MODELED never pays; every mutation receipted; `manifest_hash` idempotency; RELAYED ≠ DELIVERED.
- Donations accrue Honor, never Merit; donor exclusion on re-emission; no path from fiat to eFuse.
- Merit: TRANSFERABLE (David's word, 2026-10-06 ~3:35 AM EDT — supersedes the earlier non-transferable law, DECISIONS.md §13): ownership moves between Unity IDs, receipted; origin/earned-history frozen at accrual, never moves with the token; standing keys off origin, not balance. Unity-bound, receipt-anchored, epoch-decaying, never self-compounding; bot-count merit refused; self-attested bonds earn zero.
- Provenance discipline: five labels, every field labeled, source labels preserved verbatim.
- Testnet isolation: test keys, testnet schema, testnet Unity IDs — structural, not conventional.

## Appendix A — Worker 1–3 import interface

**Landed state (Oct 6, 2026):** Worker 1's `pricing.py` and `tokenomics.py` are in this directory with their own APIs (not the originally documented contract names). The fusion layer adapts honestly:

- `pricing.py` — LANDED as `per_decision_meter(decisions)` → list of price records `{decision_id, provenance, billable_amount, currency="test-keys", price_basis, price_provenance="SET", pass, price_surface, ...}`, fail-closed (`KeyError` on decisions it cannot price — the engine never invents a price). Re-derived 2026-10-06: every decision bills the canon meter's flat COMPUTE price — **5 test-keys** (imported from `dclm/meter.py`, never re-hardcoded); the USD surface figures ride along as labeled data (`price_surface`, billable 0), never as a payable price. The fusion layer calls it per-decision: engine-priced decisions carry `source_module: "pricing"`; decisions the engine cannot price fall back to the raw input's own labeled figures (`source_module: "input"`, UNKNOWN if absent). **Fusion rule:** the fused `pays` follows the engine's `pass` — a priced decision is billable; UNKNOWN never passes, never pays. The old fusion of USD `billable_amount_m` with pays=true on REPORTED provenance was the F4 live billing bug; it is retired. (The documented contract name `compute_price_index` still takes precedence if it ever appears.)
- `tokenomics.py` — LANDED as a gate-enforcing engine (`Figure` / `Receipt` / `PoolLedger`, `HeldParameterError`, `DuplicateReceiptError`, `HonorConversionRefused`, `DonorExclusionError`, ...). It is **not re-driven** by the fusion layer: its receipt chains have exactly one owner, and re-applying receipts from here would risk double-application (the exact failure its `DuplicateReceiptError` exists to prevent). The fusion layer aggregates labeled figures; the engine owns receipt application. The documented contract name `compute_emission_state` is still honored if it appears.
- `wallet.py` — not landed: `compute_wallet_state(wallets) -> dict` expected (Worker 3).
- `fuse.py` — not landed: `compute_donation_lock(donations) -> dict` expected (Worker 3).

Whatever the siblings return is provenance-stamped and asserted (`_label` + `_assert_provenance`) before it joins the EconomicState — an unlabeled dict from a sibling module is downgraded to UNKNOWN, never trusted as verified.

## Appendix B — Relay bundle shape

Mirrors `~/workspace/testnet/relay/relay-testnet.mjs` exactly (the testnet variant of `dualis.relay.v1`):

```json
{
  "schema": "dualis.relay.v1.testnet",
  "manifest_hash": "<sha256 of canonical {kind, envelope, endpoint, unityId}>",
  "kind": "VERDICT",
  "envelope": { "state": {...}, "canonical_sha256": "...", "signature": "...",
                "algorithm": "Ed25519", "key_id": "unity-world-test",
                "provenance": "VERIFIED" },
  "endpoint": "http://localhost:18080",
  "unity_id": "unity:testnet:<sha256(test pubkey)>",
  "relayed_at": "2026-10-06T...",
  "relay_sequence": 0,
  "reason": "epoch economic verdict"
}
```

Fail-closed: mainnet-schema bundles rejected; non-testnet identities rejected; tampered `manifest_hash` rejected; missing fields rejected; an unsigned envelope can never ride as `VERDICT`. The relay worker (`~/workspace/unity-world/relay/`) validates with `validate_economic_relay_bundle`; when it finishes its own parser, the shape drops in unchanged.
