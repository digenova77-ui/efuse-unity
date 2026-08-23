# eFuse Unity

**Fuel under an empty center.**  
`coin = fuel_not_Accept` · `pure_own = cost paid before title` · Mirror ∈ {0,1}

## Seal

See [`UNITY_SEAL_v1.md`](./UNITY_SEAL_v1.md). Boot computes `unity_hash` and refuses drift.

## Quick start

```bash
cd efuse-unity
PYTHONPATH=src python simulations/run_orbit.py
# EFUSE_SIM_N=10000 PYTHONPATH=src python simulations/run_orbit.py
```

## Architecture

```
RF5 → RF6 → GateA → GateB → evidence_ok → spend → tip → Mirror
ESCROW --(cost paid + Accept 1)--> PURE --(burn)--> SPENT
```

## Docs

- [White paper direction](./docs/WHITEPAPER.md)
- [Indexes](./docs/INDEX.md)
- [Company launch pack](./company/README.md)

## Simulations

Orbit trials smash honest paths and attacks into the engine.  
**Flat orbit:** honest → 1, attacks → 0, seal stable (gravity to middle).

## Shared playground

Free to test. Same stick. No Exempt. Belongs to them as much as us — under the line, not above it.

---

*Fuel pays the claim; the tip keeps the time; the center stays empty.*
