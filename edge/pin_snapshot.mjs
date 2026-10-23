/**
 * Emit Omni/frontier snapshot JSON for pinning.
 * Usage: node edge/pin_snapshot.mjs > /tmp/omni.json
 * Then pin with existing pinata-pin workflow or:
 *   curl -X POST https://api.pinata.cloud/pinning/pinJSONToIPFS \
 *        -H "Authorization: Bearer $PINATA_JWT" \
 *        -H "Content-Type: application/json" \
 *        -d @/tmp/omni.json
 */
import { omniSnapshot, frontierReport, DEFAULT_FACETS, standingProbe } from "./diamond_edge.js";

const snapshot = {
  omni: omniSnapshot(DEFAULT_FACETS),
  frontier: frontierReport(DEFAULT_FACETS),
  standing: standingProbe(),
  note: "pure edge snapshot — NOT_FOR_EMISSION",
};
process.stdout.write(JSON.stringify(snapshot, null, 2) + "\n");
