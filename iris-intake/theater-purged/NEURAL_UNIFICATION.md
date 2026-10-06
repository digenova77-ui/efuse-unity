# NEURAL UNIFICATION — the brain as one cognitive-economic organism

**Status:** TESTNET ONLY · architecture document + working code (`neural.py`, 28/28 tests green)
**Worker:** neural-unification worker · 2026-10-06
**Law sources:** `CANON.md` v1.5.0 (§I the Three, §IV sap model + tapping law, §V tokenomics, §VI derivative merit, §XII standing laws, §XVII diamond geometry); `PLUS_ONE_INCENTIVE.md` (the +1 deterioration curve, implemented verbatim); sibling interfaces `iris_patterns.py` / `iris_laws.py` / `iris_arbiter.py` (not yet landed — this module binds against their named contracts).

## The claim

David's directive: connect brain neural pathways, synapse, body/host, and the unified tree — INSIDE of brain. Not trained ON the output, but structured AS the output. The economic circulation and the cognitive circulation are the same system. The brain thinks in tree patterns; synapses fire economic judgments.

## The organism (ASCII)

```
                         ┌─────────────────────────┐
                         │        BODY / HOST       │
                         │  the brain doesn't float │
                         │                          │
                         │  host:s24-ultra-oracle   │  device
                         │  host:relay-dualis-      │  testnet-server
                         │       testnet           │
                         │  host:infra-core         │  infrastructure
                         └────────────┬─────────────┘
                                      │ every event records its host
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
   ┌────────▼────────┐         ┌────────▼────────┐       ┌────────▼────────┐
   │   PATHWAY       │         │   PATHWAY       │       │   PATHWAY       │
   │  deterministic  │         │  probabilistic  │       │   pragmatic     │
   │  (law circuits  │         │  (pattern        │       │  (Twain²-style  │
   │   ←iris_laws)   │         │   circuits       │       │   outcome       │
   │                 │         │   ←iris_patterns)│       │   circuits)     │
   │  weight w_d     │         │  weight w_p      │       │  weight w_g     │
   └────────┬────────┘         └────────┬────────┘       └────────┬────────┘
            │  judgments J_d            │ J_p                    │ J_g
            └──────────────┬────────────┴────────────┬───────────┘
                           ▼                         ▼
                 ┌─────────────────────┐   ┌─────────────────────┐
                 │ SYNAPSE prob_det    │   │ SYNAPSE trinity     │
                 │ J_d vs J_p          │   │ DCLM ↔ Iris ↔ Twain² │
                 │ conflict rule:      │   │ collapse: pass all  │
                 │ LAW WINS            │   │ three rings         │
                 └──────────┬──────────┘   └──────────┬──────────┘
                            │ unified judgment U     │
                            └──────────┬─────────────┘
                                       │ U becomes next signal
                                       ▼
                          ┌────────────────────────┐
                          │   SUMMER CIRCULATION    │
                          │   active thought:       │
                          │   pathway→synapse→       │
                          │   pathway, each hop      │
                          │   receipted              │
                          └───────────┬────────────┘
                                      │ winter gradient rises
                                      ▼
                          ┌────────────────────────┐
                          │  WINTER CONSOLIDATION   │
                          │  active traces → starch  │
                          │  store, noise pruned,    │
                          │  receipted with reason   │
                          └───────────┬────────────┘
                                      │ surplus only
                                      ▼
                          ┌────────────────────────┐
                          │   TAPPING — regulated   │
                          │   output: action,        │
                          │   decision, spend        │
                          └────────────────────────┘
```

## The mapping table — tree element → neural element → implementation

