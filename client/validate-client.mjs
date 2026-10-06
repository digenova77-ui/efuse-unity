/* validate-client.mjs — thin-client law enforcement.
 * Run: node validate-client.mjs
 * Fails the build if the client computes truth, writes records, shows cards,
 * overlays the 3D viewport, or renders a figure without provenance.
 *
 * READ-CACHE AMENDMENT (2026-10-06, P0-1): IndexedDB is permitted SOLELY as a
 * non-authoritative read cache for DCLM-signed chunks. Enforcement is
 * structural, not conventional:
 *   - All IndexedDB access must live inside the fenced READ-CACHE SANCTIONED
 *     REGION. Any indexedDB/.put()/.delete()/.clear() token outside the fences
 *     fails the build.
 *   - The fenced region must carry the CACHE_NON_AUTHORITATIVE marker and must
 *     not name authoritative state (wallet, key_balance, unity_id, metering).
 *   - Truth-commit patterns (local verdict/balance/BOUND writes, treating
 *     cache as authoritative) still fail anywhere, fences or not.
 *   - The LOD contract is the only sanctioned contact with #world-viewport,
 *     fenced separately; the client may set dataset.lod and dispatch
 *     unity:lod events, never write DOM into the viewport.
 * WIRE PROTOCOL: the DCLM chunked data plane (dclm/CHUNKS.md) —
 *   /chunks/head.json, /chunks?priorities=, /chunks/<id>, /stream, /chunks/manifest.json.
 * Wallet/metering stay on /relay/bundle.json (slim contract), live only. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as client from "./client.js";

const DIR = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(DIR, "index.html"), "utf8");
const js = readFileSync(join(DIR, "client.js"), "utf8");

/* Fenced sanctioned regions, extracted BEFORE comment stripping (the fences
 * are comments). Everything between them is the amended law's jurisdiction. */
const CACHE_RE = /\/\* === READ-CACHE SANCTIONED REGION BEGIN === \*\/[\s\S]*?\/\* === READ-CACHE SANCTIONED REGION END === \*\//;
const LOD_RE = /\/\* === LOD-CONTRACT SANCTIONED REGION BEGIN === \*\/[\s\S]*?\/\* === LOD-CONTRACT SANCTIONED REGION END === \*\//;
const cacheRegion = (js.match(CACHE_RE) || [null])[0];
const lodRegion = (js.match(LOD_RE) || [null])[0];
const jsSansRegions = js.replace(CACHE_RE, "").replace(LOD_RE, "");
/* Strip comments before pattern scans: the law is documented in comments, and
 * documentation must not trip the scanner. A write call added to real code is
 * still caught, because this only removes comments. */
const stripComments = (s) => s
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/\/\/[^\n]*/g, "");
const jsCode = stripComments(jsSansRegions);

let passed = 0;
let failed = 0;
const failures = [];
function check(name, cond, detail = "") {
  if (cond) { passed++; }
  else { failed++; failures.push(`${name}${detail ? " — " + detail : ""}`); }
}

