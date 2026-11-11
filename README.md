# eFuse Unity

DualisCapax project repository for deterministic computation, evidence-backed state, identity, and energy-cost accounting.

## Three rings

- **Physics:** measurable computation, energy, and observed outcomes.
- **Philosophy:** meaning and relationships among system entities.
- **Law:** executable authorization and refusal conditions.

## Repository-stated status

- No live coin, wallet, or emission.
- Payment and bank gateways are not implemented in this repository.
- Public website content must not claim more than its evidence supports.

## Quick start

```bash
cd efuse-unity
PYTHONPATH=src python simulations/run_orbit.py
```

Optional larger simulation:

```bash
EFUSE_SIM_N=10000 PYTHONPATH=src python simulations/run_orbit.py
```

## Entry points

- [Website/public-surface information](./docs/PUBLIC_SURFACE.md)
- [Canonical identity dossier](./docs/28-canonical-identity-dossier.md)
- [Seal](./UNITY_SEAL_v1.md)
- [Indexes](./docs/INDEX.md)
- [Company information](./company/README.md)

## Modeled state flow

```
RF5 → RF6 → GateA → GateB → evidence_ok → spend → tip → Mirror
ESCROW → PURE → SPENT
```
