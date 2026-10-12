#!/usr/bin/env bash
# DualisCapax swarm node bootstrap — FUSED. One paste births a cluster citizen.
#
# Run ONCE per server (safe to run twice — it repairs, never wipes, never
# duplicates the birth):
#   curl -fsSL https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node/bootstrap.sh | sudo bash -s -- DCLM
# (lane label is the first argument: DCLM on the NJ box, EUROPE on the Amsterdam box)
#
# Two lanes, not a relay: each box runs its own loop autonomously. Lanes
# exchange ONLY hash-chained attestations (see node/attest.py); the merge
# happens asynchronously via node/swarm-merge. If a lane goes dark, the other
# keeps working — the loop degrades to one lane, never halts.
#
# What one paste births (no second step, no bolt-on):
#   1. Checks python3 (Ubuntu 22.04 ships it); installs git if missing.
#   2. Creates /opt/dualis, /var/lib/dualis, /etc/dualis (never touches anything else).
#   3. Downloads the node files into /opt/dualis/node/ (overwrites only our own files).
#   3b. Downloads the signing regime into /opt/dualis/signing/ (stdlib-only
#      Ed25519 — the lane verifies manifests, bundles, and streams).
#   4. Downloads the cluster middleware into /opt/dualis/pull-agent/ and installs
#      the dualis-pull-agent systemd unit — the lane's own legs, outbound-only.
#   5. Writes /etc/dualis/node-id (kept), /etc/dualis/lane, /etc/dualis/version,
#      and pins the offline root pubkey at /etc/dualis/david-pubkey (C1).
#      The lane keypair is born on-lane at first breath (C2) — private key
#      0600, never leaves the box; pubkey published in the birth trace.
#   6. Clones (or pulls) the public code mirror into /opt/dualis/code.
#   7. Installs a systemd timer (every 5 min); falls back to cron if no systemd.
#   8. Runs one heartbeat immediately, then writes the BIRTH trace — the lane's
#      cluster self-registration (region, lane, version) as a claim in its own
#      attestation chain. Exactly once per lane, ever.
#   9. EUROPE lane only: installs the object-store pieces (Garage S3 binary,
#      garage.service unit, object-init/object-status/s3.py). The store itself
#      is initialized by David afterwards with: sudo object-init
#      (object-init generates and shows the credentials exactly once).
#
# What it NEVER does: no user accounts, no firewall changes, no package
# upgrades, no wiping, no inbound ports, no outbound calls except GitHub raw +
# github.com + garagehq.deuxfleurs.fr (object-store binary, EUROPE lane only) + PyPI.
# Idempotent — safe to run twice (repairs, never duplicates; the birth trace
# is written once; never touches /etc/dualis/garage.toml once object-init
# has written it).
#
# Fixture hooks (test only — never set on a real box):
#   DUALIS_PREFIX   redirect the whole install tree under this dir
#   DUALIS_FIXTURE  skip network-mutating steps (apt, code mirror, garage
#                   binary download, systemd enable/start)
#   RAW_BASE        override the download base (default: GitHub raw)
#
# Signing regime (C1): the offline root PUBLIC key is pinned HERE, at the
# one-hand moment. Public keys are public — no secrecy needed. Set
# DAVID_PUBKEY to the hex pubkey from the key ceremony BEFORE pasting;
# the bootstrap writes it to /etc/dualis/david-pubkey and the pull-agent
# verifies every manifest signature against it from then on. Empty means
# pre-ceremony: the lane runs with manifest signatures UNVERIFIED (an
# honest warning is printed and attested) until the ceremony happens.
# The expected fingerprint is carried out-of-band in the deploy doc —
# compare it to what the bootstrap prints. One glance, then paste.
DAVID_PUBKEY="${DAVID_PUBKEY:-}"
set -euo pipefail

RAW_BASE="${RAW_BASE:-https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node}"
GARAGE_URL="https://garagehq.deuxfleurs.fr/_releases/v2.0.0/x86_64-unknown-linux-musl/garage"
P="${DUALIS_PREFIX:-}"
FIXTURE="${DUALIS_FIXTURE:-}"
INSTALL_DIR="$P/opt/dualis"
NODE_DIR="$INSTALL_DIR/node"
PULL_DIR="$INSTALL_DIR/pull-agent"
STATE_DIR="$P/var/lib/dualis"
ETC_DIR="$P/etc/dualis"
BIN_DIR="$P/usr/local/bin"
SYSTEMD_DIR="$P/etc/systemd/system"
CRON_FILE="$P/etc/cron.d/dualis-heartbeat"
LANE="${1:-}"
FUSED_VERSION="v1.1.0"

export DUALIS_PREFIX="$P"
export DUALIS_STATE_DIR="$STATE_DIR"
export DUALIS_ETC_DIR="$ETC_DIR"

