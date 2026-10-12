# The one hand — first-breath bootstrap procedure

David's law: the system cannot be born autonomous. The FIRST bootstrap on a
new lane needs exactly one hand, once, ever. This is that hand, documented
honestly: what it does, and why nothing after it needs one.

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
4. Wait for `BOOTSTRAP COMPLETE`. On Amsterdam only, afterwards run
   `sudo object-init` once and record the printed credentials.
5. Done. The hand leaves.

## What the bootstrap installs (so the hand is never needed again)

- Node files → `/opt/dualis/node/` (heartbeat, attestation chain, merge)
- `pull-agent.py` → `/opt/dualis/pull-agent/` + systemd unit
  `dualis-pull-agent.service` (outbound-only poll loop, 5 min)
- Heartbeat timer → `dualis-heartbeat.timer` (ticks every minute)
- Identity → `/etc/dualis/node-id`, `/etc/dualis/lane`, `/etc/dualis/version`
- Directories → `/var/lib/dualis` (state), `/etc/dualis` (identity)

## Why nothing after needs a hand

- **Outbound-only, forever.** The pull-agent polls GitHub raw + the
  object store over HTTPS. No inbound ports are opened, no SSH is needed,
  no firewall rules are touched.
- **Self-updating.** New node software versions appear in `manifest.json`;
  the pull-agent stages, self-tests, applies, and attests — itself.
- **Self-reporting.** Heartbeats and attestations are the health stream;
  the cluster watches the stream, not the box.
- **Self-healing.** A dead lane is removed from DNS answers by the health
  consumer; traffic shifts; the lane's pull-agent keeps trying to heal
  locally and re-announces when it breathes again.

The only remaining human word in the system is "go live" — and that word
is a collapse: his verdict, the system's execution. `golive.py` is that
word, executable.
