/**
 * End-to-end entry-gate test: the REAL DCLM ceremony output, through the
 * REAL client entry flow.
 *
 * 1. Runs gate/entry.py's perform_entry (testnet, temp state dir, TEST STUB
 *    verifier) via a python driver and captures the real JSON envelope.
 * 2. Serves it from a mock fetch as the serving layer would:
 *    { ok: true, entry: <envelope> } on POST /api/world/bind.
 * 3. Drives the real client.performEntry() against a fake document.
 * 4. Asserts the doorway behaves: covenant + ceremony posted, wallet shows
 *    the server's BOUND state, receipts render, the ignition plays, the card
 *    is gone afterwards.
 *
 * Also covers the refusal path and the unreachable-server path.
 *
 * Run: node test_entry_client.mjs  (from this directory)
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const client = await import(path.join(HERE, "..", "client", "client.js"));

let passed = 0, failed = 0;
const failures = [];
function check(name, cond, extra = "") {
  if (cond) { passed++; }
  else { failed++; failures.push(name + (extra ? " — " + extra : "")); }
}

/* ---------- the python driver: real DCLM, real ceremony ---------------- */
const DRIVER = `
import importlib.util, json, sys
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m
gate_dir = sys.argv[1]; state_dir = sys.argv[2]
gate_mod = load("e2e_gate", gate_dir + "/gate.py")
entry_mod = load("e2e_entry", gate_dir + "/entry.py")
def stub(identity, proof):  # TEST STUB — simulated device ceremony only
    return gate_mod.VerificationResult(status="VERIFIED", detail="test stub")
gate = gate_mod.UnityGate(state_dir=state_dir)
proof = {"kind": "testnet-stub", "testnet_ceremony": True,
         "stub_seed": "cf" * 32}
res = entry_mod.perform_entry(True, proof, verifier=stub, gate=gate)
print(json.dumps(res))
`;

function realEntryEnvelope() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "unity-e2e-"));
  const driver = path.join(tmp, "driver.py");
  fs.writeFileSync(driver, DRIVER);
  try {
    const out = execFileSync("python3", [driver, HERE, tmp], { encoding: "utf8", timeout: 60000 });
    return { envelope: JSON.parse(out), tmp };
  } finally {
    fs.rmSync(driver, { force: true });
  }
}

/* ---------- a minimal fake document ------------------------------------- */
function fakeEl() {
  return {
    textContent: "", innerHTML: "", hidden: false, value: "",
    style: {}, dataset: {},
    classList: { add() {}, remove() {} },
    scrollIntoView() {},
    addEventListener() {},
  };
}
function fakeDoc() {
  const els = {};
  return { getElementById: (id) => els[id] || (els[id] = fakeEl()), _els: els };
}

/* ================= 1. happy path: real envelope, real client ============ */
{
  const { envelope, tmp } = realEntryEnvelope();
  check("e2e: DCLM performed the ceremony", envelope.ok === true, JSON.stringify(envelope).slice(0, 200));
  const displayId = envelope.obfuscated_display;

  let postedBody = null;
  const fetchFn = async (url, opts) => {
    if (url.includes("/api/world/bind") && opts.method === "POST") {
      postedBody = JSON.parse(opts.body);
      return { json: async () => ({ ok: true, entry: envelope }) };
    }
    throw new Error("unexpected request " + url);
  };
  const doc = fakeDoc();
  const r = await client.performEntry(doc, fetchFn);

  check("e2e: client posted covenant acceptance",
    postedBody && postedBody.covenant_accepted === true);
  check("e2e: client posted ceremony material, never an identity",
    postedBody && postedBody.ceremony && postedBody.ceremony.kind === "testnet-stub" &&
    !("identity" in postedBody) && !("unity_id" in postedBody));
  check("e2e: wallet shows the server's BOUND state",
    doc.getElementById("wallet-state").innerHTML.includes("BOUND"));
  check("e2e: wallet shows the DCLM-derived obfuscated ID",
    doc.getElementById("wallet-id").innerHTML.includes(displayId));
  check("e2e: entry receipts rendered",
    doc.getElementById("entry-receipts").innerHTML.includes(envelope.seed.seed_id.slice(0, 16)));
  check("e2e: ignition carried the obfuscated ID",
    doc.getElementById("ignition-unity-id").textContent === displayId);
  check("e2e: the card is gone after ignition (doorway, not destination)",
    doc.getElementById("entry-gate").style.display === "none");
  check("e2e: performEntry resolved ok", r.ok === true);
  fs.rmSync(tmp, { recursive: true, force: true });
}

/* ================= 2. refusal path ======================================= */
{
  const fetchFn = async (url, opts) => {
    if (url.includes("/api/world/bind")) {
      return { json: async () => ({ ok: false, refused: { reason: "COVENANT_NOT_ACCEPTED", detail: "no", at_step: "covenant" } }) };
    }
    throw new Error("unexpected request " + url);
  };
  const doc = fakeDoc();
  const r = await client.performEntry(doc, fetchFn);
  check("e2e: refusal names its reason honestly",
    doc.getElementById("entry-status").textContent.includes("COVENANT_NOT_ACCEPTED"));
  check("e2e: refusal leaves the wallet untouched",
    doc.getElementById("wallet-state").innerHTML === "");
  check("e2e: refusal leaves the card standing",
    doc.getElementById("entry-gate").style.display !== "none");
  check("e2e: refusal resolves ok:false", r.ok === false);
}

/* ================= 3. unreachable server ================================== */
{
  const fetchFn = async () => { throw new Error("network down"); };
  const doc = fakeDoc();
  const r = await client.performEntry(doc, fetchFn);
  check("e2e: dead server strands no one — the doorway stays open",
    doc.getElementById("entry-status").textContent.includes("Server unreachable") &&
    doc.getElementById("entry-gate").style.display !== "none");
  check("e2e: unreachable resolves ok:false", r.ok === false);
}

console.log(`\ntest_entry_client: ${passed}/${passed + failed} checks passing`);
if (failed) {
  console.log("FAILURES:");
  for (const f of failures) console.log("  - " + f);
  process.exit(1);
}
console.log("all checks pass");
