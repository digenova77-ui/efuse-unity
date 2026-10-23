#!/bin/sh
# Usage: PINATA_JWT=... ./edge/pin_elsewhere.sh
# Pins via Pinata, prints CID, reminds to pin elsewhere.
set -e
cd "$(dirname "$0")/.."
node edge/pin_snapshot.mjs > /tmp/omni-frontier.json
if [ -z "$PINATA_JWT" ]; then
  echo "PINATA_JWT not set. Snapshot written to /tmp/omni-frontier.json"
  echo "Pin it with any IPFS node: ipfs add /tmp/omni-frontier.json"
  exit 0
fi
# Caller can POST; this script only prepares and instructs.
echo "Snapshot ready: /tmp/omni-frontier.json"
echo "1. Pin with Pinata (scripts/pin-pinata.mjs --pin) or:"
echo "   curl -X POST https://api.pinata.cloud/pinning/pinJSONToIPFS -H \"Authorization: Bearer \$PINATA_JWT\" -H \"Content-Type: application/json\" -d @/tmp/omni-frontier.json"
echo "2. On a second node: ipfs pin add <CID>"
echo "3. Update IPNS to <CID>"
