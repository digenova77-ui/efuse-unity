# RECEIPTS — purity index (purity worker, unity-world build)

Testnet only. The measurer measures itself: this ledger receipts the purity
worker's own files, and D4 (`index.py`) verifies this ledger like any other.

Mutation log: every file here was created new (no prior content, so
before-sha256 is N/A — the file did not exist).

| time (UTC)        | file               | before (sha256) | after (sha256)                                                       |
|-------------------|--------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:10 | purity/index.py    | N/A (new)       | ea00e2d9701322cf42248c2e870746be22c8885c05207ae0c58064a33a582615      |
| 2026-10-06 ~07:10 | purity/test_index.py | N/A (new)     | 9232de0f8bd690c02daa319649c64dfc1a05fa18e9927be807c0225ac4f783ac      |
| 2026-10-06 ~07:12 | purity/PURITY_INDEX.md | N/A (new)   | 7e085ef395491cf07524f1994a35687da6b6071832622f6e7fa1f5bad6917bda      |


| 2026-10-06 ~07:16 | purity/PURITY_INDEX.md | `7e085ef39549`… (creation) | `bb8a64a5c4e9baea113f24a9e15e7ab9db8138b4751c7277ebda1eb31d9fcd21` |
Notes:
- 27/27 tests passing at write time (`python3 test_index.py`).
- Live measurement at write time: D1/D2/D3/D5 PASS, D4 FAIL (economics +
  relay receipt gaps — see PURITY_INDEX.md §6). The index reports the FAIL
  honestly; that is its job.
- Calibration history (scorer bugs found and fixed during calibration):
  D1 envelope-shape read, D2 container/input boundary, D5 REASON_* and
  test-fixture exclusions, D4 latest-row-wins + self-seal convention.
  Full log in PURITY_INDEX.md §3.


| time (UTC)        | file                     | before (sha256) | after (sha256)                                                       |
|-------------------|--------------------------|-----------------|----------------------------------------------------------------------|
| 2026-10-06 ~07:42 | purity/index.py          | `ea00e2d97013`… (creation) | `bef5da1cc76167d9f742acc854b94837e22784b6378dc87394cd55fce622372b` |
| 2026-10-06 ~07:42 | purity/test_index.py     | `9232de0f8bd6`… (creation) | `a1a81b2c2e7c9f3fbbd6895b34c659175e6ef89e8cd5aba387467be5e965c627` |
| 2026-10-06 ~07:42 | purity/PURITY_INDEX.md   | `bb8a64a5c4e9b`… (07:16 update) | `709840c8443bf810b6759972f5d803d222f4950a16bd87daa235eef8e67e0c57` |

Notes (diamond clarity layer, 2026-10-06 ~07:42 UTC):
- `clarity_grade(score, threshold=1.0, structural_violation=False)` added: FL/VVS/VS/SI/I bands
  calibrated against the EXISTING per-dimension thresholds (VS/SI boundary IS the PASS threshold;
  FL canon at exactly 1.0; VVS/VS and SI/I each split their band at the midpoint; 0.5 hinge; structural
  violation -> I at any score). Thresholds untouched; grades refine, never override the binary verdict.
- `score_live()` dimensions now carry `grade` alongside `score`; `judge()` returns `clarity`
  (all-FL -> "Flawless"; PURE -> worst grade present; FAIL -> SI/I by severity; UNKNOWN -> no reading).
- `test_index.py`: 27 -> 46 tests (clarity boundary suite + aggregate clarity suite + live grade checks),
  all passing. `PURITY_INDEX.md`: new §8 documents the scale, the band calibration with WHY, and the
  refine-never-override rule; §6 snapshot gained the deterministic grades; §7 deliverables updated.
- Live at write time: D1/D2/D3/D5 FL, D4 SI (0.855, economics+relay receipt gaps per §6) -> aggregate FAIL,
  clarity SI. The index reports the FAIL honestly; the grade says it is fixable, not false gold.
`RECEIPTS.md` sha256 after this entry (seal-line-excluded convention):
774d3cd6a3dd932bbbac85ee1df96037c2340f3573625d01ad8011b83de751db  RECEIPTS.md