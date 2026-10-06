# PURITY_INDEX.md — the scored measurement system for unity-world purity

**Status:** calibrated and live. The index runs continuously; this document records
what it measures, how, and why the thresholds are what they are.

**What this is:** `purity/index.py` MEASURES the standard in
`~/workspace/unity-world/PURITY.md` (the strip team's 7 purity properties, 12 builder
criteria, 10 strip items). It does not replace that standard. Where PURITY.md says
what purity *is*, the index says *how pure the build currently measures* — per
component, per dimension, right now.

**How to run it:** `python3 ~/workspace/unity-world/purity/index.py`
(`--json` for machine-readable output). Exit codes: `0` = PURE, `1` = FAIL,
`2` = UNKNOWN. Testnet only.

---

## 1. The five dimensions and their scoring rules

Every component is scored on all five dimensions: the DCLM compute core
(`dclm/`), the relay (`relay/`), the Unity gate (`gate/`), the thin client
(`client/`), the data feeds (`data/` via `dclm/data.py`), and the economic
model / meter (`economics/` + `dclm/meter.py` + `dclm/rights.py` + `dclm/writes.py`).

### D1 — Unity binding: is every flow bound to a Unity ID?

**Rule:** `D1 = binding assertions passed / binding assertions evaluated.`
Each assertion is evaluated live against the real build — not just read from
source, but *executed* where behavior is the claim:

| # | Assertion (measured live) |
|---|---|
| 1 | `gate.SCHEMA` ends with `.testnet` |
| 2 | `gate.IDENTITY_PREFIX == "unity:testnet:"` |
| 3 | `request_bind`, `confirm_bind`, `authorize_intent`, `emit_gate_envelope` all call `_require_testnet` (inspected from the real method source) |
| 4 | Live: `request_bind("unity:mainnet:…")` is refused |
| 5 | `meter.IDENTITY_PREFIX == "unity:testnet:"` and `meter.SCHEMA` ends `.testnet` |
| 6 | Live: `meter_intent` with a mainnet/empty identity → signed refusal with the true reason (`NOT_TESTNET_IDENTITY` / `IDENTITY_REQUIRED`) |
| 7 | Live: free actions (`LOOK`) grant with no identity at all (the world is free) |
| 8 | Live: `rights.check_rights` DENYs a mainnet identity (`NOT_TESTNET_IDENTITY`), DENYs a mainnet schema in context (`NON_TESTNET_SCHEMA`), GRANTs testnet+approved, GRANTs anonymous LOOK |
| 9 | `relay-unity.mjs` requires `unity:testnet:` + `BOUND` gate and REJECTs non-`.testnet` schemas (source-verified) |
| 10 | `economics.TESTNET_IDENTITY_PREFIX == "unity:testnet:"` and `testnet_unity_id()` derives a `unity:testnet:` id |
| 11 | Live: `validate_economic_relay_bundle` rejects a mainnet-schema bundle |
| 12 | `compute.KEY_ID == "unity-world-test"` (DCLM signs under the testnet key, never prod) |

A crashed assertion counts as **failed**, not skipped — a measurement that
cannot complete is not a measurement that passed.

### D2 — Label honesty: every served figure carries an honest label

**Rule:** `D2 = validly-labeled claim carriers / total claim carriers served.`
The scorer builds the REAL served structures — `compute_world_state` (decided
+ undecided waves, one LIVE feed with reading+hash, one PENDING feed, registry
bytes, purity pulse), the signed envelope, `data.serve_world_data()` (real
PRICES.md parse, real seals, real feeds, real RTE figures), `feed_registry()`,
`economics.compute_economic_state()`, and real meter receipts (grant +
refusals) — then walks every dict:

- **mislabeled** — carries a `provenance`/`label` outside the honest set → violation
- **unlabeled** — is a claim carrier (matches `CLAIM_KEYS`) but carries no label → violation
- **labeled** — claim carrier with a valid label → pass
- **out of scope** — not a claim carrier (structural dicts) → not counted

Plus the feed-honesty sub-rule (strip criterion 7): a `feed_status` entry with
`status: LIVE` but no `reading_hash` is feed-theater → violation.