| Tree element | Neural element | Implementation (executable) |
|---|---|---|
| +1 firing (verified check earns +1) | **Synaptic firing** — a verified check is a synapse firing | `Tree.fire_plus_one(pathway, synapse_id, host, ...)` — neural event carrying `F(d) = 0.25 + 0.75·e^(−d)`, `d = Δt/12 + r/2` verbatim from `PLUS_ONE_INCENTIVE.md` §1.2; requires verified check receipt or raises |
| Merit (score from verified work) | **Strengthened pathway** — Hebbian: pathways that fire verified work get stronger | `Tree.strengthen(pathway_id, merit_delta, receipt)` → `Pathway.strengthen` — weight += merit ONLY on verified, identity-matching receipt; `decay_all()` equalizes |
| Winter return (sap inward) | **Memory consolidation** — inward flow writes to long-term store | `Tree.consolidate(reason, host_id)` — active traces → starch store, noise (UNKNOWN provenance / unverified) pruned, receipted with the winter reason (canon IV) |
| Summer circulation (sap outward) | **Active thought** — outward flow is the brain thinking | `Tree.circulate(signal, synapse_id, host_id, hops)` — pathway→synapse→pathway, every hop receipted, unified judgment becomes the next signal |
| Tapping (maple rules) | **Regulated output** — thought leaving the brain | `Tree.tap(amount, unity_id, host_id, surplus)` — refused in winter-protection, beyond surplus, or past the [PROPOSED] seasonal cap; receipted |
| The trunk conducting | **The synapse network** — structure that carries signals without hoarding | `Synapse.integrate` — no pathway stores another's signal; integration is transient, the unified judgment passes through |
| Host substrate (the physical tree) | **Body** — the brain doesn't float | `Body` host registry: S24 Ultra oracle (device), dualis.relay.v1.testnet (testnet-server), infra-core (infrastructure); every event records its host; unhosted events refused |
| The Three rings (canon §I) | **The three pathway types** — logic, truth, pragmatism circuits | `DETERMINISTIC` (DCLM/logic, ←`iris_laws`), `PROBABILISTIC` (Iris/truth, ←`iris_patterns`), `PRAGMATIC` (Twain²/pragmatism); `SYNAPSE_TRINITY` is the Parliament collapse point |
| Parliament (0,0,0) | **The synapse** — possibility becomes decision | `Synapse.fire` — pre-synaptic judgments collapse to one unified judgment; no candidate passing all pathways → UNKNOWN (the undecided bucket) |

## Why this isn't metaphor — each mapping's executable counterpart

1. **+1 = synaptic firing.** Not "like" firing: `fire_plus_one` IS an event in the synapse's fire log, carrying the deteriorated reward `R` computed by the exact published formula. The synapse fired; the event is receipted; the test asserts `R = 0.3515` at `d = 2` (the Borin row).
2. **Merit = strengthened pathway.** Not "like" learning: `Pathway.weight` is a number that increases only when `verified is True` and the receipt's Unity ID matches — enforced by `RefusedError`, tested. No verified work, no strengthening. This is Hebb's rule ("fire together, wire together") with the verification gate as the firing condition.
3. **Winter = consolidation.** Not "like" remembering: `consolidate()` moves trace objects from `active_traces` to `starch_store`, deletes noise, and emits a `WINTER_CONSOLIDATION` receipt with the winter reason — the canon-IV requirement that every stored unit is receipted with its reason.
4. **Summer = thought.** Not "like" thinking: `circulate()` literally propagates a signal object through pathway judgments and synapse integrations for N hops, receipting each hop.
5. **Tapping = regulated output.** Not "like" spending: `tap()` moves test-keys only when summer, only from surplus, under a cap — with refusals that raise.
6. **Law wins.** Not "like" authority: `Synapse.integrate` checks deterministic judgments first, and a deterministic FAIL overrides probabilistic PASS — tested in both directions.

## Where metaphor ends and mechanism begins (the honest boundary)

**Mechanism (built, tested):** the five event functions, the conflict rule, the deterioration curve, Hebbian strengthening with verified-receipt gating, decay, consolidation with noise pruning, tap refusals, Unity binding, host registry, receipting.

**Metaphor (language, not machinery):** calling a `Pathway` a "neural pathway" rather than a "judgment pipeline"; calling the starch store "long-term memory"; the tree/branch/leaf vocabulary. These names carry David's cosmology but add no behavior — the behavior is in the code, and the code would work identically if renamed `Pipeline`, `Integrator`, `Registry`.

