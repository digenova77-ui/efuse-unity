/**
 * Dry-run quoter for an Arweave Turbo seal of the Omni/frontier snapshot.
 * Builds the snapshot, prints byte size, fetches Turbo price.
 * Does not sign. Does not upload. No key required.
 *
 * Usage: node edge/seal_turbo.mjs
 */
import { omniSnapshot, frontierReport, DEFAULT_FACETS, standingProbe } from "./diamond_edge.js";

const snapshot = {
  omni: omniSnapshot(DEFAULT_FACETS),
  frontier: frontierReport(DEFAULT_FACETS),
  standing: standingProbe(),
  note: "pure edge snapshot — NOT_FOR_EMISSION",
  protocol: "DIAMOND.STORAGE.v1",
  ts: new Date().toISOString(),
};

const body = JSON.stringify(snapshot);
const bytes = Buffer.byteLength(body);
console.log("bytes", bytes);

let price = null;
try {
  const res = await fetch(`https://turbo.ardrive.io/price/arweave/${bytes}`);
  price = await res.json();
  console.log("turbo_price", JSON.stringify(price));
} catch (e) {
  console.log("turbo_price", "unavailable", String(e.message || e));
}

const freeTier = bytes <= 105 * 1024;
console.log(JSON.stringify({
  protocol: "DIAMOND.STORAGE.v1",
  layer: "sealed",
  door: "Turbo",
  bytes,
  under_105kib: freeTier,
  note: "quote only — no upload",
  boundary: "NOT_FOR_EMISSION",
}, null, 2));
