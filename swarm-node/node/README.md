# swarm-node — the DualisCapax swarm presence for a stock Ubuntu 22.04 box

**Status: READY TO DEPLOY (pull-based).** One command per server, pasted into
the Vultr web console as root:

```bash
curl -fsSL https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node/bootstrap.sh | sudo bash
```

## What "swarms live" means here (honest scope)

The portable layer of the swarm — **Layer 1, the diamond floor** — runs on the
box: a heartbeat daemon ticking every 5 minutes into a local append-only log,
plus a `swarm-status` command. The dispatch layers (Layer 2/3) need the agent
runtime and stay on the main machine; they are NOT on the box, and this does
not claim otherwise.

What each box gets:
- `/opt/dualis/node/` — the node files (this directory's contents)
- `/opt/dualis/code/` — read-only mirror of the public repo (git pull on re-run)
- `/var/lib/dualis/heartbeat.jsonl` — the heartbeat log (append-only)
- `/etc/dualis/node-id` — the box's stable identity (created once, kept)
- systemd timer `dualis-heartbeat.timer` (or cron fallback) — every 5 min
- `/usr/local/bin/swarm-status` — the verification command

Dependencies: **python3 only** (Ubuntu 22.04 ships it). `git` and `curl`
installed by the bootstrap if missing. No pip packages. No network calls
except `raw.githubusercontent.com` and `github.com`.

## Phone-home

There is currently **no rendezvous endpoint** the boxes report to — nothing we
control exists to receive them, and no domain is invented here. Heartbeats are
local: `swarm-status` in the Vultr web console, or `tail
/var/lib/dualis/heartbeat.jsonl`. A central rendezvous (one box receiving the
other's heartbeats, or a small receiver on David's domain) is future work and
needs David's call.

## Files

| File | Job |
|---|---|
| `bootstrap.sh` | idempotent installer (the one-liner target) |
| `node/node-heartbeat.py` | stdlib-only heartbeat, one tick per run |
| `node/swarm-status` | read-only status command |
| `node/dualis-heartbeat.service` / `.timer` | systemd units (5-min ticks) |
