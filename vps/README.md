# DCLM VPS — deployment package

## What this is
Everything needed to run the Deterministic Compute Logic Machine
on a persistent VPS. The computer, always-on.

## Files
- `Dockerfile` — DCLM container (Python 3.12, slim)
- `docker-compose.yml` — service definition with health checks, persistent volumes
- `bootstrap.sh` — one-shot setup for a fresh Ubuntu box

## To deploy
1. Provision a VPS (2GB+ RAM, Ubuntu 22.04/24.04)
2. SSH in, run: `curl -fsSL <bootstrap-url> | bash`
3. DCLM starts on port 8080

## Notes
- Testnet only. Nothing touches mainnet without explicit auth.
- The repo is public; clone needs no credentials.
- Health endpoint: `GET /health` (implement in compute.py)