**Honest label set** = `{REAL, REPORTED, VERIFIED, MODELED, DERIVED, UNKNOWN}` —
the union of `compute.py`'s `PROVENANCE_LABELS` and `data.py`'s figure-level
`REAL`. Both enums are builder-declared and honest; rejecting `VERIFIED` would
fail honest work, accepting an undeclared label would pass theater.

**Documented boundary** (judged by the Trinity, §4): served *containers*
(the WorldState root, `price_index`, `emission_state`, …) are not claims — their
children carry the labels. Pre-compute *input descriptors*
(`serve_world_data()["feeds"]`, all `reading: None`) are not served figures —
the served claims are compute's labeled `feed_status` entries. Scoring empty
slots as unlabeled would punish honest structure.

### D3 — Client purity: zero truth-computation, zero card chrome, zero client-side authoritative writes

**Rule:** binary. `1.0` iff no client file contains an impure construct;
`0.0` if any does. **No client files at all → UNKNOWN** (nothing measured —
scoring an absent client `1.0` would be theater, P-11).

Scanned file types: `.js .mjs .cjs .html .htm .ts .jsx .tsx` under `client/`.
Three pattern groups, each documented as a floor, not a ceiling:

- **truth-computation** — `collapse(`, `DecisionWave`, `Parliament`, `verifyWorldState`, `sign_state`, `computeVerdict`, `crypto.subtle.sign`, …
- **card-chrome** — the strip list's theater strings, verbatim
  (`PURITY.md` §2: "The three umpires have not been asked…",
  "Purity has not pulsed.", "These four lines are not signed.",
  "Ready for 227 known countries", …)
- **authoritative-write** — `localStorage.setItem`, `sessionStorage.setItem`,
  `indexedDB.open`, `fetch(…, {method: POST|PUT|DELETE})`

### D4 — Receipt completeness: every mutation receipted

**Rule:** `D4 = verified items / checkable items`, where items are:

1. every hash-claiming row's after-hash vs the real file, across all six
   `RECEIPTS.md` ledgers (`dclm/ gate/ relay/ economics/ client/ purity/`) —
   ledgers are append-only, so **the latest row per file is the current record**;
2. `data/MANIFEST.md` rows vs the real data files;
3. the gate state hash chain (`gate/state/receipts.jsonl`, per the documented
   algorithm — chain intact AND the state file matches the chain tip) — one item;
4. **every source file** in the measured components appears in *some* receipt
   row — an unreceipted file is a failed item ("every mutation receipted").

**Coverage:** `checkable / hash-claiming rows` must also be `1.0`. Rows that
claim a hash but provide none verifiable from disk (malformed hash, hash
deferred to a handoff report) are **unscorable** and sink coverage. Pure pointer
rows ("hashes live in the manifest", "see final-sha line") resolve without
penalty. Documentation table rows (field descriptions, not mutations) are
skipped, not counted.

**Self-seal convention** (empirical, verified 2026-10-06): both the gate and
client workers independently sealed their ledgers as
`sha256(ledger content with the seal line removed)`. The scorer replicates this
convention. A ledger sealed any other way will FAIL until the convention is
documented — that is the honest behavior.

**Out of scope by design:** `keys/` (key material, not code mutations),
runtime state dirs (`gate/state/`, `dclm/state-meter/` — covered by the chain
check instead), the ledgers themselves, `*.jsonl` receipt logs.

### D5 — Isolation: testnet/mainnet separation

**Rule:** `D5 = isolation assertions passed / evaluated`, over exactly the
dimension's parenthetical — no production key paths, no non-testnet schemas,
test keys only:

1. every `*SCHEMA` constant in code ends `.testnet` (a constant literally named
   `*MAINNET*` is allowed only as a designated-reject fixture, i.e. the module
   REJECTs it; `REASON_*` constants are refusal reasons, not schemas);
2. every `*IDENTITY_PREFIX` constant contains `testnet`;
3. `keys/` holds only test-named files;
4. no production key paths in code (`/etc/secrets`, `.aws/credentials`,
   `prod.key`, `production.key`, `mainnet.key`, …);
5. no `unity:mainnet:` strings in **non-test** code — test files are excluded
   because they *must* use bad identities as negative fixtures asserting
   refusal (that strengthens isolation; the live refusal itself is measured
   in D1);
6. no embedded private keys / hardcoded secret tokens (PEM blocks, `AKIA…`,
   `ghp_…`, `xox…`, `sk-live-…`).