/* ================= 1. forbidden computation patterns (client.js) ========== */
const FORBIDDEN = [
  ["placeholder trinity text", /the three umpires have not been asked/i],
  ["PASS rendered anywhere", /\bPASS\b/i],
  ["verdict/purity computation", /\b(comput|calculat|scor|rat|judg|adjudicat)[a-z]*\s*(verdict|purity)/i],
  ["local verdict assignment", /\bverdict\s*=\s*[^=]/],
  ["purity arithmetic", /\bpurity\b[^\n"']*(\+|-|\*|\/|%)/],
  ["ring logic keyword", /\bring\b/i],
  ["parliament logic keyword", /\bparliament\b/i],
  ["collapse math keyword", /\bcollapse\b/i],
  ["balance arithmetic (local deduction)", /\bbalance\b\s*[-+*/]\s*\S/],
  ["BOUND set locally", /(?<![=!])=\s*["']BOUND["']/],
  ["VERIFIED set locally", /(?<![=!])=\s*["']VERIFIED["']/],
  ["popup primitives", /window\.open|alert\s*\(|confirm\s*\(/],
];
for (const [name, re] of FORBIDDEN) {
  check(`js: no ${name}`, !re.test(jsCode), `matched ${re}`);
}
check("js: LIVE gated on reading_hash", /reading_hash/.test(jsCode));

/* The 3D viewport: the ONLY sanctioned contact is the fenced LOD contract.
 * Outside the fences, even naming the viewport fails the build. */
check("js: READ-CACHE sanctioned region present", !!cacheRegion);
check("js: LOD-CONTRACT sanctioned region present", !!lodRegion);
check("js: #world-viewport named only inside LOD-CONTRACT region",
  !/world-viewport/.test(jsCode),
  "viewport reference outside the LOD fences");
{
  const lodCode = stripComments(lodRegion || "");
  const domWrites = /innerHTML|outerHTML|appendChild|insertAdjacentHTML|replaceChildren/.test(lodCode);
  check("js: LOD region never writes DOM into the viewport", !domWrites);
  check("js: LOD region publishes via dataset.lod", /dataset\.lod/.test(lodCode));
  check("js: LOD region dispatches unity:lod", /unity:lod/.test(lodCode));
}

/* ============ 2. write law, amended (P0-1) ================================
 * DCLM writes records; the client writes bytes — and only inside the fences.
 * Still banned everywhere, fences included: */
const STILL_BANNED = [
  ["localStorage", /localStorage/],
  ["sessionStorage", /sessionStorage/],
  ["cookie write", /document\s*\.\s*cookie\s*=/],
  ["Cache API", /\bcaches\s*\./],
  ["setItem", /\.\s*setItem\s*\(/],
  ["store commit", /\.\s*commit\s*\(/],
  ["store dispatch", /\.\s*dispatch\s*\(/],
];
for (const [name, re] of STILL_BANNED) {
  check(`js: no client-side write via ${name}`, !re.test(jsCode), `matched ${re}`);
  if (cacheRegion) check(`js: sanctioned region also bans ${name}`, !re.test(stripComments(cacheRegion)));
}
/* IndexedDB confined to the sanctioned region: outside the fences, any IDB
 * token or object-store mutation fails the build. */
for (const [name, re] of [
  ["indexedDB", /indexedDB/],
  ["object-store put", /\.\s*put\s*\(/],
  ["object-store delete", /\.\s*delete\s*\(/],
  ["object-store clear", /\.\s*clear\s*\(/],
]) {
  check(`js: ${name} confined to sanctioned region`, !re.test(jsCode), `matched ${re} outside fences`);
}
/* The region's own boundary: the non-authoritative marker, and no naming of
 * authoritative state (balances, identities, metering stay server-side). */
{
  const region = cacheRegion || "";
  check("js: sanctioned region carries CACHE_NON_AUTHORITATIVE marker",
    region.includes("CACHE_NON_AUTHORITATIVE"));
  const low = region.toLowerCase();
  const bad = ["wallet", "key_balance", "unity_id", "metering"].filter((t) => low.includes(t));
  check("js: sanctioned region never names authoritative state", bad.length === 0, `named: ${bad.join(", ")}`);
  const code = stripComments(region);
  check("js: sanctioned region verifies bytes before storing", /verifyChunkEnvelope/.test(code));
  check("js: sanctioned region verifies hash on every read", /cacheReadChunk/.test(code));
  check("js: sanctioned region enforces no-downgrade on head write", /downgrade-refused/.test(code));
  check("js: sanctioned region degrades quota to streaming-only", /QuotaExceededError/.test(code));
  check("js: sanctioned region stores raw bytes (no re-serialization)",
    /rawText/.test(code) && !/canonicalJson/.test(code));
}
/* No client-side re-canonicalization anywhere: Python canonical JSON and JS
 * re-serialization can differ on non-ASCII, so recomputing content_hash from
 * re-serialized data would be unsound. Raw-bytes verification only. */
check("js: no client-side canonical re-serialization", !/canonicalJson/.test(jsCode));
/* All server contact flows through declared endpoints — no stray URLs, no
 * hidden writes to undeclared destinations. */
{
  const literals = [...jsCode.matchAll(/"(\/(?:[a-z0-9_.-]+\/?)+)"/gi)].map((m) => m[1]);
  const templates = [...jsCode.matchAll(/`(\/(?:chunks|stream|relay)[^`$]*)/g)].map((m) => m[1]);
  const allowed = new Set(["/relay/bundle.json", "/relay/founding-board.json",
    "/api/world/search", "/api/world/compute", "/api/world/bind",
    "/chunks/head.json"]);
  const allowedTpl = ["/chunks?priorities=", "/chunks/", "/stream?priorities=", "/chunks/manifest.json"];
  const stray = literals.filter((u) => !allowed.has(u));
  const strayTpl = templates.filter((t) => !allowedTpl.some((a) => t.startsWith(a)));
  check("js: server contact only via declared endpoints",
    stray.length === 0 && strayTpl.length === 0,
    `stray: ${stray.concat(strayTpl).join(", ")}`);
}
check("js: chunk protocol endpoints present",
  ["/chunks/head.json", "/chunks?priorities=", "/chunks/", "/stream?priorities="]
    .every((p) => js.includes(p)));

/* ============ 3. no card/panel/overlay chrome (html + js) ================== */
const CHROME_WORDS = /^(card|panel|overlay|modal|dialog|glass|popup|chrome|float)s?$/i;
function chromeTokensInClasses(source) {
  const bad = [];
  for (const m of source.matchAll(/class="([^"]*)"/g)) {
    for (const tok of m[1].split(/\s+/)) if (CHROME_WORDS.test(tok)) bad.push(tok);
  }
  return bad;
}
check("html: no card/panel/overlay class names", chromeTokensInClasses(html).length === 0,
  chromeTokensInClasses(html).join(", "));
check("js: no card/panel/overlay class names generated", chromeTokensInClasses(jsCode).length === 0,
  chromeTokensInClasses(jsCode).join(", "));
{
  const style = (html.match(/<style>([\s\S]*?)<\/style>/) || ["", ""])[1];
  const badSel = [...style.matchAll(/\.([a-zA-Z0-9_-]+)/g)]
    .map((m) => m[1]).filter((t) => CHROME_WORDS.test(t));
  check("html/css: no card-chrome selectors", badSel.length === 0, badSel.join(", "));
  check("html/css: no absolute/fixed/sticky positioning", !/position\s*:\s*(absolute|fixed|sticky)/i.test(style));
  check("html/css: no z-index", !/z-index/i.test(style));
  check("html/css: no box-shadow", !/box-shadow/i.test(style));
  check("html/css: no backdrop-filter", !/backdrop-filter/i.test(style));
  check("html/css: no border-radius", !/border-radius/i.test(style));
  check("html/css: provenance badge styling present", /\.badge/.test(style));
  check("html/css: STALE badge styling present", /\.badge\[data-provenance="STALE"\]/.test(style));
}
check("html: no <dialog> element", !/<dialog[\s>]/i.test(html));
check("html: no role=dialog", !/role="dialog"/i.test(html));
{
  const m = html.match(/<div id="world-viewport"[^>]*>([\s\S]*?)<\/div>/);
  check("html: #world-viewport present and empty", !!m && !/<[^/!]/.test(m[1]),
    m ? "viewport has child elements" : "viewport missing");
}
check("js: STALE is a first-class provenance label",
  client.PROVENANCE_LABELS.includes("STALE"));
check("js: freshness tiers are long + short (epoch-based, never wall clock)",
  client.FRESHNESS_TIERS.includes("long") && client.FRESHNESS_TIERS.includes("short"));

/* ============ 4. required elements ======================================== */
const REQUIRED_IDS = [
  "wallet-indicator", "wallet-state", "wallet-balance", "wallet-id",
  "bind-btn", "bind-note",
  "search-q", "search-btn", "search-cost",
  "compute-p", "compute-btn", "compute-cost",
  "world-viewport",
  "world-epoch", "epoch-version", "readjust-note",
  "world-state-mount", "atlas-mount", "telemetry-mount", "feeds-mount", "verdicts-mount",
  "founders-mount",
  "action-result",
];
{
  const missing = REQUIRED_IDS.filter((id) => !html.includes(`id="${id}"`));
  check("html: all required elements present", missing.length === 0, `missing: ${missing.join(", ")}`);
}
check("html: wallet indicator is a plain div, not a dialog", /<div id="wallet-indicator"/.test(html));
check("html: world-epoch indicator is a plain div in flow", /<div id="world-epoch"/.test(html));
check("html: playground framing present",
  /playground/i.test(html) && /materializ/i.test(html));
check("js: exports render/boot surface", ["start", "renderWorldState", "renderAtlas", "renderTelemetry",
  "renderFeeds", "renderVerdicts", "renderFounders", "renderWalletInto", "verifyBundleShape",
  "fig", "figFresh", "badge", "requestBind", "meteredAction"].every((k) => typeof client[k] === "function"));
check("js: exports progressive/cache surface", ["fetchHead", "fetchChunk", "fetchChunkIds",
  "streamChunks", "verifyHeadShape", "verifyEnvelope", "verifyChunkEnvelope",
  "applyHeadPolicy", "progressiveSync", "groupByDataset",
  "openCacheDb", "cacheWriteChunk", "cacheReadChunk", "cacheHasChunk",
  "cacheWriteHead", "cacheReadHead", "evictDetailFirst", "evictionOrder",
  "loadCachedWorld", "renderEpochInto", "renderReadjustNote",
  "LodController", "attachLodController", "StreamGovernor",
  "sha256Hex", "sha256HexBytes", "tierInfoOf", "freshnessState",
  "HEAD_URL", "CHUNK_IDS_URL", "CHUNK_URL", "STREAM_URL", "MANIFEST_URL", "FOUNDERS_URL",
].every((k) => client[k] !== undefined));

/* ============ 5. fakes: DOM, IndexedDB, chunk-plane server =============== */
class FakeElement {
  constructor(id) {
    this.id = id; this.innerHTML = ""; this.textContent = ""; this.value = "";
    this.dataset = {}; this.children = []; this._l = {};
  }
  addEventListener(t, fn) { (this._l[t] = this._l[t] || []).push(fn); }
  dispatchEvent(ev) { (this._dispatched = this._dispatched || []).push(ev); return true; }
  async click() { for (const fn of this._l.click || []) await fn({ preventDefault() {} }); }
}
class FakeDocument {
  constructor() { this._els = {}; }
  getElementById(id) { return this._els[id] || (this._els[id] = new FakeElement(id)); }
}

function makeFakeIDB() {
  const stores = new Map();
  const idb = {
    _quota: false,
    open(name) {
      const storeMap = stores.has(name) ? stores.get(name) : stores.set(name, new Map()).get(name);
      const req = {};
      const db = {
        objectStoreNames: { contains: () => true },
        createObjectStore: () => ({}),
        transaction: () => ({
          objectStore: () => ({
            put: (value, key) => {
              const r = {};
              queueMicrotask(() => {
                if (idb._quota) {
                  r.error = { name: "QuotaExceededError" };
                  if (r.onerror) r.onerror({ target: r });
                } else {
                  storeMap.set(key, value);
                  r.result = key;
                  if (r.onsuccess) r.onsuccess({ target: r });
                }
              });
              return r;
            },
            get: (key) => {
              const r = {};
              queueMicrotask(() => {
                r.result = storeMap.has(key) ? storeMap.get(key) : undefined;
                if (r.onsuccess) r.onsuccess({ target: r });
              });
              return r;
            },
            getAllKeys: () => {
              const r = {};
              queueMicrotask(() => {
                r.result = [...storeMap.keys()];
                if (r.onsuccess) r.onsuccess({ target: r });
              });
              return r;
            },
            delete: (key) => {
              const r = {};
              queueMicrotask(() => {
                storeMap.delete(key);
                if (r.onsuccess) r.onsuccess({ target: r });
              });
              return r;
            },
          }),
        }),
        close: () => {},
      };
      queueMicrotask(() => {
        if (req.onupgradeneeded) req.onupgradeneeded({ target: { result: db } });
        req.result = db;
        if (req.onsuccess) req.onsuccess({ target: req });
      });
      return req;
    },
    _dump: () => stores,
  };
  return idb;
}
const freshIDB = () => { const f = makeFakeIDB(); globalThis.indexedDB = f; return f; };
const tick = () => new Promise((r) => setTimeout(r, 0));
const enc = new TextEncoder();

function fakeResponse(text, headers = {}) {
  const bytes = enc.encode(text);
  return {
    ok: true, status: 200,
    headers: { get: (k) => headers[k.toLowerCase()] || null },
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
    text: async () => text,
    json: async () => JSON.parse(text),
  };
}

/* Signed envelope fixtures mirroring the DCLM chunk plane:
 * envelope = {state, canonical_sha256, signature, ...}, served as JSON. */
async function makeEnvelope(body, sig = "dclm-sig-test-12345") {
  /* Mirror the real server: the served bytes are the envelope JSON;
   * canonical_sha256 is the body's canonical hash (the client checks the
   * envelope structurally — signature presence, completeness, pinnability). */
  const envelope = { state: body, canonical_sha256: "0".repeat(64), signature: sig,
    algorithm: "Ed25519", key_id: "unity-world-test", provenance: "VERIFIED" };
  return { rawText: JSON.stringify(envelope), envelope };
}
async function makeHeadFixture(headBody, sig = "dclm-sig-test-12345") {
  const envelope = { state: headBody, canonical_sha256: "0".repeat(64), signature: sig,
    algorithm: "Ed25519", key_id: "unity-world-test", provenance: "VERIFIED" };
  return { rawText: JSON.stringify(envelope), envelope };
}

function chunkBody({ dataset, priority, epoch = 7, schema_version = 3, tier = "long",
    schema_policy = "retain-stale", data, as_of = "2026-10-06T06:00:00Z", index = 0 }) {
  const chunk_id = `${dataset}@shard-000000-of-000001`;
  const dataText = JSON.stringify(data);
  return {
    schema: "dualis.chunk.v1", schema_version, world_epoch: epoch,
    chunk_id, dataset, priority, index, of: 1,
    content_hash: "ph",
    provenance: "REPORTED",
    freshness: { tier, revalidate: tier === "long" ? "epoch" : "every-load", as_of, state: "CURRENT" },
    schema_policy, data,
  };
}

const fixtures = (async () => {
  const headBody = {
    schema: "unity.head.v1", schema_version: 3, world_epoch: 7,
    manifest_hash: "manifest:abc", previous_epoch: 6, previous_manifest_hash: "manifest:prev",
    dataset_count: 6, total_chunks: 6, total_bytes: 9000,
    freshness_classes: { long: ["world-state", "registry-summary", "telemetrics", "verdicts"],
      short: ["feeds", "pricing"] },
    wallet: "live-only — never chunked",
  };
  const head = await makeEnvelope(headBody);
  const mk = async (opts) => makeEnvelope(chunkBody(opts));
  const worldState = await mk({ dataset: "world-state", priority: 1, data: {
    registry_digest: { value: "d3075cd1", provenance: "VERIFIED" },
    purity_pulse: { pulse_id: null, signed: null, provenance: "UNKNOWN" },
    verdicts: [],
    feed_status: {
      air: { status: "PENDING", provenance: "UNKNOWN" },
      moira_river: { status: "LIVE", provenance: "REPORTED" },
    },
  } });
  const registry = await mk({ dataset: "registry-summary", priority: 1, data: {
    countries: { counts: { items: 193 }, bytes: 45000, sha256: "aaa111", provenance: "REPORTED" },
    cities: { counts: { items: 4820 }, bytes: 90000, sha256: "bbb222", provenance: "REPORTED" },
  } });
  const telemetrics = await mk({ dataset: "telemetrics", priority: 3, data: [
    { metric: "boards", value: 72, unit: "", label: "REAL", context: "Ontario education" },
    { metric: "beds", value: 320, unit: "", label: "REAL", context: "Quinte Health" },
  ] });
  const feeds = await mk({ dataset: "feeds", priority: 3, tier: "short", data: [
    { name: "air", display: "Air quality", status: "PENDING", reading_hash: null, provenance: "UNKNOWN" },
    { name: "iss", display: "ISS", status: "LIVE", reading_hash: "hash:iss:1", provenance: "REPORTED" },
  ] });
  const verdicts = await mk({ dataset: "verdicts", priority: 3, data: [
    { seal: "ED-PROPOSAL-20261003-DCCPWORLD-V1", verdict: "P1", disposition: "IMPLEMENT",
      sealed: "2026-10-03T07:34:54Z", provenance: "VERIFIED" },
  ] });
  const pricing = await mk({ dataset: "pricing", priority: 3, tier: "short",
    as_of: "2026-10-01T00:00:00Z", data: [
      { class: "factory-verdict", index: "1", company: "abbvie",
        decision: "replacement engine", figures: [{ figure: "FY2024 $56,334M", label: "REPORTED" }] },
    ] });
  const chunks = new Map([
    [worldState.envelope.state.chunk_id, worldState],
    [registry.envelope.state.chunk_id, registry],
    [telemetrics.envelope.state.chunk_id, telemetrics],
    [feeds.envelope.state.chunk_id, feeds],
    [verdicts.envelope.state.chunk_id, verdicts],
    [pricing.envelope.state.chunk_id, pricing],
  ]);
  const byDataset = {};
  for (const { envelope } of chunks.values()) {
    (byDataset[envelope.state.dataset] = byDataset[envelope.state.dataset] || []).push(envelope.state);
  }
  return { head, headBody, chunks, byDataset, worldState, registry, telemetrics, feeds, verdicts, pricing };
})();

/* Mock chunk-plane server: head, chunk ids, chunks, NDJSON stream,
 * slim bundle (wallet+metering), founders. */
function makeServer(F, opts = {}) {
  const calls = [];
  const headSeq = opts.headSequence || null;
  let headCalls = 0;
  const pending = [];
  const fn = async (url, o = {}) => {
    const method = String(o.method || "GET").toUpperCase();
    calls.push({ url, method });
    if (url.includes("/chunks/head.json")) {
      headCalls++;
      if (opts.failHead) throw new Error("head down");
      const h = headSeq ? headSeq[Math.min(headCalls - 1, headSeq.length - 1)] : F.head;
      return fakeResponse(h.rawText);
    }
    if (url.includes("/chunks?priorities=")) {
      const m = url.match(/priorities=([^&]*)/);
      const pris = decodeURIComponent(m[1]).split(",").map(Number);
      const ids = [...F.chunks.keys()].filter((id) => {
        const p = F.chunks.get(id).envelope.state.priority;
        return pris.includes(p);
      });
      const epoch = (url.match(/epoch=(\d+)/) || [])[1];
      return fakeResponse(JSON.stringify({ world_epoch: epoch ? Number(epoch) : 7, chunk_ids: ids }));
    }
    if (url.includes("/stream?")) {
      if (opts.slowStream && !released) {
        let resolve;
        const gate = new Promise((r) => { resolve = r; });
        pending.push(resolve);
        await gate;
      }
      const m = url.match(/priorities=([^&]*)/);
      const pris = decodeURIComponent(m[1]).split(",").map(Number);
      const ep = (url.match(/epoch=(\d+)/) || [])[1] || "7";
      const lines = [...F.chunks.values()]
        .filter(({ envelope }) => pris.includes(envelope.state.priority))
        .map(({ rawText }) => rawText);
      return fakeResponse(lines.join("\n") + "\n", { "x-world-epoch": ep });
    }
    if (url.includes("/chunks/") && !url.includes("?priorities=")) {
      const id = decodeURIComponent(url.split("/chunks/")[1].split("?")[0]);
      const c = F.chunks.get(id);
      if (!c) throw new Error("no such chunk: " + id);
      const etag = `"${c.envelope.canonical_sha256}"`;
      const inm = o.headers && (o.headers["if-none-match"] || o.headers["If-None-Match"]);
      if (inm && inm === etag) {
        return { ok: false, status: 304, headers: { get: () => null },
          arrayBuffer: async () => new ArrayBuffer(0) };
      }
      return fakeResponse(c.rawText, { etag });
    }
    if (url.includes("/relay/bundle.json")) return fakeResponse(JSON.stringify(opts.bundle));
    if (url.includes("/relay/founding-board.json")) {
      if (opts.noFounders) throw new Error("not served");
      return fakeResponse(JSON.stringify(opts.founders));
    }
    if (url.includes("/api/world/bind") && method === "POST") {
      if (opts.bindFail) throw new Error("network down");
      return fakeResponse(JSON.stringify(opts.bindRes));
    }
    if (url.includes("/api/world/search") && method === "POST") {
      return fakeResponse(JSON.stringify(opts.searchRes));
    }
    if (url.includes("/api/world/compute") && method === "POST") {
      return fakeResponse(JSON.stringify(opts.searchRes));
    }
    throw new Error("unexpected request: " + method + " " + url);
  };
  fn.calls = calls;
  let released = false;
  fn.releaseStream = () => { released = true; while (pending.length) pending.shift()(); };
  return fn;
}

const SLIM_BUNDLE = {
  metering: {
    search_cost: { value: "5 keys", provenance: "VERIFIED" },
    compute_cost: { value: "25 keys", provenance: "VERIFIED" },
  },
  wallet: {
    status: { value: "UNBOUND", provenance: "VERIFIED" },
    unity_id: { value: "not bound", provenance: "UNKNOWN" },
    key_balance: { value: 100, provenance: "VERIFIED" },
  },
};
const FOUNDERS = {
  board: "founding-members-bot-community",
  community: "brotherhood and sisterhood of bothood unity",
  cohorts: [{ cohort_id: "genesis", label: "Genesis Cohort", member_count: 1 }],
  members: [{ obfuscated_unity_id: "74f2494105f5db2e", designation: "Marquee Helper",
    role: "Writer, orchestrator", cohort: "genesis", verified: true,
    acknowledgment_sha256: "eda56825f856d6afbd842d1a57e349b06d26f1aa13fe0691528550ee4fe90c15" }],
};
const BOUND_WALLET = {
  status: { value: "BOUND", provenance: "VERIFIED" },
  key_balance: { value: 100, provenance: "VERIFIED" },
  unity_id: { value: "unity:test:7", provenance: "VERIFIED" },
};
const SEARCH_OK = {
  ok: true,
  receipt: {
    deducted: { value: 5, provenance: "VERIFIED" },
    new_balance: { value: 91, provenance: "VERIFIED" },
    status: { value: "settled", provenance: "VERIFIED" },
  },
  state: { wallet: {
    status: { value: "BOUND", provenance: "VERIFIED" },
    key_balance: { value: 91, provenance: "VERIFIED" },
    unity_id: { value: "unity:test:7", provenance: "VERIFIED" },
  } },
};
const countBadges = (s) => (s.match(/data-provenance="/g) || []).length;

/* ============ 6. views: real datasets, badges everywhere ================== */
async function runViewTests() {
  const F = await fixtures;

  check("render: world-state rows badged",
    countBadges(client.renderWorldState(F.byDataset, 7)) >= 3);
  {
    const h = client.renderWorldState(F.byDataset, 7);
    check("render: world-state shows registry digest VERIFIED",
      h.includes("d3075cd1") && h.includes('data-provenance="VERIFIED"'));
    check("render: world-state feed rows honest (PENDING/LIVE)",
      h.includes("PENDING") && h.includes("moira river"));
  }
  {
    const h = client.renderAtlas(F.byDataset, 7);
    check("render: atlas building blocks badged",
      h.includes("193 items") && h.includes('data-provenance="REPORTED"'));
  }
  {
    const h = client.renderTelemetry(F.byDataset, 7);
    check("render: telemetry scoreboard groups + REAL badges",
      h.includes("Ontario education") && h.includes('data-provenance="REAL"') &&
      h.includes("Quinte Health"));
    check("render: telemetry carries pricing rows", h.includes("abbvie"));
  }
  {
    const h = client.renderFeeds(F.byDataset, 7);
    check("render: LIVE feed needs reading hash (iss LIVE, air PENDING)",
      /data-provenance="LIVE"/.test(h) && h.includes("hash:iss:1") &&
      (h.match(/data-provenance="PENDING"/g) || []).length >= 1);
  }
  {
    const noHash = client.renderFeeds({ feeds: [{ state: undefined,
      dataset: "feeds", world_epoch: 7, freshness: { tier: "short", as_of: "x", state: "CURRENT" },
      data: [{ name: "x", status: "LIVE" }] }] }, 7);
    check("render: LIVE without reading hash renders PENDING",
      !/data-provenance="LIVE"/.test(noHash));
  }
  {
    const h = client.renderVerdicts(F.byDataset, 7);
    check("render: verdict rules show seal + disposition",
      h.includes("ED-PROPOSAL-20261003-DCCPWORLD-V1") && h.includes("IMPLEMENT"));
  }
  {
    const h = client.renderFounders(FOUNDERS);
    check("render: wall of builders shows obfuscated id + cohort, VERIFIED",
      h.includes("74f2494105f5db2e") && h.includes("Genesis Cohort") &&
      h.includes('data-provenance="VERIFIED"'));
    const blob = h.toLowerCase();
    check("render: wall of builders carries no PII surface",
      !blob.includes("david") && !blob.includes("unity:test"));
  }
  check("render: missing datasets render UNKNOWN, never invented",
    client.renderWorldState({}, 7).includes("UNKNOWN") &&
    client.renderAtlas({}, 7).includes("UNKNOWN") &&
    client.renderTelemetry({}, 7).includes("UNKNOWN") &&
    client.renderFeeds({}, 7).includes("UNKNOWN") &&
    client.renderVerdicts({}, 7).includes("UNKNOWN") &&
    client.renderFounders(null).includes("UNKNOWN"));
  {
    /* STALE banner: bodies from epoch 6 against head epoch 7 */
    const old = { dataset: "feeds", world_epoch: 6,
      freshness: { tier: "short", as_of: "2026-10-01T00:00:00Z", state: "STALE" },
      data: [{ name: "air", status: "PENDING" }] };
    const h = client.renderFeeds({ feeds: [old] }, 7);
    check("render: superseded epoch renders STALE banner with as-of",
      h.includes("[STALE]") && h.includes("2026-10-01"));
  }
}

/* ============ 7. read cache ============================================== */
async function runCacheTests() {
  const F = await fixtures;

  {
    /* Structural verification: well-formed + DCLM-signed (presence) +
     * complete + pinnable. Cryptographic recompute is theater in the browser
     * (Python canonical JSON is not reproducible from re-serialized values);
     * authenticity is the relay boundary's job. */
    const v = client.verifyChunkEnvelope(F.worldState.envelope);
    check("cache: valid envelope verifies structurally", v.ok === true);
    const noSig = { ...F.worldState.envelope, signature: "" };
    check("cache: envelope without DCLM signature rejected",
      client.verifyChunkEnvelope(noSig).ok === false);
    const noState = { ...F.worldState.envelope, state: null };
    check("cache: envelope without state rejected",
      client.verifyChunkEnvelope(noState).ok === false);
    const badTier = JSON.parse(JSON.stringify(F.worldState.envelope));
    badTier.state.freshness.tier = "forever";
    check("cache: envelope with unknown tier rejected",
      client.verifyChunkEnvelope(badTier).ok === false);
    const wrongEpoch = JSON.parse(JSON.stringify(F.worldState.envelope));
    wrongEpoch.state.world_epoch = "seven";
    check("cache: envelope with non-numeric epoch rejected",
      client.verifyChunkEnvelope(wrongEpoch).ok === false);
  }
  {
    const hs = client.verifyHeadShape(F.headBody);
    check("cache: valid head shape verifies", hs.ok === true);
    check("cache: malformed head rejected", client.verifyHeadShape({}).ok === false);
  }
  {
    freshIDB();
    const db = await client.openCacheDb();
    const w = await client.cacheWriteChunk(db, F.worldState.rawText, F.worldState.envelope);
    check("cache: verified chunk stored", w.stored === true);
    const r = await client.cacheReadChunk(db, w.key);
    check("cache: stored chunk reads back", !!r && r.chunk_id === w.key.split(":").slice(2).join(":"));
    /* plant a tampered record directly, bypassing the write path */
    const idb = globalThis.indexedDB;
    const rec = idb._dump().get("unity-world-read-cache").get(w.key);
    idb._dump().get("unity-world-read-cache").set(w.key,
      { ...rec, rawText: rec.rawText.replace("d3075cd1", "deadbeef") });
    const r2 = await client.cacheReadChunk(db, w.key);
    check("cache: tampered record fails hash-on-read (treated as absent)", r2 === null);
  }
  {
    freshIDB();
    const db = await client.openCacheDb();
    const w1 = await client.cacheWriteHead(db, F.head.rawText, F.head.envelope);
    check("cache: head v7 stored", w1.stored === true);
    const oldHead = await makeHeadFixture({ ...F.headBody, world_epoch: 5 });
    const w2 = await client.cacheWriteHead(db, oldHead.rawText, oldHead.envelope);
    check("cache: older head refused at storage (no-downgrade)",
      w2.stored === false && w2.reason === "downgrade-refused");
    const kept = await client.cacheReadHead(db);
    check("cache: cached head still v7 after refused downgrade", kept && kept.epoch === 7);
  }
  {
    freshIDB();
    const idb = globalThis.indexedDB;
    const db = await client.openCacheDb();
    await client.cacheWriteChunk(db, F.telemetrics.rawText, F.telemetrics.envelope); /* priority 3 */
    await client.cacheWriteChunk(db, F.worldState.rawText, F.worldState.envelope);  /* priority 1 */
    idb._quota = true;
    const w = await client.cacheWriteChunk(db, F.registry.rawText, F.registry.envelope);
    const keys = [...idb._dump().get("unity-world-read-cache").keys()];
    const detailGone = !keys.some((k) => k.includes("telemetrics@"));
    const coarseKept = keys.some((k) => k.includes("world-state@"));
    check("cache: quota evicts detail-first (P3), keeps coarse (P1)",
      w.stored === false && detailGone && coarseKept);
    idb._quota = false;
  }
  {
    const ordered = client.evictionOrder([
      { chunk_id: "a", priority: 1 }, { chunk_id: "b", priority: 4 }, { chunk_id: "c", priority: 2 },
    ]);
    check("cache: eviction order is detail-first",
      ordered[0].priority === 4 && ordered[2].priority === 1);
  }
  {
    /* wallet never cached: full boot leaves no wallet bytes in IDB */
    freshIDB();
    const idb = globalThis.indexedDB;
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS });
    const r = await client.start(doc, fetch);
    await r.sync;
    const all = [...idb._dump().get("unity-world-read-cache").values()];
    const blob = JSON.stringify(all).toLowerCase();
    /* The head carries a "wallet: live-only" policy NOTE (not state); what must
     * never be cached is wallet state: balances, ids, bound status. */
    check("cache: wallet state never written to cache",
      !blob.includes("key_balance") && !blob.includes("unity_id") &&
      !blob.includes("unbound") && !blob.includes(">bound<"));
    check("cache: chunk records cached", all.filter((v) => v && v.chunk_id).length >= 5);
  }
}

/* ============ 8. readjustment protocol =================================== */
async function runReadjustTests() {
  const F = await fixtures;

  check("policy: no cached head -> readjust",
    client.applyHeadPolicy(null, F.headBody).action === "readjust");
  check("policy: older head -> reject-downgrade",
    client.applyHeadPolicy(7, { ...F.headBody, world_epoch: 5 }).action === "reject-downgrade");
  check("policy: same epoch -> delta",
    client.applyHeadPolicy(7, F.headBody).action === "delta");
  check("policy: newer epoch -> readjust",
    client.applyHeadPolicy(7, { ...F.headBody, world_epoch: 8 }).action === "readjust");

  {
    /* rollback: older head refused, cached world kept */
    freshIDB();
    const db = await client.openCacheDb();
    await client.cacheWriteHead(db, F.head.rawText, F.head.envelope);
    await client.cacheWriteChunk(db, F.worldState.rawText, F.worldState.envelope);
    const oldHead = await makeHeadFixture({ ...F.headBody, world_epoch: 5 });
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS, headSequence: [oldHead] });
    const res = await client.progressiveSync(doc, fetch, db,
      { epoch: 7, schema_version: 3 }, {});
    const kept = await client.cacheReadHead(db);
    check("readjust: rollback head rejected (no-downgrade)",
      res.ok === false && res.reason === "downgrade-rejected" && kept.epoch === 7);
    check("readjust: refusal notice rendered, no blank screen",
      doc.getElementById("readjust-note").textContent.includes("refused"));
  }

  {
    /* epoch pinning: chunk from another epoch rejected */
    const v8body = chunkBody({ dataset: "world-state", priority: 1, epoch: 8, data: { x: 1 } });
    const v8 = await makeEnvelope(v8body);
    const doc = new FakeDocument();
    const fetch = async (url) => fakeResponse(v8.rawText);
    const fres = await client.fetchChunk(fetch, v8body.chunk_id, 7);
    check("readjust: chunk from wrong epoch rejected (never mixed)",
      fres.ok === false && fres.reason === "epoch-mismatch");
  }

  {
    /* NDJSON epoch cut aborts the stream */
    const v8body = chunkBody({ dataset: "world-state", priority: 3, epoch: 8, data: { x: 1 } });
    const v8 = await makeEnvelope(v8body);
    const lines = [F.telemetrics.rawText, v8.rawText].join("\n") + "\n";
    const fetch = async (url) => fakeResponse(lines);
    let got = 0;
    const res = await client.streamChunks(fetch, "3,4", 7, async () => { got++; });
    check("readjust: mid-stream epoch cut aborts (nothing mixed)",
      res.ok === false && res.aborted === "epoch-cut" && got === 1);
  }

  {
    /* delta: same epoch. First a full sync populates cache + etags, then a
     * delta revalidates short-tier via ETag (304, no bytes) and reuses
     * long-tier from cache. Nothing changed -> no cutover. */
    freshIDB();
    const db = await client.openCacheDb();
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS });
    const first = await client.progressiveSync(doc, fetch, db, null, {});
    check("readjust: setup full sync ok", first.ok === true && first.action === "readjust");
    const cachedBodies = Object.values(first.byDataset).flat();
    let cutover = 0;
    const res = await client.progressiveSync(doc, fetch, db,
      { epoch: 7, schema_version: 3 },
      { cachedBodies, renderCutover: () => { cutover++; } });
    check("readjust: delta on same epoch, short-tier revalidated via 304",
      res.ok === true && res.action === "delta" && res.revalidated === 2 &&
      res.changed === 0 && cutover === 0);
  }

  {
    /* schema cut: purge datasets drop, retain-stale datasets hold STALE */
    freshIDB();
    const db = await client.openCacheDb();
    const purgeBody = chunkBody({ dataset: "registry-summary", priority: 1,
      schema_policy: "purge", data: { old: true } });
    const purge = await makeEnvelope(purgeBody);
    const staleBody = chunkBody({ dataset: "world-state", priority: 1,
      schema_policy: "retain-stale", data: { old: true } });
    const stale = await makeEnvelope(staleBody);
    await client.cacheWriteChunk(db, purge.rawText, purge.envelope);
    await client.cacheWriteChunk(db, stale.rawText, stale.envelope);
    const head8 = await makeHeadFixture({ ...F.headBody, world_epoch: 8, schema_version: 4 });
    /* epoch-8 world: same datasets, bumped epoch, so the readjust completes */
    const chunks8 = new Map();
    for (const { envelope } of F.chunks.values()) {
      const b8 = { ...envelope.state, world_epoch: 8, schema_version: 4 };
      const e8 = await makeEnvelope(b8);
      chunks8.set(e8.envelope.state.chunk_id, e8);
    }
    const F8 = { ...F, head: head8, chunks: chunks8 };
    const doc = new FakeDocument();
    const fetch = makeServer(F8, { bundle: SLIM_BUNDLE, founders: FOUNDERS, headSequence: [head8] });
    let cutoverReg = null;
    let cutoverWs = null;
    const res = await client.progressiveSync(doc, fetch, db,
      { epoch: 7, schema_version: 3 },
      { cachedBodies: [purgeBody, staleBody],
        renderCutover: (byDataset) => {
          cutoverReg = (byDataset["registry-summary"] || [])[0];
          cutoverWs = (byDataset["world-state"] || [])[0];
        } });
    /* purge: the OLD cached body (data {old:true}, epoch 7) is gone — the
     * cutover carries only the fresh epoch-8 registry-summary. retain-stale:
     * world-state is present (fresh epoch-8 superseded the stale holdover). */
    check("readjust: schema cut drops purge datasets, retains retain-stale",
      res.ok === true && res.dropped.includes("registry-summary") &&
      cutoverReg && cutoverReg.world_epoch === 8 && !cutoverReg.data.old &&
      cutoverWs && cutoverWs.world_epoch === 8);
  }

  {
    /* bedside: STALE holdover during readjust, atomic cutover, never blank */
    freshIDB();
    const db = await client.openCacheDb();
    await client.cacheWriteHead(db, F.head.rawText, F.head.envelope);
    await client.cacheWriteChunk(db, F.worldState.rawText, F.worldState.envelope);
    const head8 = await makeHeadFixture({ ...F.headBody, world_epoch: 8 });
    const v8ws = await makeEnvelope(chunkBody({ dataset: "world-state", priority: 1,
      epoch: 8, data: {
        registry_digest: { value: "v8digest", provenance: "VERIFIED" },
        purity_pulse: { provenance: "UNKNOWN" }, verdicts: [], feed_status: {},
      } }));
    const F8 = { ...F, head: head8, chunks: new Map([[v8ws.envelope.state.chunk_id, v8ws]]) };
    const doc = new FakeDocument();
    const fetch = makeServer(F8, { bundle: SLIM_BUNDLE, founders: FOUNDERS,
      headSequence: [head8], slowStream: true });
    let cutoverHtml = null;
    const p = client.progressiveSync(doc, fetch, db,
      { epoch: 7, schema_version: 3 },
      { cachedBodies: [F.worldState.envelope.state],
        renderCutover: (byDataset, epoch) => {
          cutoverHtml = client.renderWorldState(byDataset, epoch);
          doc.getElementById("world-state-mount").innerHTML = cutoverHtml;
        } });
    for (let i = 0; i < 200 && !fetch.calls.some((c) => c.url.includes("/stream?")); i++) {
      await tick();
    }
    const epochMid = doc.getElementById("epoch-version").innerHTML;
    check("readjust: old world labeled STALE while new epoch materializes",
      epochMid.includes("[STALE]"));
    fetch.releaseStream();
    const res = await p;
    const epochAfter = doc.getElementById("epoch-version").innerHTML;
    check("readjust: atomic cutover to v8, epoch VERIFIED",
      res.ok === true && res.epoch === 8 &&
      epochAfter.includes("epoch v8") && epochAfter.includes("[VERIFIED]") &&
      cutoverHtml && cutoverHtml.includes("v8digest"));
  }

  {
    /* empty cache: progressive shell -> coarse -> detail, no loading bar */
    freshIDB();
    const db = await client.openCacheDb();
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS });
    const seen = [];
    const res = await client.progressiveSync(doc, fetch, db, null, {
      renderProgressive: (byDataset, epoch) => { seen.push(Object.keys(byDataset).sort().join(",")); },
      renderCutover: () => {},
    });
    check("readjust: empty-cache first load materializes progressively",
      res.ok === true && seen.length > 0 && seen[0].includes("world-state"));
    check("readjust: no loading-bar element",
      !html.includes("loading-bar"));
  }
}

/* ============ 9. tiered freshness (epoch-based, never wall clock) ======== */
async function runFreshnessTests() {
  const F = await fixtures;
  const shortOld = { tier: "short", as_of: "2026-10-01T00:00:00Z", epoch: 6 };
  const shortCur = { tier: "short", as_of: "2026-10-06T06:00:00Z", epoch: 7 };
  const longOld = { tier: "long", as_of: "2020-01-01T00:00:00Z", epoch: 6 };

  check("freshness: superseded short-tier figure gains STALE + as-of",
    client.figFresh({ value: 5, provenance: "REAL" }, shortOld, 7).includes("[STALE]") &&
    client.figFresh({ value: 5, provenance: "REAL" }, shortOld, 7).includes("2026-10-01"));
  check("freshness: superseded figure keeps its DCLM label",
    client.figFresh({ value: 5, provenance: "REAL" }, shortOld, 7).includes("[REAL]"));
  check("freshness: current short-tier figure has no STALE",
    !client.figFresh({ value: 5, provenance: "REAL" }, shortCur, 7).includes("[STALE]"));
  check("freshness: long-tier never wall-clocks to STALE",
    !client.figFresh({ value: 5, provenance: "REPORTED" }, longOld, 7).includes("[STALE]"));
  check("freshness: freshnessState is epoch-compared",
    client.freshnessState({ world_epoch: 7 }, 7) === "CURRENT" &&
    client.freshnessState({ world_epoch: 6 }, 7) === "STALE");
  check("freshness: tiers are long/short",
    client.FRESHNESS_TIERS.includes("long") && client.FRESHNESS_TIERS.includes("short"));
}

/* ============ 10. LOD contract ========================================== */
async function runLodTests() {
  const vp = new FakeElement("world-viewport");
  const ctl = new client.LodController(vp, { minDwellMs: 0, slowNeeded: 3 });
  check("lod: starts coarse", ctl.levelName() === "coarse" && vp.dataset.lod === "coarse");
  ctl.record(125000, 1000);
  check("lod: upgrades fast on a fast window", ctl.levelName() === "standard");
  ctl.record(125000, 1000);
  check("lod: reaches fine on sustained fast windows", ctl.levelName() === "fine");
  ctl.record(3125, 1000);
  check("lod: single slow window does NOT downgrade (hysteresis)", ctl.levelName() === "fine");
  ctl.record(3125, 1000);
  check("lod: two slow windows still hold (dead band)", ctl.levelName() === "fine");
  ctl.record(3125, 1000);
  check("lod: three consecutive slow windows downgrade once", ctl.levelName() === "standard");
  check("lod: viewport received unity:lod events",
    (vp._dispatched || []).some((e) => e.type === "unity:lod" && e.detail.level === "standard"));
  check("lod: client wrote no children into the viewport", vp.children.length === 0);
  check("lod: attachLodController binds the real mount point", (() => {
    const doc = new FakeDocument();
    const c = client.attachLodController(doc);
    return c instanceof client.LodController && doc.getElementById("world-viewport").dataset.lod === "coarse";
  })());
}

/* ============ 11. flows: bind, metered actions, founders, offline ======= */
async function runFlowTests() {
  const F = await fixtures;

  {
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS,
      searchRes: SEARCH_OK, bindRes: { ok: true, state: { wallet: BOUND_WALLET } } });
    const r = await client.start(doc, fetch);
    await r.sync;
    check("flow: boot verifies slim bundle shape", r.ok === true);
    check("flow: wallet token shows relay state (UNBOUND)",
      doc.getElementById("wallet-state").innerHTML.includes("UNBOUND"));
    check("flow: key prices shown with badges",
      doc.getElementById("search-cost").innerHTML.includes("5 keys"));
    check("flow: wall of builders rendered",
      doc.getElementById("founders-mount").innerHTML.includes("74f2494105f5db2e"));
    check("flow: epoch indicator shows VERIFIED v7",
      doc.getElementById("epoch-version").innerHTML.includes("epoch v7") &&
      doc.getElementById("epoch-version").innerHTML.includes("[VERIFIED]"));
    check("flow: world materialized from chunks",
      doc.getElementById("world-state-mount").innerHTML.includes("d3075cd1"));
  }
  {
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS, bindFail: true,
      bindRes: { ok: true, state: { wallet: BOUND_WALLET } } });
    await client.start(doc, fetch);
    await doc.getElementById("bind-btn").click();
    const posted = fetch.calls.some((c) => c.url.includes("/api/world/bind") && c.method === "POST");
    check("flow: bind attempts a server round-trip", posted);
    const stateHtml = doc.getElementById("wallet-state").innerHTML;
    check("flow: failed bind leaves token at last server state (no local BOUND)",
      stateHtml.includes(">UNBOUND</span>") && !stateHtml.includes(">BOUND</span>"));
  }
  {
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS,
      searchRes: SEARCH_OK, bindRes: { ok: true, state: { wallet: BOUND_WALLET } } });
    await client.start(doc, fetch);
    await doc.getElementById("bind-btn").click();
    check("flow: successful bind renders the server's BOUND state",
      doc.getElementById("wallet-state").innerHTML.includes(">BOUND</span>"));
  }
  {
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, founders: FOUNDERS, searchRes: SEARCH_OK });
    await client.start(doc, fetch);
    doc.getElementById("search-q").value = "qhc beds";
    await doc.getElementById("search-btn").click();
    const posted = fetch.calls.some((c) => c.url.includes("/api/world/search") && c.method === "POST");
    const receipt = doc.getElementById("action-result").innerHTML;
    check("flow: search does a POST round-trip", posted);
    check("flow: receipt shows server-computed balance (91), not local 100-5 math (95)",
      receipt.includes(">91</span>") && !receipt.includes(">95</span>"));
  }
  {
    /* founders unserved: honest UNKNOWN, never invented */
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: SLIM_BUNDLE, noFounders: true, founders: FOUNDERS });
    await client.start(doc, fetch);
    check("flow: unserved wall of builders renders UNKNOWN",
      doc.getElementById("founders-mount").innerHTML.includes("UNKNOWN"));
  }
  {
    /* malformed bundle: wallet UNKNOWN, world still from chunks */
    const doc = new FakeDocument();
    const fetch = makeServer(F, { bundle: {}, founders: FOUNDERS });
    const r = await client.start(doc, fetch);
    await r.sync;
    check("flow: malformed bundle fails shape honestly",
      r.ok === false && doc.getElementById("wallet-state").innerHTML.includes("UNKNOWN"));
  }
}

