# DERIVATIVE AUDIT — 2D audit office for unity-world

**For auditors: blockchain, DAG, and old-school.** A 2D view on DCLM truth — it displays
what DCLM computed; it never computes. Testnet only.

## Serve it

This is a static site. Serve the `audit/` directory over HTTP from inside the
unity-world tree so the in-browser verification can reach the real files:

    cd ~/workspace/unity-world && python3 -m http.server 8000
    # open http://127.0.0.1:8000/audit/

Relative paths (`../data/…`, `../founding-board/…`) are how the Verify tab fetches
files for hash recomputation. Under `file://` those fetches are blocked — the site
will say so honestly instead of pretending.

## Rebuild the data

    cd ~/workspace/unity-world/audit && python3 build_audit.py

Parses the real sources into `data/*.json`:

| output | source |
|---|---|
| `chain.json` | `dclm/chunk_receipts.log` — epoch chain (42 built epochs, 5 fork points) |
| `gate.json` | `gate/state/receipts.jsonl` — 2-mutation binding chain |
| `manifests.json` | `deploy/SHIP_MANIFEST.md` (45 files) + `data/MANIFEST.md` (10 registries) + disk-hash drift check at build time |
| `receipts.json` | `deploy/TELEMETRY.md` §4 — the six RECEIPTS.md ledgers, 53 rows |
| `tables.json` | test suites, economic params (decided/held), mesh topology, honest gaps, benchmarks |
| `founding.json` | `founding-board/founding-board.json` + acknowledgment hash check |

## The three auditor views

1. **CHAIN** — blockchain auditors. Epoch table (epoch, timestamp, manifest hash,
   previous hash, chunks, bytes, schema, datasets, linkage, fork flags); gate state
   chain; the six receipt ledgers with drift flags. Click any hash for the full record.
2. **DAG** — merge auditors. 2D SVG of the epoch DAG (42 nodes, 41 edges, 5 forks).
   Pan/zoom/click; node panel shows manifest, parents, children, datasets, linkage.
   SVG export included.
3. **TABLES** — spreadsheet auditors. Nine dense tables (ship files, registries,
   founding board, test suites, params, mesh, benchmarks, honest gaps, ledger rows).
   Search, sort, per-table CSV export, per-table JSON export.

**VERIFY** tab: A) epoch linkage re-check · B) gate linkage re-check ·
C) full file-hash recompute in the browser (55 files) · D) founding-board ack hash.

## Honest scope

- Provenance labels on everything: REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN / REAL / PENDING.
- The site checks *consistency* of the record (linkage, recorded-vs-served hashes).
  It does not re-derive DCLM's computations, re-run tests, or seal anything.
  A PASS means the record is self-consistent as served to your browser.
- Disk-hash drift checks in `manifests.json` are labeled AUDIT-BUILD (this build's
  method, point in time) — they are not DCLM seals.
- UNKNOWN is never PASS.
