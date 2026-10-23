import { classify, readyToName, protocolReport, PROTOCOL } from "./diamond_storage_protocol.js";

let failed = 0;
const assert = (c, m) => { if (!c) { console.error("FAIL", m); failed++; } else console.log("ok", m); };

assert(PROTOCOL === "DIAMOND.STORAGE.v1", "protocol id");
assert(classify({ kind: "snapshot" }).layer === "living", "snapshot is living");
assert(classify({ kind: "seal" }).action === "turbo-upload", "seal goes turbo");
assert(classify({ immutable: true }).layer === "sealed", "immutable sealed");
assert(readyToName(["pinata"]).ok === false, "one pin not enough");
assert(readyToName(["pinata", "storacha"]).ok === true, "two pins ok");
const r = protocolReport();
assert(r.law === "LAW WINS", "law");
assert(r.boundary === "NOT_FOR_EMISSION", "boundary");
assert(r.rules.length >= 5, "rules present");

if (failed) process.exit(1);
console.log("storage protocol ok");