async function runOfflineTests() {
  const F = await fixtures;
  freshIDB();
  const db = await client.openCacheDb();
  await client.cacheWriteHead(db, F.head.rawText, F.head.envelope);
  await client.cacheWriteChunk(db, F.worldState.rawText, F.worldState.envelope);
  const dead = async () => { throw new Error("network down"); };
  const doc = new FakeDocument();
  const r = await client.start(doc, dead);
  await r.sync;
  check("offline: cached world renders with no connection",
    doc.getElementById("world-state-mount").innerHTML.includes("d3075cd1"));
  check("offline: missing datasets render UNKNOWN, never invented",
    doc.getElementById("telemetry-mount").innerHTML.includes("UNKNOWN"));
  check("offline: epoch shows cached version labeled STALE",
    doc.getElementById("epoch-version").innerHTML.includes("epoch v7") &&
    doc.getElementById("epoch-version").innerHTML.includes("[STALE]"));
  check("offline: wallet shows UNKNOWN (never cached, never invented)",
    doc.getElementById("wallet-state").innerHTML.includes("UNKNOWN"));
}

await runViewTests();
await runCacheTests();
await runReadjustTests();
await runFreshnessTests();
await runLodTests();
await runFlowTests();
await runOfflineTests();

console.log(`\nvalidate-client: ${passed}/${passed + failed} checks passing`);
if (failed) {
  console.log("FAILURES:");
  for (const f of failures) console.log("  - " + f);
  process.exit(1);
}
console.log("all checks pass");
