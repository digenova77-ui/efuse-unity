# The one hand — first-breath bootstrap procedure (FUSED)

David's law: the system cannot be born autonomous. The FIRST bootstrap on a
new lane needs exactly one hand, once, ever. This is that hand, documented
honestly: what it does, and why nothing after it needs one.

**The fusion:** the bootstrap no longer installs a bare node that later gets
middleware bolted on. One paste now births a **cluster citizen** — the node
runtime, the pull-agent, and the birth trace all arrive in the same breath.
The paste line itself did not change; what it births did.

## What the one hand does (per new lane)

1. Open the lane's web console (Vultr dashboard → server → View Console),
   or use the approved browser path.
2. Log in as `linuxuser` (password from the provisioning record).
3. Paste exactly one line and press enter:

   DCLM (New Jersey):
   ```
   curl -fsSL https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node/bootstrap.sh | sudo bash -s -- DCLM
   ```
   EUROPE (Amsterdam):
   ```
   curl -fsSL https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node/bootstrap.sh | sudo bash -s -- EUROPE
   ```
4. Wait for `== swarm node live — born a cluster citizen ==`. On Amsterdam
   only, afterwards run `sudo object-init` once and record the printed
   credentials.
5. Done. The hand leaves.

## What the single paste births

- Node files → `/opt/dualis/node/` (heartbeat, attestation chain, merge,
  status, object-store client)
- Cluster middleware → `/opt/dualis/pull-agent/pull-agent.py` + systemd unit
  `dualis-pull-agent.service`, enabled and started (outbound-only poll loop)
- Identity → `/etc/dualis/node-id` (kept forever), `/etc/dualis/lane`,
  `/etc/dualis/version` (`v1.1.0`)
- Heartbeat timer → `dualis-heartbeat.timer` (every 5 min; cron fallback)
- **The birth trace** → the lane's cluster self-registration as a claim in
  its own attestation chain (`shift_id: birth`,
  `claims_touched: [cluster-registration]`, note carries region, lane,
  version, stream paths, cluster node id). Written exactly once per lane —
  the `born` marker in `/etc/dualis` guards it. Registration is a trace,
  not a config edit: the health consumer sees the lane the moment it reads
  the chain, and GeoDNS/the balancer follow from there.

## Why nothing after needs a hand

- **Outbound-only, forever.** The pull-agent polls GitHub raw + the object
  store over HTTPS. No inbound ports are opened, no SSH is needed, no
  firewall rules are touched.
- **Self-updating.** New node software versions appear in `manifest.json`;
  the pull-agent stages, self-tests, applies, and attests — itself. The
  fused bundle (v1.1.0+) carries node + pull-agent + unit together, previous
  versions kept for rollback.
- **Self-reporting.** Heartbeats and attestations are the health stream;
  the cluster watches the stream, not the box.
- **Self-healing.** A dead lane is removed from DNS answers by the health
  consumer; traffic shifts; the lane's pull-agent keeps trying to heal
  locally and re-announces when it breathes again.

The only remaining human word in the system is "go live" — and that word
is a collapse: his verdict, the system's execution. `golive.py` is that
word, executable.

## Honest failure modes

| Failure | What happens | Recovery |
|---|---|---|
| Paste fails halfway (network drop, console lost) | Whatever installed stays; nothing half-registers — the birth trace is written only after the first heartbeat ticks. | Re-run the same paste. Idempotent: repairs, never duplicates; `born` marker prevents a second birth trace. |
| Lane boots but can't phone home (no outbound net) | Heartbeats and attestations accumulate locally. The cluster sees UNKNOWN — fail-closed, no traffic routed there. | Fix the network; the pull-agent retries the manifest poll forever and the health consumer picks the lane up when its stream arrives. |
| Bundle sha256 mismatch (v1.1.0+) | The pull-agent refuses the bundle, attests `pull-failed`, keeps running the current version. | Fix the manifest/bundle; the next poll retries. Nothing was applied, nothing lost. |
| Second paste on a live lane | Safe no-op: node-id kept, birth skipped (`already born`), files refreshed, pull-agent restarted if the unit changed. | None needed. |
| Garage download fails (EUROPE) | Script exits non-zero at the object-store step — the lane is already born; only the object store is incomplete. | Re-run the paste: birth is skipped, the download retried. `sudo object-init` still comes after. |
| `object-init` never run (EUROPE) | Garage installed but the service never starts; the lane works as a full cluster citizen, just not as the object authority yet. | Run `sudo object-init` whenever ready — no reinstall needed. |

Proven by `tests/test_bootstrap_fusion.py`: the fused bootstrap ran twice
against a fixture (DCLM) plus once (EUROPE) — one birth, stable identity,
valid chain, pull-agent installed from the single paste in every run.
