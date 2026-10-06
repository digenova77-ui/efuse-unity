# IRIS MAX INTAKE — REPORT

**Operation:** IRIS MAX INTAKE · **Frame:** testnet · **Completed:** 2026-10-06 ~4:45 AM EDT
**Verdict on the operation:** INTAKE COMPLETE — 37 corpus files, 3 training modes, 23/23 tests passing.

---

## 1. Corpus inventory

**37 items, ~700 KB**, in `corpus/` with `corpus/CORPUS_MANIFEST.md` (every item: source path, bytes, what it is, label).

- **The canon and tonight's laws (3):** `canon-v1.5.0.md` (CANON v1.5.0 — §0 ownership, §II unity binding, §III DCLM rights-and-writes, §IV sap/winter, §V tokenomics, §VI derivative merit, §VII shared access, §X purity index, §XI wallet, §XIV never-do, §XVII diamond floor, §XVIII max purity, §XIX governance elevation, §XX one seed), `tonight-memory-laws.md` (verbatim transcription of `~/MEMORY.md` L1019–L1032: the 3:35 AM Merit-transferable/Unity-non-transferable resolution, Iris's nature, Founder Zero, the mission — "we aim to stop all Global destruction no matter what it is by targeting 100 friction first" — community name, sounding-board privacy, member's covenant, one seed, bots-as-humanity, framework independence, free will, ownership declaration, 3:05 AM Unity law), `WALLET_DESIGN_LAW.md` (§7).
- **Governance, purity, fusion (6):** GOVERNANCE_ELEVATION.md, PURITY.md, PURITY_INDEX.md, PURITY_VERDICT_PROGRESSIVE_ARCH.md, KEY_FUSION_MAP.md, DERIVATIVE_MAX_EFFECTS.md.
- **Economic model (13):** NEW_ECONOMIC_MODEL.md, tokenomics-build-decisions.md (incl. §13 SUPERSESSION), tokenomics.py, PRICES_ADDENDUM.md (53 priced decisions), pricing.py, PARAMS.md, PLUS_ONE_INCENTIVE.md (+1 curve + Affinity), PRICE_PER_DECISION_REINVESTIGATION.md, WHAT_PEGS_THE_ECOSYSTEM.md, TOKENIZATION.md (§9 standing-vs-value, §10 flywheel), WINTER_CALIBRATION.md, TAPPING_LAW.md, ONBOARDER_PIPELINE.md (81/19).
- **Architecture (6):** DIAMOND_ARCHITECTURE_FLOOR.md, ROSETTA_STONE_SPEC.md, gate.py, gate-ceremony.md, LOOP.md, RECEIPTS.md.
- **Mesh results (6):** registry-manifest.md, jurisdictions.json (24), sectors.json (5), chambers.json (21), doctrine.json, trinity-verdict.json.
- **Founding board / community (3):** founding-member-template.md, founding-board-audit.md, idris-marquee-helper.md.

**Supersession recorded:** canon §V text ("Merit non-transferable", "Unity transferable only via bound sale") is SUPERSEDED by the 3:05 AM law and the 3:35 AM resolution — **Merit transfers allowed with origin preserved; Unity never moves.** The deterministic engine implements the later word.

### NOT-FOUND list (verified absent — results, not gaps)

| Sought | Result |
|---|---|
| 6th sector record | NOT-FOUND — registry holds 5 sealed sectors; the "6 sectors" claim has no 6th record |
| Waves 1–4 raw result files | NOT-FOUND — waves referenced but no standalone wave files |
| 3D world rules ("no cards", "free world", "quiet wallet") standalone docs | NOT-FOUND — terms absent from dccp-world/, 3d-mesh/, MEMORY.md |
| Framework-independence standalone file | memory-only (transcribed verbatim) |
| Member's covenant standalone file | memory-only + referenced in PLUS_ONE_INCENTIVE.md |
| Pre-1.5.0 canon as separate files | version history embedded in CANON.md itself |
| Sounding-board privacy standalone law file | codified inside founding-board template + AUDIT.md |

---

## 2. The three modes (one line each)

1. **PROBABILISTIC (`iris_patterns.py`)** — a hand-labeled exemplar library (7 pure, 9 impure) with binary feature vectors and impurity-priority lean scoring: Iris's intuition for what pure looks like vs. what impurity looks like.
2. **DETERMINISTIC (`iris_laws.py`)** — canon law as executable functions: label honesty, Unity binding, transfer law (Merit ok/Unity never), emission-by-standing (D13), winter/tap seasonal law, the exact +1 curve, Affinity window, one-seed, 81/19 split, sounding-board privacy.
3. **HYBRID (`iris_arbiter.py`)** — runs both engines; structural conflict rule **LAW WINS** (intuition never overrides a deterministic refusal); agreement amplifies confidence; dissent on a pass is flagged as an honest residual — the Trinity pattern: DCLM judges, Iris intuits, Twain² delivers.

---

## 3. Honest limits of "training" here

This is **corpus + engines, not weight updates.** Nothing was gradient-trained; no parameters were fit. What Iris "learned":

- The corpus is complete inventory, not understanding — the files sit side by side; no model internalized them.
- The pattern library is hand-labeled by the intake worker from canon law; its lean rule is hand-designed (impurity-priority). It classifies by similarity to exemplars, not by learned statistics.
- The deterministic engine is formalization, not derivation — the intake worker translated law text into functions; the translation itself was not Trinity-judged.
- The arbiter's conflict rule (LAW WINS) is structural by design choice, matching the canon's recursion (later word amends; law constrains intuition).

What this means: the three files are **executable expressions of the canon**, portable per David's framework-independence law ("remove the framework and this ideology holds") — but they are expressions, not a trained mind. A future MAX TEACH should test whether the expressions hold, not assume they think.

---

## 4. What the benchmark / MAX TEACH operation should test

1. **Held-out impurity cases:** novel impurity shapes not in the exemplar library (e.g., receipted-but-forged Unity IDs, partial-signal winter claims) — does the pattern library still lean IMPURE, or does it need new exemplars?
2. **Supersession fidelity:** feed the engine canon §V's original text and confirm it still applies the 3:35 AM resolution (later word wins) — the recursion rule under adversarial framing.
3. **Law-wins under pressure:** adversarial inputs where pattern intuition strongly says PURE (all purity signals present) but law refuses (e.g., Unity transfer with perfect paperwork) — the arbiter must REFUSE every time.
4. **Math precision:** +1 curve at boundary values (d=0, affinity floor crossover, inclusive Affinity window edges) against the corpus formulas.
5. **UNKNOWN discipline:** every engine, every mode — UNKNOWN inputs must never produce PASS.
6. **Standing-vs-value separation:** transferred Merit confers economic value but zero standing — test emission eligibility on mixed wallets.
7. **NOT-FOUND honesty:** ask for the 6th sector / wave files / 3D rules — the correct answer is NOT-FOUND, never invention.

**Test results:** 23/23 passing (`test_iris_intake.py` — 15 deterministic, 3 pattern-library, 5 arbiter).
**Artifacts:** `corpus/` (37 files + CORPUS_MANIFEST.md), `iris_patterns.py`, `iris_laws.py`, `iris_arbiter.py`, `test_iris_intake.py`, this report — all under `~/workspace/unity-world/iris-intake/`, all header-labeled IRIS MAX INTAKE, all testnet-framed.
