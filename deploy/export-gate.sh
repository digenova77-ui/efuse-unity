#!/usr/bin/env bash
# export-gate.sh — export the entry gate flow to the website.
# Run AFTER the gate builder worker completes.
set -euo pipefail
cd ~/workspace/unity-world

echo "=== 1. Validate client (gate included) ==="
cd client && node validate-client.mjs
echo "client validation passed"

echo "=== 2. Verify gate files ==="
cd ~/workspace/unity-world
for f in client/index.html client/client.js founding-board/founding-board.json; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
  echo "ok: $f ($(sha256sum "$f" | cut -d' ' -f1 | head -c 16)…)"
done

echo "=== 3. Pin to IPFS ==="
cd ~/workspace
CID=$(python3 skills/pinata/bin/pin_dir.py unity-world/client "unity-world-gate-$(date +%Y%m%d-%H%M)" | python3 -c "import json,sys; print(json.load(sys.stdin)['cid'])")
echo "pinned: $CID"

echo "=== 4. Update worker CIDS ==="
python3 -c "
import re
p = 'cloudflare/dccp-gateway-worker.js'
s = open(p).read()
s = re.sub(r'\"world-v2\": \"[^\"]+\"', '\"world-v2\": \"$CID\"', s)
open(p,'w').write(s)
print('worker CIDS updated')
"

echo ""
echo "=== READY FOR CLOUDFLARE PUSH ==="
echo "CID: $CID"
echo "David: deploy the updated worker via Cloudflare dashboard."
echo "Verify: https://dualiscapax.ai/ shows the gate card."
