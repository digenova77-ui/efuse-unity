/**
 * DIAMOND.ARCHITECTURE.v1
 * One composition of the layers already built.
 *
 * Floor   — law, origin, NOT_FOR_EMISSION
 * Mesh    — diamond gate, frontier, storage protocol, energy ratio (held)
 * Ceiling — claimable only at maximum band and two pins before a name move
 */
export const ARCH = "DIAMOND.ARCHITECTURE.v1";

export const FLOOR = {
  law: "LAW WINS",
  origin: "immutable",
  boundary: "NOT_FOR_EMISSION",
  decision_price: "PRICE_COMPUTE=5 test-keys",
  peg: "eFuse = merit / E",
  E: "HELD",
};

export const MESH = {
  gate: "clarity∈{FL,VVS,VS} ∧ color∈{D,E,F} ∧ cut∈{Excellent,Very Good} ∧ reflects=purity",
  frontier: "FL ∧ D ∧ Excellent ∧ purity",
  storage_living: "IPFS · two pins · then IPNS/DNSLink",
  storage_sealed: "Arweave via Turbo · one tx · no overwrite",
  compute: "Cloudflare Worker",
  usd: "label only · not a bill",
};

export const CEILING = {
  claimable_iff: "floor holds ∧ nothing held ∧ (name move only after two pins)",
};

import { grade, facesFrontier, frontierReport, DEFAULT_FACETS } from "./diamond_edge.js";
import { classify, readyToName, PROTOCOL as STORAGE } from "./diamond_storage_protocol.js";
import { protocolReality } from "./reality_standard.js";

export function architectureReport(facets = DEFAULT_FACETS, pins = []) {
  const fr = frontierReport(facets);
  const nameReady = readyToName(pins);
  return {
    arch: ARCH,
    storage: STORAGE,
    floor: FLOOR,
    mesh: MESH,
    ceiling: {
      ...CEILING,
      frontier_claimable: fr.ceiling_claimable,
      facing: fr.facing,
      held: fr.held,
      name_ready: nameReady.ok,
      claimable: fr.ceiling_claimable && nameReady.ok,
    },
    integrity: "UNCHANGED — core not touched",
    reality: protocolReality(),
  };
}

export function admit(artifact, facets = DEFAULT_FACETS) {
  const storage = classify(artifact);
  const sample = facets.find((f) => f.kind !== "ceiling") || facets[0];
  return {
    storage,
    gate: grade(sample).verdict,
    frontier: facesFrontier(sample),
    boundary: "NOT_FOR_EMISSION",
  };
}
