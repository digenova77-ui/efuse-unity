import { architectureReport, admit, ARCH, FLOOR } from "./diamond_architecture.js";

let failed = 0;
const assert = (c, m) => { if (!c) { console.error("FAIL", m); failed++; } else console.log("ok", m); };

assert(ARCH === "DIAMOND.ARCHITECTURE.v1", "id");
assert(FLOOR.law === "LAW WINS", "law");
assert(FLOOR.E === "HELD", "E held");
assert(FLOOR.boundary === "NOT_FOR_EMISSION", "boundary");

const one = architectureReport(undefined, ["pinata"]);
assert(one.ceiling.name_ready === false, "one pin blocks name");
assert(one.ceiling.claimable === false, "not claimable on one pin");

const two = architectureReport(undefined, ["pinata", "storacha"]);
assert(two.ceiling.name_ready === true, "two pins ready");
// default facets hold summer/winter → frontier not claimable
assert(two.ceiling.frontier_claimable === false, "default held");
assert(two.ceiling.claimable === false, "ceiling refused while held");

const seal = admit({ kind: "seal" });
assert(seal.storage.layer === "sealed", "seal layer");
assert(seal.storage.action === "turbo-upload", "seal action");
assert(seal.boundary === "NOT_FOR_EMISSION", "admit boundary");

const live = admit({ kind: "snapshot" });
assert(live.storage.layer === "living", "snapshot living");

if (failed) process.exit(1);
console.log("architecture ok");
