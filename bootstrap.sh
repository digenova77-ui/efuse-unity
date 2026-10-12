#!/usr/bin/env bash
# DualisCapax swarm node bootstrap — pull-based, idempotent, non-destructive.
#
# Run ONCE per server (safe to run twice — it repairs, never wipes):
#   curl -fsSL https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node/bootstrap.sh | sudo bash -s -- DCLM
# (lane label is the first argument: DCLM on the NJ box, EUROPE on the Amsterdam box)
#
# Two lanes, not a relay: each box runs its own loop autonomously. Lanes
# exchange ONLY hash-chained attestations (see node/attest.py); the merge
# happens asynchronously via node/swarm-merge. If a lane goes dark, the other
# keeps working — the loop degrades to one lane, never halts.
#
# What it does:
#   1. Checks python3 (Ubuntu 22.04 ships it); installs git if missing.
#   2. Creates /opt/dualis, /var/lib/dualis, /etc/dualis (never touches anything else).
#   3. Downloads the node files into /opt/dualis/node/ (overwrites only our own files).
#   4. Installs /usr/local/bin/swarm-status.
#   5. Clones (or pulls) the public code mirror into /opt/dualis/code.
#   6. Installs a systemd timer (every 5 min); falls back to cron if no systemd.
#   7. Runs one heartbeat immediately and prints swarm-status.
#   8. EUROPE lane only: installs the object-store pieces (Garage S3 binary,
#      garage.service unit, object-init/object-status/s3.py). The store itself
#      is initialized by David afterwards with: sudo object-init
#      (object-init generates and shows the credentials exactly once).
#
# What it NEVER does: no user accounts, no firewall changes, no package
# upgrades, no wiping, no outbound calls except GitHub raw + github.com +
# garagehq.deuxfleurs.fr (object-store binary, EUROPE lane only) + PyPI.
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/digenova77-ui/efuse-unity/main/swarm-node"
GARAGE_URL="https://garagehq.deuxfleurs.fr/_releases/v2.0.0/x86_64-unknown-linux-musl/garage"
INSTALL_DIR="/opt/dualis"
NODE_DIR="$INSTALL_DIR/node"
STATE_DIR="/var/lib/dualis"
CODE_DIR="$INSTALL_DIR/code"
LANE="${1:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (or with sudo)." >&2
  exit 1
fi

echo "[1/8] dependencies"
command -v python3 >/dev/null || { echo "ERROR: python3 not found." >&2; exit 1; }
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

echo "[2/8] directories"
mkdir -p "$NODE_DIR" "$STATE_DIR" /etc/dualis /usr/local/bin

echo "[3/8] node files"
for f in node-heartbeat.py swarm-status dualis-heartbeat.service dualis-heartbeat.timer attest.py swarm-merge; do
  curl -fsSL "$RAW_BASE/node/$f" -o "$NODE_DIR/$f"
done
chmod +x "$NODE_DIR/node-heartbeat.py" "$NODE_DIR/swarm-status" "$NODE_DIR/attest.py" "$NODE_DIR/swarm-merge"
cp -f "$NODE_DIR/swarm-status" /usr/local/bin/swarm-status
cp -f "$NODE_DIR/swarm-merge" /usr/local/bin/swarm-merge
chmod +x /usr/local/bin/swarm-status /usr/local/bin/swarm-merge
if [ "$LANE" = "EUROPE" ]; then
  for f in object-init object-status s3.py garage.service; do
    curl -fsSL "$RAW_BASE/node/$f" -o "$NODE_DIR/$f"
  done
  chmod +x "$NODE_DIR/object-init" "$NODE_DIR/object-status" "$NODE_DIR/s3.py"
  echo "  object-store files staged"
fi

echo "[4/8] node identity (kept if it exists)"
"$NODE_DIR/node-heartbeat.py" --init >/dev/null
if [ -n "$LANE" ]; then
  echo "$LANE" > /etc/dualis/lane
  echo "  lane: $LANE"
else
  echo "  lane: (none given — pass DCLM or EUROPE as first argument)"
fi

echo "[5/8] code mirror"
if [ -d "$CODE_DIR/.git" ]; then
  git -C "$CODE_DIR" pull --quiet --ff-only || true
else
  rm -rf "$CODE_DIR"
  git clone --quiet --depth 1 https://github.com/digenova77-ui/efuse-unity.git "$CODE_DIR" || {
    echo "  WARNING: code mirror failed (network?) — node still works without it." >&2
  }
fi

echo "[6/8] scheduler"
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  cp -f "$NODE_DIR/dualis-heartbeat.service" /etc/systemd/system/dualis-heartbeat.service
  cp -f "$NODE_DIR/dualis-heartbeat.timer" /etc/systemd/system/dualis-heartbeat.timer
  systemctl daemon-reload
  systemctl enable --quiet dualis-heartbeat.timer
  systemctl start dualis-heartbeat.timer
  echo "  systemd timer installed and started"
else
  printf '%s\n' "*/5 * * * * root /usr/bin/python3 /opt/dualis/node/node-heartbeat.py >/dev/null 2>&1" \
    > /etc/cron.d/dualis-heartbeat
  chmod 644 /etc/cron.d/dualis-heartbeat
  echo "  no systemd — cron fallback installed (every 5 min)"
fi

echo "[7/8] first heartbeat"
if [ -n "$LANE" ]; then
  DUALIS_LANE="$LANE" "$NODE_DIR/node-heartbeat.py"
else
  "$NODE_DIR/node-heartbeat.py"
fi

if [ "$LANE" = "EUROPE" ]; then
  echo "[8/8] object store install (EUROPE lane)"
  if [ ! -x /usr/local/bin/garage ] || ! /usr/local/bin/garage --version >/dev/null 2>&1; then
    echo "  downloading garage v2.0.0..."
    curl -fsSL "$GARAGE_URL" -o /tmp/garage-bin
    chmod +x /tmp/garage-bin
    /tmp/garage-bin --version || { echo "ERROR: garage binary failed to run." >&2; exit 1; }
    mv -f /tmp/garage-bin /usr/local/bin/garage
  else
    echo "  garage binary already present: $(/usr/local/bin/garage --version | head -1)"
  fi
  cp -f "$NODE_DIR/garage.service" /etc/systemd/system/garage.service
  cp -f "$NODE_DIR/object-init" /usr/local/bin/object-init
  cp -f "$NODE_DIR/object-status" /usr/local/bin/object-status
  cp -f "$NODE_DIR/s3.py" /usr/local/bin/s3.py
  chmod +x /usr/local/bin/object-init /usr/local/bin/object-status /usr/local/bin/s3.py
  systemctl daemon-reload 2>/dev/null || true
  echo "  garage installed (service NOT started — David initializes it next)."
  echo "  NEXT STEP: sudo object-init"
else
  echo "[8/8] object store: skipped (EUROPE lane only — this box is lane ${LANE:-unset})"
fi
echo
echo "== swarm node live =="
swarm-status
