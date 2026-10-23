import { grade, facesFrontier, frontierReport, omniSnapshot, DEFAULT_FACETS } from "./diamond_edge.js";

let failed = 0;
function assert(cond, msg) {
  if (!cond) { console.error("FAIL:", msg); failed++; }
  else console.log("ok:", msg);
}

const max = { clarity: "FL", color: "D", cut: "Excellent", reflects: "purity" };
assert(grade(max).pure === true, "max is pure");
assert(facesFrontier(max) === true, "max faces frontier");

const soft = { clarity: "VS", color: "E", cut: "Very Good", reflects: "purity" };
assert(grade(soft).pure === true, "soft passes old gate");
assert(facesFrontier(soft) === false, "soft held by frontier");

const bad = { clarity: "SI2", color: "J", cut: "Fair", reflects: "theater" };
assert(grade(bad).pure === false, "bad is glass");
assert(grade(bad).failed.includes("clarity:SI2"), "names clarity");
assert(grade(bad).failed.includes("color:J"), "names color");

const fr = frontierReport(DEFAULT_FACETS);
assert(fr.facing.includes("foundation"), "foundation facing");
assert(fr.held.some((h) => h.name === "summer"), "summer held");
assert(fr.ceiling_claimable === false, "ceiling not claimable with held");
assert(fr.law === "LAW WINS", "law present");

const o = omniSnapshot(DEFAULT_FACETS);
assert(o.label === "OMNI", "omni label");
assert(o.diamond.floor_holds === true, "floor holds");
assert(o.frontier.held_count === 2, "two held");
assert(o.contract.boundary === "NOT_FOR_EMISSION", "boundary");

if (failed) { console.error(failed, "failed"); process.exit(1); }
console.log("all edge tests passed");

import { verifyReceiptChain, standingProbe } from "./diamond_edge.js";

const chain = [
  { id: "rcpt:aaa", prev: null },
  { id: "rcpt:bbb", prev: "rcpt:aaa" },
  { id: "rcpt:ccc", prev: "rcpt:bbb" },
];
assert(verifyReceiptChain(chain).ok === true, "chain ok");
assert(verifyReceiptChain([{ id: "rcpt:x", prev: "nope" }, { id: "rcpt:y", prev: "other" }]).ok === false, "chain break");
const sp = standingProbe();
assert(sp.boundary === "NOT_FOR_EMISSION", "probe boundary");
assert(sp.emission_source.includes("origin"), "probe origin");
