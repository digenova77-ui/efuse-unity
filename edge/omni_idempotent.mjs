/**
 * Omni idempotency gate.
 * Runs reality report. Fails if any PASS claim lacks evidence.
 * Prints the report. Exit 0 only when the gate holds.
 */
import { protocolReality } from "./reality_standard.js";

const r = protocolReality();
let bad = 0;
for (const c of r.claims) {
  if (c.pass && !c.evidence) {
    console.error("PASS without evidence:", c.statement);
    bad++;
  }
  if (c.pass && c.grade !== "MEASURED" && c.grade !== "DEPLOYED") {
    console.error("PASS on non-real grade:", c.statement, c.grade);
    bad++;
  }
}
console.log(JSON.stringify(r, null, 2));
if (bad) {
  console.error("omni idempotency FAIL", bad);
  process.exit(1);
}
console.log("omni idempotency OK");