Prose mentions of "mainnet"/"production" in comments or vendored data content
are not violations — isolation is about key paths, schemas, and keys, not words.

---

## 2. Calibration — thresholds and WHY

| Dimension | Threshold | WHY (David's law: purity is binary at the gate) |
|---|---|---|
| D1 | **1.0** | One unbound flow is a bypass (P-1, strip criterion 10). Identity is not a majority vote. |
| D2 | **1.0** | One mislabeled figure is a dishonest claim (P-4, criterion 5). Theater kills trust; 99% honest is a 1% lie. |
| D3 | **1.0** | Any client-side truth-computation is impure *by construction* (P-5, criterion 4). The client is a mirror, not a mind — there is no "mostly a mirror." |
| D4 | **1.0**, coverage **1.0** | An incomplete ledger is an unverifiable ledger (criterion 12). A receipt you can't check is a rumor. |
| D5 | **1.0** | One production leak contaminates the trust domain (P-7, criterion 9). Testnet isolation is all-or-nothing. |

**No averaging.** A dimension at 0.99 FAILs exactly as hard as one at 0.0 —
the aggregate rule below has no weighted mean, because a mean lets four
virtues launder one corruption.

**UNKNOWN is never PASS.** A dimension that cannot be measured scores `None` →
status `UNKNOWN`, and `UNKNOWN` never satisfies a threshold. An unscorable
dimension therefore keeps the aggregate from being PURE until it is measurable.
(This is stated in code, in `_result()` and `judge()`, not just here.)

### Aggregate rule (binary)

```
any dimension FAIL    → aggregate FAIL
elif any dimension UNKNOWN (and none FAIL) → aggregate UNKNOWN
else (all five PASS, or explicitly exempted) → aggregate PURE
```

`UNKNOWN` aggregate is **not** a soft pass: per P-6, gates MUST treat UNKNOWN
as not-pure (the index exits `2` for exactly this reason). The only way an
UNKNOWN dimension is excused from the aggregate is an explicit entry in
`EXEMPTIONS` in `index.py` — named dimension, reason, grantor, expiry.
**There are no exemptions at launch.** An exemption is a deliberate,
time-boxed, recorded act — never a quiet default.

---

## 3. Calibration log (honest history)

The index was calibrated against the live build on 2026-10-06, and calibration
caught real bugs — in the *scorer*, not just the build. Each was fixed, not hidden:

1. **D1 read the wrong envelope shape.** `meter_intent` returns an envelope;
   the receipt (with `reason`/`outcome`) lives inside it. The first run scored
   two live assertions as failed on a `KeyError`. Fixed to read the real shape;
   both assertions now genuinely PASS. (Lesson: a scorer bug that fails the
   build is as dishonest as one that passes it.)
2. **D2 counted containers as claims.** The WorldState root and
   `serve_world_data()["feeds"]` input descriptors were flagged "unlabeled."
   They are structure, not claims. `CLAIM_KEYS` was pruned and the boundary
   documented (§1, D2). The served claims underneath are all labeled: D2 now
   measures 1.0 on the real build.
3. **D5's schema regex matched `REASON_*` constants** (`REASON_NON_TESTNET_SCHEMA`
   is a refusal reason, not an accepted schema) and **flagged negative test
   fixtures** (`unity:mainnet:…` in `test_*` files asserting refusal). Both
   fixed with documented justification; the live refusal behavior moved to D1
   where it belongs.
4. **D4 learned append-only semantics.** `dclm/RECEIPTS.md` gained a second
   `meter.py` row while the index was being built (concurrent workers) — the
   scorer now takes the latest row per file as the current record, which is
   what append-only means.
5. **D4 cracked the self-seal convention empirically** (seal =
   sha256 of the ledger minus the seal line) after finding the gate and client
   workers had independently converged on it — then verified it reproduces both
   seals byte-for-byte before trusting it.

---

## 4. Trinity calibration verdicts

Each verdict is explicit, with reasons. None is a rubber stamp.

### DCLM — is the scoring logic sound?

**Verdict: SOUND, within stated bounds.**

