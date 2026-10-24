# FRAMEWORK CRUFT — scaffolding vs law

**Updated 2026-10-24 (second pass).**

## Completed

- `dclm/chunk_build.lock` — deleted
- `maximum_run/` one-shot script and run directories — archived, originals removed
- `derivative_sim.py` — archived to `archive/derivative_sim/`, original removed (modeled companion, imported by nothing)
- `dualiscapax-landing/sectors.html` — pure stub removed

## Retained (still load-bearing or content)

- All tests
- `tokenize.py` shim, `ed25519.js` helper
- Chunk state files (live inputs to chunks.py)
- Landing HTML pages that are redirects or carry real content (alchemy, dai-overcol, after-spot, etc.)
- `status.html` (one-line purity marker)

## Notes

Empty directories are not tracked by Git. Testnet serve logs were not present in the tree.
Remaining landing pages were inspected: under-300-byte files are redirects or the status marker. Larger one-off pages contain real content and were left in place.

*End of FRAMEWORK_CRUFT.md.*
