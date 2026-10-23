/**
 * DIAMOND.STORAGE.v1
 * Best-architecture storage protocol for dualiscapax artifacts.
 *
 * Living  → IPFS, two pins (Pinata + Storacha/self), name via IPNS or DNSLink
 * Sealed  → Arweave via Turbo (endowment). One tx per seal. Never overwrite.
 * Compute → Cloudflare Worker. Storage does not execute gates.
 * Boundary → NOT_FOR_EMISSION. LAW WINS. Origin immutable.
 */
export const PROTOCOL = "DIAMOND.STORAGE.v1";

export const LAYERS = {
  living: {
    network: "IPFS",
    pins: ["pinata", "storacha-or-self"],
    name: "IPNS-or-DNSLink",
    retrieval: ["pinata-dedicated-gateway", "cloudflare"],
    updates: "new CID, move name",
  },
  sealed: {
    network: "Arweave",
    door: "Turbo",
    model: "endowment",
    updates: "new transaction only",
  },
  compute: {
    network: "Cloudflare-Worker",
    routes: ["/omni", "/frontier", "/purity", "/standing-probe", "/receipts/verify"],
    note: "does not replace pins or seals",
  },
};

export const RULES = [
  "Living snapshot is pinned in at least two places before IPNS/DNSLink moves.",
  "Seal only a version that will not be rewritten. One Arweave tx per seal.",
  "Media that is streamed is served from Pinata gateway or Cloudflare, not from Arweave.",
  "Public ipfs.io is not a production retrieval path.",
  "Storage never emits, never changes standing, never overrides LAW WINS.",
  "Irys L1 is not a substitute for an Arweave seal.",
];

export function classify(artifact) {
  const kind = artifact.kind || "living";
  if (kind === "seal" || artifact.immutable === true) {
    return { layer: "sealed", action: "turbo-upload", protocol: PROTOCOL };
  }
  return { layer: "living", action: "pinata-then-second-pin", protocol: PROTOCOL };
}

export function readyToName(pins) {
  const n = Array.isArray(pins) ? pins.filter(Boolean).length : 0;
  return { ok: n >= 2, pins: n, reason: n >= 2 ? "two pins" : "need second pin" };
}

export function protocolReport() {
  return {
    protocol: PROTOCOL,
    layers: LAYERS,
    rules: RULES,
    law: "LAW WINS",
    origin: "immutable",
    boundary: "NOT_FOR_EMISSION",
  };
}