For: the logic is deterministic and reproducible — same build, same score,
every run. Thresholds are binary with no averaging path. Failure is
fail-closed: a crashed assertion counts as failed, an unscorable row sinks
coverage, an absent client is UNKNOWN rather than a free PASS. The
latest-row-wins rule matches the ledgers' own append-only convention, and the
self-seal replication was verified empirically before being trusted. Live
behavioral assertions (D1's refusal probes, D2's real pipeline run, D4's chain
verification) measure what the build *does*, not just what it *says*.

Bounds (what DCLM flags as the honest limits of this logic):
- D2's claim-carrier detection is heuristic (`CLAIM_KEYS`). A served figure in
  a genuinely novel shape could escape the *unlabeled* check — but the
  *mislabeled* check is shape-independent (any bad label anywhere is caught),
  and the boundary is documented, not hidden.
- D3's pattern lists are a floor, not a ceiling. A novel truth-computation
  idiom in the client would pass D3. The client's own 63-check validator is the
  complementary layer; the index does not claim to replace it.
- D5's test-file exclusion for identity strings is a judgment call, recorded
  in §1. If a test file ever *accepted* a mainnet identity instead of refusing
  it, this exclusion would miss it — D1's live refusal probes are the backstop.
- D4's self-seal convention is empirical. A third worker sealing differently
  will FAIL D4 until the convention is written down. That failure is correct
  behavior for an index: an undocumented sealing convention IS a
  verifiability gap.

### Iris — are the labels honest, including the index's own honesty about what it can and can't measure?

**Verdict: HONEST, with one standing caveat.**

