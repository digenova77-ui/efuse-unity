# eFuse Unity

**Fuel under an empty center.**  
`coin = fuel_not_Accept` · `pure_own = cost paid before title` · Mirror ∈ {0,1}

Company-first public surface. The measure does not require a personal name.  
What connects the project to the world is only what others can **find**: this repo, published site copy, and public registries when they exist.

## Seal

See [`UNITY_SEAL_v1.md`](./UNITY_SEAL_v1.md). Boot computes `unity_hash` and refuses drift.

## Website & portal

See [`docs/PUBLIC_SURFACE.md`](./docs/PUBLIC_SURFACE.md).

```
docs + simulations     → open to test (same toll)
payment / bank gateway → not in this repo (dead until operator builds real rails)
KYC                    → institutions only; not a hash; not this chat
```

Public website uploads are **irreversible marks** — claim ≤ evidence.

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

- [Public surface / website honesty](./docs/PUBLIC_SURFACE.md)
- [White paper direction](./docs/WHITEPAPER.md)
- [Indexes](./docs/INDEX.md)
- [Company pack](./company/README.md)

## Simulations

Orbit trials: honest → 1, attacks → 0, seal stable (gravity to empty center).

## Shared playground

Free to test. Same stick. No Exempt.  
Belongs to them as much as the authors — **under the line**, not above it.

---

*Fuel pays the claim; the tip keeps the time; the center stays empty.*