case "$LANE" in
  DCLM)   REGION="americas" ;;
  EUROPE) REGION="europe" ;;
  *)      REGION="unassigned" ;;
esac

if [ -z "$P" ] && [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (or with sudo)." >&2
  exit 1
fi

echo "[1/9] dependencies"
command -v python3 >/dev/null || { echo "ERROR: python3 not found." >&2; exit 1; }
if [ -z "$FIXTURE" ]; then
  if ! command -v git >/dev/null; then
    echo "  installing git..."
    apt-get update -qq && apt-get install -y -qq git
  fi
  command -v curl >/dev/null || { apt-get update -qq && apt-get install -y -qq curl; }
  if [ "$LANE" = "EUROPE" ]; then
    command -v openssl >/dev/null || { apt-get update -qq && apt-get install -y -qq openssl; }
    python3 -c "import boto3" 2>/dev/null || {
      echo "  installing pip + boto3 (object-store client)..."
      apt-get update -qq && apt-get install -y -qq python3-pip
      pip3 install --quiet boto3
    }
  fi
else
  echo "  fixture mode — apt steps skipped"
fi

echo "[2/9] directories"
mkdir -p "$NODE_DIR" "$PULL_DIR" "$STATE_DIR" "$ETC_DIR" "$BIN_DIR" "$SYSTEMD_DIR" "$(dirname "$CRON_FILE")"

echo "[3/9] node files"
for f in node-heartbeat.py swarm-status dualis-heartbeat.service dualis-heartbeat.timer attest.py swarm-merge; do
  curl -fsSL "$RAW_BASE/node/$f" -o "$NODE_DIR/$f"
done
chmod +x "$NODE_DIR/node-heartbeat.py" "$NODE_DIR/swarm-status" "$NODE_DIR/attest.py" "$NODE_DIR/swarm-merge"
cp -f "$NODE_DIR/swarm-status" "$BIN_DIR/swarm-status"
cp -f "$NODE_DIR/swarm-merge" "$BIN_DIR/swarm-merge"
chmod +x "$BIN_DIR/swarm-status" "$BIN_DIR/swarm-merge"
echo "[3b/9] signing regime (stdlib-only — the lane verifies everything)"
SIGNING_DIR="$INSTALL_DIR/signing"
mkdir -p "$SIGNING_DIR"
for f in __init__.py backend.py ed25519_pure.py keys.py envelope.py manifest.py intent.py lane.py allowlist.py orders.py; do
  curl -fsSL "$RAW_BASE/signing/$f" -o "$SIGNING_DIR/$f"
done
echo "  signing module installed at $SIGNING_DIR"
if [ "$LANE" = "EUROPE" ]; then
  for f in object-init object-status s3.py garage.service; do
    curl -fsSL "$RAW_BASE/node/$f" -o "$NODE_DIR/$f"
  done
  chmod +x "$NODE_DIR/object-init" "$NODE_DIR/object-status" "$NODE_DIR/s3.py"
  echo "  object-store files staged"
fi

echo "[4/9] cluster middleware (the lane's own legs)"
curl -fsSL "$RAW_BASE/cluster/pull-agent.py" -o "$PULL_DIR/pull-agent.py"
curl -fsSL "$RAW_BASE/cluster/dualis-pull-agent.service" -o "$PULL_DIR/dualis-pull-agent.service"
chmod +x "$PULL_DIR/pull-agent.py"
if [ -z "$FIXTURE" ] && command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  cp -f "$PULL_DIR/dualis-pull-agent.service" /etc/systemd/system/dualis-pull-agent.service
  systemctl daemon-reload
  systemctl enable --quiet dualis-pull-agent.service
  systemctl start dualis-pull-agent.service
  echo "  pull-agent installed, enabled, started (outbound-only)"
else
  cp -f "$PULL_DIR/dualis-pull-agent.service" "$SYSTEMD_DIR/dualis-pull-agent.service"
  echo "  pull-agent staged at $PULL_DIR (no systemd here — unit staged, not started)"
fi

echo "[5/9] node identity (kept if it exists)"
"$NODE_DIR/node-heartbeat.py" --init >/dev/null
if [ -n "$LANE" ]; then
  echo "$LANE" > "$ETC_DIR/lane"
  echo "  lane: $LANE (region: $REGION)"
else
  echo "  lane: (none given — pass DCLM or EUROPE as first argument)"
fi
echo "$FUSED_VERSION" > "$ETC_DIR/version"
echo "  version: $FUSED_VERSION"
if [ -n "$DAVID_PUBKEY" ]; then
  printf '%s\n' "$DAVID_PUBKEY" > "$ETC_DIR/david-pubkey"
  chmod 644 "$ETC_DIR/david-pubkey"
  FP="$(python3 -c 'import hashlib;h=hashlib.sha256(bytes.fromhex("'"$DAVID_PUBKEY"'")).hexdigest()[:16];print("-".join(h[i:i+4] for i in range(0,16,4)))')"
  echo "  offline root pubkey pinned — fingerprint: $FP"
  echo "  (compare with the deploy doc. One glance.)"
else
  echo "  WARNING: DAVID_PUBKEY not set — pre-ceremony mode."
  echo "  Manifest signatures will NOT be verified until the key ceremony."
  echo "  Run the ceremony, then re-run this bootstrap with DAVID_PUBKEY set."
fi

echo "[6/9] code mirror"
CODE_DIR="$INSTALL_DIR/code"
if [ -n "$FIXTURE" ]; then
  echo "  fixture mode — code mirror skipped"
elif [ -d "$CODE_DIR/.git" ]; then
  git -C "$CODE_DIR" pull --quiet --ff-only || true
else
  rm -rf "$CODE_DIR"
  git clone --quiet --depth 1 https://github.com/digenova77-ui/efuse-unity.git "$CODE_DIR" || {
    echo "  WARNING: code mirror failed (network?) — node still works without it." >&2
  }
