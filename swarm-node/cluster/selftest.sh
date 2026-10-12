#!/usr/bin/env bash
# Bundle self-test — run by pull-agent.py inside the staging dir before apply.
# Exit 0 = the bundle may be applied. This runs ON the lane, hermetic:
# it never touches the live /opt/dualis or /etc/dualis trees.
set -euo pipefail

echo "[selftest] compiling python files"
python3 -m py_compile node/attest.py node/node-heartbeat.py pull-agent/pull-agent.py

echo "[selftest] checking expected files"
for f in node/node-heartbeat.py node/attest.py node/swarm-merge node/swarm-status \
         node/dualis-heartbeat.service node/dualis-heartbeat.timer \
         pull-agent/pull-agent.py dualis-pull-agent.service; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done

echo "[selftest] chain verify on empty fixture state"
FIXTURE_STATE="$(mktemp -d)"
FIXTURE_ETC="$(mktemp -d)"
DUALIS_STATE_DIR="$FIXTURE_STATE" DUALIS_ETC_DIR="$FIXTURE_ETC" \
  python3 node/attest.py --verify
rm -rf "$FIXTURE_STATE" "$FIXTURE_ETC"

echo "[selftest] OK"