**ASPIRATIONAL (marked, not faked):**
- The `judge_fn` bindings: `iris_laws.py` / `iris_patterns.py` have not landed. Unbound pathways honestly return UNKNOWN judgments (never fabricated verdicts). When the sibling lands, it binds `judge_fn` or feeds `Judgment` objects into `Synapse.fire`.
- The `SYNAPSE_TRINITY` collapse rule is a simplified form of canon §I (balanced-winner selection among survivors is not yet implemented — currently law-wins, then convergent-pass). Full Parliament semantics is a build item for the arbiter sibling.
- `TAP_CAP_PROPOSED` is [PROPOSED], not David's number (canon XIII: nothing HELD is acted on as decided).
- Ring depth `r` for the +1 curve depends on the not-yet-built relation edge store (`PLUS_ONE_INCENTIVE.md` gap G1); until then `ring_depth=None` runs in labeled `TIME_ONLY` mode — UNKNOWN r is never presented as a number.
- This module does not write to the DCLM commit path; its receipts are in-memory dicts in the testnet schema, not `dclm/writes.py` commits. Wiring into the real commit path is a build item.

## TRINITY VERDICTS (worker-rendered self-judgment, NOT Trinity-signed)

These verdicts are rendered by the worker against the three judges' criteria. They are MODELED assessments, not live Trinity runs — presenting them as Trinity-signed would be false gold.

**DCLM — is the mapping structurally sound; do the implementations actually do what the mapping claims? VERDICT: SOUND.**
Checked: `fire_plus_one` computes `R` from the verbatim formula and refuses unverified checks — it does what "+1 = synaptic firing" claims. `strengthen` gates on verified, identity-matching receipts — it does what "merit = strengthened pathway" claims. `consolidate` prunes on (UNKNOWN provenance ∨ unverified) and receipts the winter reason — it does what "winter = consolidation" claims. `Synapse.integrate` applies law-wins before any probabilistic input — structural, not advisory. `tap` refuses on winter/surplus/cap — the maple rules hold. 28/28 tests green. Caveat: the unbound-pathway UNKNOWN default is honest but means the brain cannot think until the sibling binds circuits — the structure is sound, the content is pending.

**Iris — is it honest; where does the metaphor end and the mechanism begin? VERDICT: HONEST, boundary marked above.**
The mapping table's third column is the honesty mechanism: every row names the function, not a feeling. The ASPIRATIONAL list names exactly what is not built (sibling bindings, full Parliament semantics, the [PROPOSED] tap cap, the ring-depth store, the DCLM commit-path wiring). No PENDING is presented as live; no PROPOSED as decided; no UNKNOWN as PASS. The one risk flagged: the word "neural" could be read as claiming biological fidelity — it claims architectural fidelity (pathways, synapses, plasticity, consolidation), which the code exhibits.

**Twain² — does it run? VERDICT: RUNS.**
`python3 test_neural.py` → 28 tests, OK, 0.006s. No external dependencies beyond the standard library. The sibling worker can import `neural` today: `Tree`, `Pathway`, `Synapse`, `Body`, `plus_one_factor`, `build_receipt`, `RefusedError` are all importable, and `Synapse.fire` / `Pathway.judge_fn` are the documented integration points for `iris_arbiter.py` / `iris_laws.py` / `iris_patterns.py`. Known limit: in-memory receipts only — persistence wiring is the named build item.

## Interface contract for the sibling worker

- Bind circuits: `tree.add_pathway(..., judge_fn=my_judge)` where `my_judge(signal) -> Judgment` (from `iris_laws` / `iris_patterns`).
- Feed judgments: `tree.synapses["synapse.prob_det"].fire([judgment_d, judgment_p])`.
- Own the arbiter: subclass or wrap `Synapse` with `kind="arbiter"` — the integration points here are named so `iris_arbiter.py` can adopt them rather than duplicate them.
- Read the fire log: `syn.fire_log` and `tree.active_traces` carry every receipted event.

*End of NEURAL_UNIFICATION. Testnet only. The brain thinks in tree patterns; the synapses fire economic judgments — and every firing is receipted.*
