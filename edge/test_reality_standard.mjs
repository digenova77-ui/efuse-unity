import { claim, protocolReality, REALITY } from "./reality_standard.js";

let failed = 0;
const assert = (c, m) => { if (!c) { console.error("FAIL", m); failed++; } else console.log("ok", m); };

assert(REALITY === "REALITY.v1", "id");
assert(claim("x", "NOPE").ok === false, "bad grade refused");
assert(claim("E", "HELD").pass === false, "held not pass");
assert(claim("cube", "HYPOTHETICAL").pass === false, "hypothetical not pass");
assert(claim("quote", "MEASURED").ok === false, "measured needs evidence");
assert(claim("quote", "MEASURED", "1320 bytes").pass === true, "measured with evidence");
assert(claim("live", "DEPLOYED").ok === false, "deployed needs evidence");

const r = protocolReality();
assert(r.claims.some((c) => c.grade === "HELD" && c.statement.includes("E")), "E held");
assert(r.claims.some((c) => c.grade === "HYPOTHETICAL" && c.statement.includes("Pages")), "deploy hypothetical");
assert(r.claims.filter((c) => c.pass).every((c) => c.grade === "MEASURED" || c.grade === "DEPLOYED"), "pass only measured/deployed");
assert(r.boundary === "NOT_FOR_EMISSION", "boundary");

if (failed) process.exit(1);
console.log("reality ok");
