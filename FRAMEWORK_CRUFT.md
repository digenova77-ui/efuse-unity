# FRAMEWORK CRUFT — scaffolding vs law

**Updated 2026-10-24.** User authorized cleanup of scaffolding left behind from implemented or dead ideas.

Rule: law as code stays. Scaffolding that is no longer load-bearing is archived or removed.

## Completed this pass

- `dclm/chunk_build.lock` — deleted (stale empty lock)
- `maximum_run/` one-shot script and run directories — archived to `archive/maximum_run_20261006/`, originals removed
- Purity status modules added across core repos (executable grades, not documentation)

## Retained (still load-bearing)

- All `dclm/test_*.py` — regression harness until LOOP END
- `dclm/tokenize.py` — PEP-562 shim; law lives in `token_engine.py`
- `dclm/ed25519.js` — node helper; no native Python crypto yet
- `dclm/chunk_epoch.json`, `chunk_prev_manifest.json`, `chunk_receipts.log`, `chunk_schema.json` — live inputs to `chunks.py`
- Testnet keys and serve scripts — required while testnet is hand-operated

## Still candidates (next calm window)

- Empty dirs: `dclm/state-meter/`, `economics/state/`, `deploy/staging/` if still empty
- `testnet/state/testnet-serve-*.log` — rotate
- `unity-world/derivative_sim.py` — modeled companion; not runtime

## Law (untouched)

CANON, core dclm modules, economics, gate, purity, iris-intake, relays, client, data.

*End of FRAMEWORK_CRUFT.md.*