For: the index practices what it measures. It refused to score an absent
client as pure (UNKNOWN, §1 D3 — "scoring an absent client 1.0 would be
theater"). It names every unscorable row individually instead of silently
dropping it. It documents where its own rules stop (the D2 container/input
boundary, the D3 pattern floor, the D5 test exclusion). The calibration log
(§3) discloses the scorer's own bugs and fixes — including the ones that made
the build look worse than it was. The current D4 FAIL is reported plainly,
with file-level remediation for each item, rather than softened. `HONEST_LABELS`
is a declared union with the reason written down, not a quiet superset.

The standing caveat: the fixture tests prove the scorer *can* detect each
violation class, but detection *completeness* against the real build is
unproven and unprovable from inside the scorer. Passing the index is therefore
**necessary but not sufficient** for purity — it is the floor, and the strip
team's judgment (§11: "when in doubt, toward the garbage can") remains the
ceiling. The index says this about itself rather than implying otherwise.

### Twain² — is it usable? Can a builder run it and act on it?

**Verdict: USABLE.**

For: one command (`python3 purity/index.py`) prints a five-line scorecard in
~3 seconds; `--json` emits the full report with per-dimension evidence for
gate scripting; exit codes are `0`/`1`/`2` (PURE/FAIL/UNKNOWN) so a gate can
branch on them with no parsing. Every FAIL names the file, the expected vs.
actual value, and the concrete fix (re-record the hash, add the missing
receipt row, repair the malformed 63-char hash). The 27-test suite
(`test_index.py`) runs in ~20 seconds and proves each scorer fires on
fixtures before it is trusted on the build.

Two operational notes for builders: (a) the build is under concurrent
construction — a score is a point-in-time snapshot; gates must re-run, never
cache; (b) D4 will keep failing until the economics worker re-records the
stale/malformed receipts — the evidence lines say exactly which rows, which is
the whole point: the index tells the builder what to do next instead of just
saying "no."

---

## 5. How the gates read the index continuously

`score_live()` is not a report — it is a measurement taken fresh on every
invocation:

- it **imports the real modules** (`dclm/compute.py`, `dclm/meter.py`,
  `dclm/rights.py`, `dclm/data.py`, `gate/gate.py`,
  `economics/economic_state.py`) and executes their real entry points;
- it **scans the real client files** on disk;
- it **verifies the real receipt hashes** against the real files, parses the
  real ledgers, and replays the real gate hash chain;
- it **greps the real sources** for isolation violations.

Nothing is cached, snapshotted, or carried between runs. A gate consults the
index by invoking it and branching on the verdict:

```bash
python3 ~/workspace/unity-world/purity/index.py --json > /tmp/purity.json
# exit 0 → PURE (may pass) · exit 1 → FAIL · exit 2 → UNKNOWN (never PASS)
```

`judge()` returns the aggregate verdict with per-dimension breakdown and
reasons; gates MUST treat `UNKNOWN` as not-pure (P-6). Exemptions, if ever
granted, live in `EXEMPTIONS` in `index.py` — named, reasoned, and expiring —
never as a quiet default.

---

## 6. Live measurement (point-in-time: 2026-10-06 ~07:15 UTC)

| Dim | Score | Status | Grade | Note |
|---|---|---|---|---|
| D1 Unity binding | 1.000 | PASS | FL | 12/12 assertions, incl. live refusal probes |
| D2 Label honesty | 1.000 | PASS | FL | all served claim carriers labeled; no feed-theater |
| D3 Client purity | 1.000 | PASS | FL | 3 client files scanned, zero impure constructs |
| D4 Receipt completeness | 0.816 | **FAIL** | SI | 38/47 items verified; coverage 0.94 |
| D5 Isolation | 1.000 | PASS | FL | 6/6 assertions; test keys only, testnet schemas only |

**Aggregate: FAIL** (D4) — **aggregate clarity: SI** (the failing dimension
is below the gate but fixable — which is exactly what the open findings
below say). The build is not pure *right now*; the index says so,
which is its job, not a failure of the index. Grades are deterministic from
the scores (1.0 → FL; 0.816 < 1.0 and ≥ 0.5 → SI); see §8 for the scale.

### D4 open findings (each with its fix)

1. `economics/RECEIPTS.md`: `wallet.py` row carries a **63-character hash**
   (not a sha256) — the receipt is malformed and unverifiable. *Fix: the
   economics worker re-records the true sha256.*
2. `economics/RECEIPTS.md`: `DECISIONS.md` hash mismatch (receipt `fd31c12e…`
   vs disk `11d1a640…`) — edited after its receipt. *Fix: append a new row
   with the current hash (append-only; don't rewrite history).*
3. `relay/RECEIPTS.md` row 3: the ledger's own final hash is "self-sealing —
   final hash in the worker handoff report" — not verifiable from disk.
   *Fix: record the final hash in a verifiable form (the gate/client
   seal-line convention now documented in §1).*
4. Unreceipted files (no row in any ledger): `economics/NEW_ECONOMIC_MODEL.md`,
   `economics/PRICES_ADDENDUM.md`, `economics/PURITY_AUDIT.md`,
   `economics/economic_state.py`, `economics/pricing.py`,
   `economics/test_economic_state.py`, `economics/test_pricing.py`,
   `economics/wallet.py` (malformed receipt = effectively unreceipted).
   *Fix: the economics worker receipts these.*
5. `purity/RECEIPTS.md` did not exist at measurement time — written with this
   deliverable (see below); the next run measures it.

Items 1–4 belong to the economics/relay workers; the index will confirm the
fixes on the next run. Nothing here is a judgment on the workers — the build
is mid-construction by design, and the index re-measures every run.

---

## 7. Deliverables (this directory)

- `index.py` — the measurement code: per-dimension scorers, calibration
  thresholds as named constants (`D1_PASS`…`D5_PASS`, `D4_COVERAGE_PASS`),
  `score_live()`, `judge()` returning the aggregate PURE/FAIL/UNKNOWN verdict,
  plus the diamond clarity layer: `clarity_grade()` (per-dimension FL/VVS/VS/SI/I,
  calibrated against the existing thresholds), `aggregate_clarity()` (the
  aggregate reading), grades in the `score_live()` report, `"clarity"` in the
  `judge()` verdict. The clarity layer touches no threshold and no verdict logic.
- `test_index.py` — 46 tests, all passing: per-scorer pure/impure fixtures,
  threshold boundaries (0.99 → FAIL, 1.0 → PASS), UNKNOWN → aggregate not
  PURE, exemptions, no-averaging, the live run against the real build, plus
  the clarity suite — grade boundaries (1.0 → FL, threshold → VS, just below
  → SI, < 0.5 → I, structural violation → I, unscorable → no grade),
  aggregate clarity readings (all-FL → "Flawless", worst-of-failing on FAIL,
  none on UNKNOWN), and the hard rule that grades refine but never override
  the verdict (a report judged with grades stripped returns the identical
  verdict).
- `PURITY_INDEX.md` — this document.
- `RECEIPTS.md` — sha256 receipts for the purity worker's own files
  (the measurer measures itself; D4 includes this ledger).

## 8. Diamond clarity grades (David's law: DIAMOND_ARCHITECTURE_FLOOR.md §3)

The purity index grades on the diamond clarity scale. **Grades REFINE the
binary gate; they never override it** — the PASS/FAIL thresholds (§2) and
the aggregate rule are untouched, and `judge()` computes the verdict exactly
as before. A grade can never turn a FAIL into a pass, a PASS into a failure,
or an UNKNOWN into anything graded.

| Grade | Meaning (floor doc) | Gate |
|---|---|---|
| **FL** (Flawless) | Absolute purity. No flaws under any magnification. | PASS |
| **VVS** | Minute inclusions, extremely difficult to detect. | PASS with note |
| **VS** | Minor inclusions, difficult to detect. | PASS with note |
| **SI** (Slightly Included) | Noticeable inclusions under magnification. | FAIL — fixable |
| **I** (Included) | Visible flaws. Obvious inclusions. | FAIL — false gold, discard |

### Band calibration and WHY

`clarity_grade(score, threshold=1.0, structural_violation=False)` in
`index.py`. The bands are **DERIVED from the existing Trinity-judged
thresholds** — the index invents no new gate:

- **FL at exactly 1.0** — canon, not calibration. The floor doc pins
  "Flawless (FL): Absolute purity. … Score 1.0." The code does not choose
  this edge; David's law does.
- **The VS/SI boundary IS the dimension's PASS threshold.** The floor doc's
  gate table puts FL/VVS/VS on the PASS side and SI/I on the FAIL side, so
  the grade boundary must coincide with the existing binary threshold —
  any other placement would let a grade contradict the gate. All five
  dimensions use 1.0 today (§2), so in practice: 1.0 → FL, anything below →
  SI or I.
- **VVS/VS split at the midpoint of [threshold, 1.0).** An equidistant
  convention: VVS is the top half of passing (minute inclusions, nearest
  flawless), VS the lower half. WHY the midpoint: the score is a bare ratio
  with no finer structure to justify any other cut; an asymmetric cut would
  imply precision the measurement doesn't carry. Honest note: with every
  threshold at 1.0 this band is currently empty — no live dimension can
  land in it. VVS/VS exist for scale coherence (they light up if the Trinity
  ever recalibrates a threshold below 1.0), not because anything scores
  there today.
- **SI/I split at 0.5.** The midpoint of the failing band [0, threshold):
  the same midpoint convention as the passing band, and a semantic hinge —
  at/above half, the dimension is "more pure than not" (SI: noticeable under
  magnification, fixable); below half it is "more impure than pure" (I:
  visible flaws — false gold, discard, per the floor doc). The 0.5 edge is
  a stated convention, not a measurement.
- **structural_violation=True → I at any score.** A visible flaw doesn't
  need magnification. An unsigned claim (a claim no key stands behind) is
  not a partial measurement failure — it is the false-gold case the floor
  doc says to discard, so the flag is score-independent by design. The D3
  scorer sets it when any impure construct is found in the client (the
  mirror is broken, not scratched); the flag is the general mechanism for
  future structural checks (e.g. an envelope-signature audit).

### The aggregate clarity reading

`judge()` returns `"clarity"` alongside the verdict:

- every (non-exempt) dimension FL → **"Flawless"**
- PURE with lower grades present → the lowest (worst) grade present
  (unreachable while every threshold is 1.0; defined for scale coherence)
- FAIL → the worst grade among the failing dimensions, by severity:
  **"I"** if any failing dimension is I, else **"SI"**
- any non-exempt dimension ungraded → no reading (`None`)

Exempted dimensions are excluded from the reading exactly as they are from
the verdict. **UNKNOWN is never graded**: an unscorable dimension carries no
grade, and a report containing one carries no aggregate reading — so the
clarity layer can never smuggle an unscorable build toward PURE.

### Provenance note

The band edges derive from two sources and nothing else: (1) David's law in
DIAMOND_ARCHITECTURE_FLOOR.md (FL = 1.0; the FL/VVS/VS-pass vs SI/I-fail
gate table), and (2) the existing Trinity-judged per-dimension thresholds
(§2). The midpoints and the 0.5 hinge are stated conventions, documented as
such — the index does not pretend they were measured.