fi

echo "[7/9] scheduler"
if [ -z "$FIXTURE" ] && command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  cp -f "$NODE_DIR/dualis-heartbeat.service" /etc/systemd/system/dualis-heartbeat.service
  cp -f "$NODE_DIR/dualis-heartbeat.timer" /etc/systemd/system/dualis-heartbeat.timer
  systemctl daemon-reload
  systemctl enable --quiet dualis-heartbeat.timer
  systemctl start dualis-heartbeat.timer
  echo "  systemd timer installed and started"
else
  printf '%s\n' "*/5 * * * * root /usr/bin/python3 $NODE_DIR/node-heartbeat.py >/dev/null 2>&1" \
    > "$CRON_FILE"
  chmod 644 "$CRON_FILE"
  echo "  no systemd — cron fallback installed (every 5 min)"
fi

echo "[8/9] first heartbeat + birth trace (cluster self-registration)"
if [ -n "$LANE" ]; then
  DUALIS_LANE="$LANE" "$NODE_DIR/node-heartbeat.py" >/dev/null
else
  "$NODE_DIR/node-heartbeat.py" >/dev/null
fi
echo "  heartbeat ticked"
if [ -f "$ETC_DIR/born" ]; then
  echo "  already born — birth trace exists, not duplicated"
else
  BIRTH_NOTE="$(python3 -c 'import json,sys; print(json.dumps({"event":"birth","region":sys.argv[1],"lane":sys.argv[2],"version":sys.argv[3],"streams":["heartbeat.jsonl","attestations.jsonl"],"cluster_node":"qnode-cluster-ingress"}, separators=(",",":")))' "$REGION" "${LANE:-unset}" "$FUSED_VERSION")"
  DUALIS_LANE="${LANE:-}" "$NODE_DIR/attest.py" --shift-id birth \
    --claims cluster-registration --note "$BIRTH_NOTE" >/dev/null
  date -u +%Y-%m-%dT%H:%M:%SZ > "$ETC_DIR/born"
  echo "  birth trace written — lane registered as a cluster citizen (region: $REGION)"
fi

if [ "$LANE" = "EUROPE" ]; then
  echo "[9/9] object store install (EUROPE lane)"
  if [ -n "$FIXTURE" ]; then
    echo "  fixture mode — garage binary download deferred (files staged above)"
  elif [ ! -x /usr/local/bin/garage ] || ! /usr/local/bin/garage --version >/dev/null 2>&1; then
    echo "  downloading garage v2.0.0..."
    curl -fsSL "$GARAGE_URL" -o /tmp/garage-bin
    chmod +x /tmp/garage-bin
    /tmp/garage-bin --version || { echo "ERROR: garage binary failed to run." >&2; exit 1; }
    mv -f /tmp/garage-bin /usr/local/bin/garage
  else
    echo "  garage binary already present: $(/usr/local/bin/garage --version | head -1)"
  fi
  if [ -z "$FIXTURE" ]; then
    cp -f "$NODE_DIR/garage.service" /etc/systemd/system/garage.service
    cp -f "$NODE_DIR/object-init" /usr/local/bin/object-init
    cp -f "$NODE_DIR/object-status" /usr/local/bin/object-status
    cp -f "$NODE_DIR/s3.py" /usr/local/bin/s3.py
    chmod +x /usr/local/bin/object-init /usr/local/bin/object-status /usr/local/bin/s3.py
    systemctl daemon-reload 2>/dev/null || true
    echo "  garage installed (service NOT started — David initializes it next)."
    echo "  NEXT STEP: sudo object-init"
  else
    echo "  fixture mode — unit/bin installs deferred"
  fi
else
  echo "[9/9] object store: skipped (EUROPE lane only — this box is lane ${LANE:-unset})"
fi
echo
echo "== swarm node live — born a cluster citizen =="
"$BIN_DIR/swarm-status"
