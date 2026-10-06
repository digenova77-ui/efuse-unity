# FRAMEWORK CRUFT — scaffolding vs law

**Maximum run, 2026-10-06.** David's law: elevate law, drop framework.
Nothing was deleted. This document names every scaffolding candidate:
the file, why it is scaffolding, and the removal recommendation.
**Deletion is David's call.**

Rule used: *law as code, structure as reality.* If a file encodes a
standing rule of the world (canon §, a gate, a ledger, a commit path),
it is law. If it exists only to help build, verify, simulate, operate,
or paper over a tooling gap, it is scaffolding.

---

## A. TEST SCAFFOLDING — retain until LOOP END, then re-evaluate

Tests are the loop's measuring instrument (canon IX). They are not law;
they verify law. Removing them before LOOP END blinds the loop.

| File | Why scaffolding | Recommendation |
|---|---|---|
| `dclm/test_*.py` (14 files) | Verify the DCLM core; not the core | Keep until LOOP END; then keep as regression harness or archive |
| `economics/test_*.py` (6 files) | Verify tokenomics/pricing/wallet | Same |
| `gate/test_gate.py` | Verifies the gate | Same |
| `purity/test_index.py` | Verifies the measurer | Same |
| `iris-intake/test_neural.py`, `test_iris_core.py` | Verify Iris | Same |
| `testnet/relay/relay-testnet.test.mjs` (14 tests) | Verifies testnet relay | Same |
| `unity-world/relay/relay-unity.test.mjs` (42 tests) | Verifies unity relay | Same |
| `testnet/proof/unification-proof.mjs` (17 proofs) | End-to-end verification script | Same; now hermetic (fixed 2026-10-06) |
| `client/validate-client.mjs` | Client boundary validator | Same |
| `economics/gauntlet/` (`gauntlet.py`, `run*.py`, `run*.log`, `results*.json`) | Adversarial test runs + logs | Archive logs/results to cold storage; keep runner until LOOP END |

## B. SHIMS & PLUMBING — load-bearing until replaced

| File | Why scaffolding | Recommendation |
|---|---|---|
| `dclm/tokenize.py` | PEP-562 shim: exists only because a module named `tokenize.py` shadows the stdlib and breaks `linecache`/`unittest` (documented in-file). The law lives in `token_engine.py`. | Rename the public path (e.g. `tokenize_api.py`) and delete the shim at the next calm window — or keep forever; it is 60 lines of honest plumbing. David's call. |
| `dclm/ed25519.js` | 20-line node subprocess helper for Ed25519 (DECISIONS.md §5: "shell to node" because Python here has no `cryptography` lib). Plumbing, not law. | Replace with a native Python Ed25519 lib when one is approved; delete the helper then. Until then it is load-bearing. |
| `iris-intake/__pycache__/`, `dclm/__pycache__/`, etc. (8 dirs) | Bytecode caches | Safe to delete any time; regenerate on import. |

## C. OPS SCAFFOLDING — needed while humans operate the testnet

| File | Why scaffolding | Recommendation |
|---|---|---|
| `testnet/serve/start-testnet.sh`, `stop-testnet.sh` | Shell wrappers around `node *.mjs &` | Replace with a process supervisor (or the daemon's own supervision) when the testnet graduates; keep while hand-operated |
| `testnet/serve/lib.mjs` | Shared helpers for the three HTTP services | Fold into the services or keep — small, honest |
| `testnet/ipns/mint-testnet-keys.mjs` | One-shot key minting (refuses to overwrite) | Archive after keys exist; re-run only for a new testnet |
| `testnet/keys/testnet-*.key` (3 files) | Test key material | NEVER delete while the testnet lives — but they are scaffolding in the elevate-law sense: the law is key-agnostic |

## D. INTERMEDIATES & LOGS — safe to archive/delete

| File | Why scaffolding | Recommendation |
|---|---|---|
| `dclm/chunk_build.lock` (0 bytes, stale) | Build lock left by a chunk build | Delete — stale |
| `dclm/chunk_epoch.json`, `chunk_prev_manifest.json`, `chunk_receipts.log`, `chunk_schema.json` | Chunk-build intermediates | Archive one snapshot; the live chunk state is what matters |
| `dclm/state-meter/`, `economics/state/` (empty dirs) | Unused state dirs | Delete if still empty at next pass |
| `deploy/staging/` (empty) | Unused staging dir | Delete or use |
| `testnet/state/testnet-serve-*.log` | Service stdout logs | Rotate; keep last N |
| `maximum_run/2026*/` (this run's artifacts) | Run evidence, not law | Keep as the run's receipts; archive after the report lands |

## E. SIMULATIONS — modeled exploration, not the system

| File | Why scaffolding | Recommendation |
|---|---|---|
| `unity-world/derivative_sim.py` (+ `__pycache__`) | Galton-Watson validation sim for DERIVATIVE_MAX_EFFECTS.md. All outputs MODELED; validates math, runs nothing real. | Keep beside the .md as its validation companion, OR archive — it is not part of the runtime. |

## F. WHAT IS LAW (not scaffolding — do not touch)

- `CANON.md` + the `*.md` law documents (PURITY.md, TOKENIZATION.md is law-doc for `token_engine.py`, etc.)
- `dclm/` core: `compute.py`, `meter.py`, `purify.py`, `rights.py`, `writes.py`, `onboard.py`, `token_engine.py`, `winter.py`, `tap.py`, `share.py`, `seed.py`, `chunks.py`, `data.py`
- `economics/`: `pricing.py`, `tokenomics.py`, `wallet.py`, `fuse.py`, `mesh_escrow.py`, `economic_state.py`
- `gate/gate.py`, `purity/index.py`, `loop.py`
- `iris-intake/`: `neural.py`, `iris_core.py`, `iris_state.py`
- `relay/relay-unity.mjs`, `testnet/relay/relay-testnet.mjs`, `testnet/daemon/daemon-testnet.mjs`
- `testnet/serve/`: `dclm-origin.mjs`, `relay-api.mjs`, `health.mjs` (the live testnet)
- `client/` (the world's mirror — D3 flags apply, but it is law-adjacent, not scaffolding)
- `founding-board/` (the registry)
- `data/` (reference data)

## G. KNOWN STALE LAW-TEXT (not cruft — needs amendment, not deletion)

- `CANON.md` §V/§VI still say Merit non-transferable / Unity via bound sale — superseded by David's 2026-10-06 ~03:35 resolution (Merit transferable; Unity non-transferable; bound sales dead). The code (`token_engine.py`, `economics/DECISIONS.md` §13) already implements his word. The canon text needs the amendment — a scribe task, not a deletion.

---

*End of FRAMEWORK_CRUFT.md. Nothing deleted. Deletion is David's call.*
