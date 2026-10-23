/**
 * Pure diamond / frontier / Omni edge module.
 * Matches playground/diamond_playground.py and frontier_protocol.py.
 * No I/O. Safe for Cloudflare Workers or browser.
 *
 * Pass bands (playground):
 *   clarity ∈ {FL, VVS, VS}
 *   color   ∈ {D, E, F}
 *   cut     ∈ {Excellent, Very Good}
 *   reflects === "purity"
 *
 * Frontier (maximum):
 *   clarity === "FL" && color === "D" && cut === "Excellent" && reflects === "purity"
 */
export const CLARITY_PASS = new Set(["FL", "VVS", "VS"]);
export const COLOR_PASS = new Set(["D", "E", "F"]);
export const CUT_PASS = new Set(["Excellent", "Very Good"]);
export const MAX_BAND = { clarity: "FL", color: "D", cut: "Excellent" };

export function grade(f) {
  const clarity_ok = CLARITY_PASS.has(f.clarity);
  const color_ok = COLOR_PASS.has(f.color);
  const cut_ok = CUT_PASS.has(f.cut);
  const reflects_ok = f.reflects === "purity";
  const pure = clarity_ok && color_ok && cut_ok && reflects_ok;
  const failed = [];
  if (!clarity_ok) failed.push(`clarity:${f.clarity}`);
  if (!color_ok) failed.push(`color:${f.color}`);
  if (!cut_ok) failed.push(`cut:${f.cut}`);
  if (!reflects_ok) failed.push("reflects:not-purity");
  return {
    pure,
    verdict: pure ? "PASS" : "GLASS",
    failed,
    clarity: { value: f.clarity, pass: clarity_ok },
    color: { value: f.color, pass: color_ok },
    cut: { value: f.cut, pass: cut_ok },
  };
}

export function facesFrontier(f) {
  return (
    f.clarity === MAX_BAND.clarity &&
    f.color === MAX_BAND.color &&
    f.cut === MAX_BAND.cut &&
    f.reflects === "purity"
  );
}

export function frontierReport(facets) {
  const facing = [];
  const held = [];
  for (const f of facets) {
    if (f.kind === "ceiling") continue;
    if (facesFrontier(f)) facing.push(f.name);
    else held.push({ name: f.name, clarity: f.clarity, color: f.color, cut: f.cut });
  }
  const floor = facets.find((f) => f.kind === "floor");
  const floorHolds = floor ? grade(floor).pure : false;
  return {
    protocol: "DIAMOND.FRONTIER.MAX.v1",
    facing,
    held,
    ceiling_claimable: held.length === 0 && floorHolds,
    law: "LAW WINS",
    origin: "immutable",
    learning: "advisory only — NOT_FOR_EMISSION",
  };
}

export function omniSnapshot(facets) {
  const g = facets.filter((f) => f.kind !== "ceiling").map((f) => ({
    name: f.name,
    verdict: grade(f).verdict,
  }));
  const fr = frontierReport(facets);
  const floor = facets.find((f) => f.kind === "floor");
  const glass = g.some((x) => x.verdict === "GLASS");
  return {
    label: "OMNI",
    diamond: {
      floor_holds: floor ? grade(floor).pure : false,
      rise_ok: !glass && (floor ? grade(floor).pure : false),
      ceiling_reached: !glass && (floor ? grade(floor).pure : false),
      facets: g,
    },
    frontier: {
      protocol: fr.protocol,
      facing: fr.facing,
      held_count: fr.held.length,
      ceiling_claimable: fr.ceiling_claimable,
    },
    contract: {
      law: "LAW WINS",
      origin: "immutable",
      boundary: "NOT_FOR_EMISSION",
    },
    integrity: "UNCHANGED — core not touched",
  };
}

/** Default playground facets (matches Python DiamondPlayground). */
export const DEFAULT_FACETS = [
  { name: "foundation", kind: "floor", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "DCLM", kind: "ring", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "Iris", kind: "ring", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "Twain²", kind: "ring", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "summer", kind: "tree", clarity: "VS", color: "E", cut: "Very Good", reflects: "purity" },
  { name: "winter", kind: "tree", clarity: "VS", color: "F", cut: "Very Good", reflects: "purity" },
  { name: "merit", kind: "economy", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "standing", kind: "economy", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
  { name: "ceiling", kind: "ceiling", clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" },
];


/** Append-only receipt chain check. Pure. */
export function verifyReceiptChain(receipts) {
  if (!Array.isArray(receipts) || receipts.length === 0) {
    return { ok: true, length: 0, reason: "empty" };
  }
  for (let i = 1; i < receipts.length; i++) {
    const prev = receipts[i - 1];
    const cur = receipts[i];
    if (!cur || !cur.id || !cur.id.startsWith("rcpt:")) {
      return { ok: false, length: i, reason: "bad id" };
    }
    if (cur.prev !== prev.id) {
      return { ok: false, length: i, reason: "prev mismatch" };
    }
  }
  return { ok: true, length: receipts.length, last: receipts[receipts.length - 1].id };
}

/** Read-only standing probe. Does not emit. */
export function standingProbe() {
  return {
    standing_callable: true,
    emission_source: "standing() — origin only",
    boundary: "NOT_FOR_EMISSION",
    note: "edge probe; live token_engine not imported here",
  };
}
