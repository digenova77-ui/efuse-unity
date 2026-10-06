"use strict";
/* DERIVATIVE AUDIT — 2D view. Displays DCLM's records; checks consistency. Never computes truth. */

const $ = (id) => document.getElementById(id);
const DATA = {};
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const PROV = {
  REPORTED: "p-reported", VERIFIED: "p-verified", MODELED: "p-modeled",
  DERIVED: "p-derived", UNKNOWN: "p-unknown", REAL: "p-real", PENDING: "p-pending",
};
const provBadge = (p) => p ? `<span class="p ${PROV[String(p).toUpperCase()] || "p-unknown"}">${esc(p)}</span>` : "";

function shortHash(h) { h = String(h || ""); return h.length > 16 ? h.slice(0, 10) + "…" + h.slice(-6) : h; }

/* Clickable hash: opens the drawer with the full record. data-hash-context carries the record label. */
function hashLink(h, context) {
  if (!h) return '<span class="muted">—</span>';
  return `<button class="hash" data-hash="${esc(h)}" data-ctx="${esc(context || "")}" title="Click to inspect">${esc(shortHash(h))}</button>`;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("button.hash");
  if (b) openDrawer(b.dataset.hash, b.dataset.ctx || "");
});

/* ---------- drawer ---------- */
function openDrawer(hash, context, extraHtml) {
  $("drawer-title").textContent = "Hash record";
  $("drawer-body").innerHTML = `
    <dl>
      <dt>SHA-256</dt><dd><div class="fullhash">${esc(hash)}</div></dd>
      <dt>Context</dt><dd>${esc(context)}</dd>
      <dt>Length</dt><dd>${hash.length} hex chars</dd>
    </dl>
    <div class="toolbar">
      <button class="btn small" id="d-copy">Copy hash</button>
    </div>
    ${extraHtml || ""}
    <div class="caveat">This hash is a recorded fingerprint. Clicking never invents data: it only shows what the ledger recorded. To re-verify a file hash, use the <strong>Verify</strong> tab.</div>`;
  $("d-copy").onclick = () => navigator.clipboard.writeText(hash).then(() => { $("d-copy").textContent = "Copied"; });
  $("drawer").classList.add("open"); $("scrim").classList.add("on");
}
function closeDrawer() { $("drawer").classList.remove("open"); $("scrim").classList.remove("on"); }
$("drawer-close").onclick = closeDrawer; $("scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

/* ---------- generic sortable table ---------- */
function renderGrid(theadEl, tbodyEl, columns, rows, opts = {}) {
  // columns: [{key, label, num?, fmt?(row)->html, search?(row)->str}]
  let sortKey = opts.sortKey || null, sortDir = 1;
  const state = { rows: rows.slice(), filter: "" };
  function visible() {
    const f = state.filter.trim().toLowerCase();
    if (!f) return state.rows;
    return state.rows.filter((r) => columns.some((c) => {
      const s = c.search ? c.search(r) : String(r[c.key] ?? "");
      return s.toLowerCase().includes(f);
    }));
  }
  function draw() {
    const vis = visible();
    if (sortKey) {
      const c = columns.find((x) => x.key === sortKey);
      vis.sort((a, b) => {
        let x = a[sortKey] ?? "", y = b[sortKey] ?? "";
        if (c && c.num) { x = +x || 0; y = +y || 0; }
        return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
      });
    }
    theadEl.innerHTML = "<tr>" + columns.map((c) =>
      `<th class="${c.num ? "num" : ""}" data-k="${esc(c.key)}">${esc(c.label)}${sortKey === c.key ? ` <span class="arr">${sortDir > 0 ? "▲" : "▼"}</span>` : ""}</th>`).join("") + "</tr>";
    theadEl.querySelectorAll("th").forEach((th) => th.onclick = () => {
      const k = th.dataset.k;
      if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = 1; }
      draw();
    });
    tbodyEl.innerHTML = vis.map((r) => "<tr>" + columns.map((c) =>
      `<td class="${c.num ? "num" : ""}${c.wrap ? " wrap" : ""}">${c.fmt ? c.fmt(r) : esc(r[c.key] ?? "")}</td>`).join("") + "</tr>").join("");
    if (opts.onCount) opts.onCount(vis.length, state.rows.length);
    state.lastVisible = vis;
  }
  draw();
  return { setFilter(f) { state.filter = f; draw(); }, setRows(r) { state.rows = r.slice(); draw(); }, visibleRows: () => state.lastVisible || state.rows };
}

function download(name, mime, text) {
  const a = document.createElement("a");
  a.download = name;
  if (typeof URL.createObjectURL === "function") {
    a.href = URL.createObjectURL(new Blob([text], { type: mime }));
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  } else {
    // fallback for non-Blob-URL contexts
    a.href = "data:" + mime + ";charset=utf-8," + encodeURIComponent(text);
    a.click();
  }
}
function toCSV(columns, rows) {
  const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const head = columns.map((c) => q(c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => q(c.csv ? c.csv(r) : (r[c.key] ?? ""))).join(",")).join("\n");
  return head + "\n" + body + "\n";
}

async function sha256hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/* ---------- tabs ---------- */
document.querySelectorAll(".tabs button").forEach((btn) => btn.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", "false"));
  btn.setAttribute("aria-selected", "true");
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("view-" + btn.dataset.view).classList.add("active");
  if (btn.dataset.view === "dag") initDAG();
}));

async function loadAll() {
  const files = ["chain", "gate", "manifests", "receipts", "tables", "founding"];
  for (const f of files) {
    const res = await fetch("data/" + f + ".json");
    DATA[f] = await res.json();
  }
  $("gen-at").textContent = "view built " + (DATA.chain.generated_at || "");
}

/* ---------- CHAIN view ---------- */
let chainGrid;
function renderChain() {
  const ch = DATA.chain;
  const s = ch.stats;
  $("chain-meta").textContent = `${s.epoch_built} built epochs · ${s.fork_points} fork points · ${s.links_ok}/${s.epoch_built} links OK · ${s.schema_bumps} schema bumps`;
  const forkParents = new Set(ch.forks.map((f) => f.parent));
  const forkChildren = new Set(ch.forks.flatMap((f) => f.children));
  const rows = ch.epochs.map((e) => ({
    ...e,
    isForkParent: forkParents.has(e.epoch),
    isForkChild: forkChildren.has(e.epoch),
  }));
  const statusBadge = (e) => {
    if (e.link_status === "OK") return `<span class="badge b-ok">LINK OK</span>`;
    if (e.link_status === "GENESIS") return `<span class="badge b-mut">GENESIS</span>`;
    return `<span class="badge b-bad">${esc(e.link_status)}</span>`;
  };
  chainGrid = renderGrid($("chain-table").querySelector("thead"), $("chain-table").querySelector("tbody"), [
    { key: "epoch", label: "Epoch", num: true },
    { key: "at", label: "Timestamp (UTC)", fmt: (r) => `<span class="hash">${esc(r.at)}</span>` },
    { key: "manifest_hash", label: "Manifest hash", fmt: (r) => hashLink(r.manifest_hash, `epoch ${r.epoch} manifest`) },
    { key: "previous_epoch", label: "Prev epoch", num: true, fmt: (r) => r.previous_epoch ?? "—" },
    { key: "previous_manifest_hash", label: "Previous hash", fmt: (r) => r.previous_manifest_hash ? hashLink(r.previous_manifest_hash, `epoch ${r.epoch} previous manifest`) : "—" },
    { key: "chunk_count", label: "Chunks", num: true },
    { key: "total_bytes", label: "Bytes", num: true, fmt: (r) => (+r.total_bytes).toLocaleString("en-US") },
    { key: "schema_version", label: "Schema", num: true },
    { key: "datasets", label: "Datasets", num: true, fmt: (r) => r.datasets.length },
    { key: "link_status", label: "Linkage", fmt: statusBadge },
    { key: "fork", label: "Fork", fmt: (r) => r.isForkParent ? `<span class="badge b-warn">FORK ⑂ ${ch.forks.find((f) => f.parent === r.epoch).children.join(", ")}</span>` : (r.isForkChild ? `<span class="badge b-warn">child of ${r.previous_epoch}</span>` : "—") },
  ], rows, { sortKey: "epoch", onCount: (v, t) => $("chain-count").textContent = `${v} of ${t} rows` });

  $("chain-search").oninput = (e) => chainGrid.setFilter(e.target.value);
  $("chain-forks-only").onchange = (e) => {
    chainGrid.setRows(e.target.checked ? rows.filter((r) => r.isForkParent || r.isForkChild) : rows);
  };
  $("chain-verify-btn").onclick = () => {
    const res = verifyEpochChain(ch.epochs);
    $("chain-verify-out").innerHTML =
      `Browser check: <strong>${res.ok}/${res.checked}</strong> links OK · ${res.broken} broken · ${res.genesis} genesis. ` +
      (res.brokenList.length ? `Broken: ${esc(res.brokenList.join(", "))}` : "No broken links.") +
      ` Forks (one parent, two children): ${ch.forks.map((f) => `${f.parent}→[${f.children.join(",")}]`).join("; ") || "none"}.`;
  };
}

function verifyEpochChain(epochs) {
  const mh = {}; epochs.forEach((e) => mh[e.epoch] = e.manifest_hash);
  let ok = 0, broken = 0, genesis = 0; const brokenList = [];
  for (const e of epochs) {
    const pe = e.previous_epoch, pm = e.previous_manifest_hash;
    if (pe == null || pm == null) { genesis++; continue; }
    if (mh[pe] === pm) ok++; else { broken++; brokenList.push("epoch " + e.epoch); }
  }
  return { checked: epochs.length, ok, broken, genesis, brokenList };
}

/* ---------- GATE view ---------- */
function renderGate() {
  const g = DATA.gate;
  $("gate-meta").textContent = `${g.mutations} mutations · chain tip ${shortHash(g.chain_tip)} · binding ceremony (TEST STUB verifier)`;
  renderGrid($("gate-table").querySelector("thead"), $("gate-table").querySelector("tbody"), [
    { key: "ts", label: "Timestamp (UTC)", fmt: (r) => `<span class="hash">${esc(r.ts)}</span>` },
    { key: "identity", label: "Identity", fmt: (r) => `<span class="hash">${esc(r.identity)}</span>` },
    { key: "transition", label: "Transition", fmt: (r) => `<span class="badge ${r.transition === "BOUND" ? "b-ok" : "b-mut"}">${esc(r.transition)}</span>` },
    { key: "prev_state_sha256", label: "Prev state hash", fmt: (r) => hashLink(r.prev_state_sha256, "gate receipt prev state") },
    { key: "new_state_sha256", label: "New state hash", fmt: (r) => hashLink(r.new_state_sha256, "gate receipt new state") },
    { key: "receipt_id", label: "Receipt ID", fmt: (r) => hashLink(r.receipt_id, "gate receipt id") },
    { key: "note", label: "Note", wrap: true, fmt: (r) => `<span class="notes">${esc(r.note)}</span>` },
    { key: "link_status", label: "Linkage", fmt: (r) => r.link_status === "OK" ? `<span class="badge b-ok">LINK OK</span>` : (r.link_status === "GENESIS" ? `<span class="badge b-mut">GENESIS</span>` : `<span class="badge b-bad">BROKEN</span>`) },
  ], g.receipts, {});
  $("gate-verify-btn").onclick = () => {
    let ok = 0, broken = 0;
    for (let i = 1; i < g.receipts.length; i++)
      if (g.receipts[i - 1].new_state_sha256 === g.receipts[i].prev_state_sha256) ok++; else broken++;
    $("gate-out").innerHTML = `Browser check: <strong>${ok}</strong> links OK, <strong>${broken}</strong> broken, 1 genesis. Chain tip: ${hashLink(g.chain_tip, "gate chain tip")}`;
  };
}

/* ---------- LEDGER view ---------- */
let ledgerGrid, ledgerRows;
function renderLedgers() {
  ledgerRows = DATA.receipts.rows;
  $("ledger-meta").textContent = `${ledgerRows.length} receipt rows · source: ${DATA.receipts.source} · as of ${DATA.receipts.as_of}`;
  const ledgers = [...new Set(ledgerRows.map((r) => r.ledger))].sort();
  $("ledger-filter").innerHTML = '<option value="">all ledgers</option>' + ledgers.map((l) => `<option>${esc(l)}</option>`).join("");
  const driftBadge = (d) => {
    d = String(d || "").trim();
    if (!d) return '<span class="badge b-mut">receipted</span>';
    if (/^drift/i.test(d)) return `<span class="badge b-bad" title="${esc(d)}">DRIFT</span>`;
    if (/unreceipted/i.test(d)) return `<span class="badge b-warn" title="${esc(d)}">UNRECEIPTED</span>`;
    return `<span class="badge b-mut" title="${esc(d)}">note</span>`;
  };
  ledgerGrid = renderGrid($("ledger-table").querySelector("thead"), $("ledger-table").querySelector("tbody"), [
    { key: "ledger", label: "Ledger" },
    { key: "file", label: "File", fmt: (r) => `<span class="hash">${esc(r.file)}</span>` },
    { key: "receipted_sha256", label: "Receipted sha256", fmt: (r) => r.receipted_sha256 ? hashLink(r.receipted_sha256, `${r.ledger} ledger receipt for ${r.file}`) : "—" },
    { key: "time", label: "Receipted (UTC)" },
    { key: "drift", label: "Drift", fmt: (r) => driftBadge(r.drift), search: (r) => r.drift },
  ], ledgerRows, { onCount: (v, t) => $("ledger-count").textContent = `${v} of ${t} rows` });
  const apply = () => {
    const l = $("ledger-filter").value, d = $("ledger-drift").value, q = $("ledger-search").value;
    let rows = ledgerRows;
    if (l) rows = rows.filter((r) => r.ledger === l);
    if (d === "DRIFT") rows = rows.filter((r) => /^drift/i.test(r.drift || ""));
    else if (d === "UNRECEIPTED") rows = rows.filter((r) => /unreceipted/i.test(r.drift || ""));
    else if (d === "receipted") rows = rows.filter((r) => !(r.drift || "").trim());
    ledgerGrid.setRows(rows); ledgerGrid.setFilter(q);
  };
  $("ledger-filter").onchange = apply; $("ledger-drift").onchange = apply; $("ledger-search").oninput = apply;
}

/* ---------- DAG view ---------- */
let dagInit = false;
const dagState = { k: 1, tx: 0, ty: 0, nodes: [], edges: [], byEpoch: {} };

function dagLayout() {
  const epochs = DATA.chain.epochs;
  const byEpoch = {}; epochs.forEach((e) => byEpoch[e.epoch] = e);
  // depth = longest path from a genesis node
  const depth = {};
  const getDepth = (e) => {
    if (depth[e.epoch] != null) return depth[e.epoch];
    const pe = e.previous_epoch;
    if (pe == null || !byEpoch[pe]) return (depth[e.epoch] = 0);
    return (depth[e.epoch] = getDepth(byEpoch[pe]) + 1);
  };
  epochs.forEach(getDepth);
  const layers = {};
  epochs.forEach((e) => { (layers[depth[e.epoch]] ||= []).push(e); });
  Object.values(layers).forEach((arr) => arr.sort((a, b) => a.epoch - b.epoch));
  const forkParents = new Set(DATA.chain.forks.map((f) => f.parent));
  const forkChildren = new Set(DATA.chain.forks.flatMap((f) => f.children));
  const X0 = 70, DX = 150, Y0 = 50, DY = 62;
  const nodes = [];
  Object.keys(layers).sort((a, b) => a - b).forEach((d) => {
    layers[d].forEach((e, i) => {
      nodes.push({
        epoch: e.epoch, x: X0 + d * DX, y: Y0 + i * DY, e,
        cls: e.link_status === "BROKEN" ? "broken" : (e.link_status === "GENESIS" ? "genesis" : (forkChildren.has(e.epoch) ? "forkchild" : "ok")),
        forkChild: forkChildren.has(e.epoch),
      });
    });
  });
  const pos = {}; nodes.forEach((n) => pos[n.epoch] = n);
  const edges = [];
  epochs.forEach((e) => {
    const pe = e.previous_epoch;
    if (pe != null && pos[pe] && pos[e.epoch]) edges.push({ from: pos[pe], to: pos[e.epoch], fork: forkParents.has(pe) });
  });
  Object.assign(dagState, { nodes, edges, byEpoch, pos });
  const maxX = Math.max(...nodes.map((n) => n.x)) + 90;
  const maxY = Math.max(...nodes.map((n) => n.y)) + 60;
  dagState.world = { w: maxX, h: maxY };
}

function dagRender() {
  const cv = $("dag-canvas");
  const { k, tx, ty } = dagState;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "560");
  svg.setAttribute("id", "dag-svg-el");
  const g = document.createElementNS(NS, "g");
  g.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`);
  // edges (elbow connectors)
  for (const ed of dagState.edges) {
    const p = document.createElementNS(NS, "path");
    const x1 = ed.from.x + 22, y1 = ed.from.y, x2 = ed.to.x - 22, y2 = ed.to.y;
    const mx = (x1 + x2) / 2;
    p.setAttribute("d", `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`);
    p.setAttribute("class", "edge" + (ed.fork ? " forkedge" : ""));
    g.appendChild(p);
  }
  // nodes
  for (const n of dagState.nodes) {
    const gn = document.createElementNS(NS, "g");
    gn.setAttribute("class", "node " + n.cls + (dagState.selected === n.epoch ? " selected" : ""));
    gn.setAttribute("transform", `translate(${n.x},${n.y})`);
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("r", "20");
    const t = document.createElementNS(NS, "text");
    t.setAttribute("text-anchor", "middle"); t.setAttribute("dy", "3.5");
    t.textContent = n.epoch;
    gn.appendChild(c); gn.appendChild(t);
    gn.addEventListener("click", (ev) => { ev.stopPropagation(); dagSelect(n.epoch); });
    g.appendChild(gn);
  }
  svg.appendChild(g);
  cv.innerHTML = ""; cv.appendChild(svg);
  dagBindPan(svg);
}

function dagSelect(epoch) {
  dagState.selected = epoch;
  const n = dagState.pos[epoch]; if (!n) return;
  const e = n.e;
  const kids = dagState.edges.filter((ed) => ed.from.epoch === epoch).map((ed) => ed.to.epoch);
  $("dag-side").innerHTML = `
    <h3>Epoch ${e.epoch} ${e.link_status === "OK" ? '<span class="badge b-ok">LINK OK</span>' : e.link_status === "GENESIS" ? '<span class="badge b-mut">GENESIS</span>' : '<span class="badge b-bad">' + esc(e.link_status) + "</span>"}</h3>
    <dl>
      <dt>Timestamp</dt><dd><span class="hash">${esc(e.at)}</span></dd>
      <dt>Manifest</dt><dd>${hashLink(e.manifest_hash, "epoch " + e.epoch + " manifest")}</dd>
      <dt>Prev epoch</dt><dd>${e.previous_epoch ?? "— (genesis)"}</dd>
      <dt>Prev hash</dt><dd>${e.previous_manifest_hash ? hashLink(e.previous_manifest_hash, "epoch " + e.epoch + " previous manifest") : "—"}</dd>
      <dt>Chunks</dt><dd>${e.chunk_count}</dd>
      <dt>Bytes</dt><dd>${(+e.total_bytes).toLocaleString("en-US")}</dd>
      <dt>Schema</dt><dd>v${e.schema_version}</dd>
      <dt>Datasets</dt><dd>${e.datasets.length}: ${esc(e.datasets.join(", "))}</dd>
      <dt>Children</dt><dd>${kids.length ? kids.join(", ") : "none (tip)"}${kids.length > 1 ? ' <span class="badge b-warn">FORK</span>' : ""}</dd>
    </dl>
    <div class="toolbar"><button class="btn small" id="dag-center">Center node</button></div>`;
  $("dag-center").onclick = () => {
    const cv = $("dag-canvas");
    dagState.tx = cv.clientWidth / 2 - n.x * dagState.k;
    dagState.ty = 280 - n.y * dagState.k;
    dagRender();
  };
  dagRender();
}

function dagBindPan(svg) {
  const cv = $("dag-canvas");
  let drag = null;
  svg.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, tx: dagState.tx, ty: dagState.ty }; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    dagState.tx = drag.tx + (e.clientX - drag.x);
    dagState.ty = drag.ty + (e.clientY - drag.y);
    svg.firstChild.setAttribute("transform", `translate(${dagState.tx},${dagState.ty}) scale(${dagState.k})`);
  });
  svg.addEventListener("pointerup", () => drag = null);
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const nk = Math.min(3, Math.max(0.25, dagState.k * f));
    // zoom toward cursor
    const r = cv.getBoundingClientRect();
    const cx = e.clientX - r.left, cy = e.clientY - r.top;
    dagState.tx = cx - (cx - dagState.tx) * (nk / dagState.k);
    dagState.ty = cy - (cy - dagState.ty) * (nk / dagState.k);
    dagState.k = nk;
    svg.firstChild.setAttribute("transform", `translate(${dagState.tx},${dagState.ty}) scale(${dagState.k})`);
  }, { passive: false });
}

function dagFit() {
  const cv = $("dag-canvas");
  const { w, h } = dagState.world;
  dagState.k = Math.min(cv.clientWidth / w, 560 / h, 1.2);
  dagState.tx = 10; dagState.ty = 10;
  dagRender();
}

function initDAG() {
  if (dagInit) return; dagInit = true;
  dagLayout();
  const s = DATA.chain.stats;
  $("dag-meta").textContent = `${s.epoch_built} nodes · ${dagState.edges.length} edges · ${s.fork_points} fork points · amber dashed = fork edge · epochs 1 and 43 were bumped but never built (no nodes)`;
  dagFit();
  $("dag-fit").onclick = dagFit;
  $("dag-reset").onclick = () => { dagState.selected = null; dagFit(); };
  $("dag-zin").onclick = () => { dagState.k = Math.min(3, dagState.k * 1.25); dagRender(); };
  $("dag-zout").onclick = () => { dagState.k = Math.max(0.25, dagState.k / 1.25); dagRender(); };
  $("dag-go").onclick = () => {
    const ep = +$("dag-jump").value;
    if (dagState.pos[ep]) { dagSelect(ep); } else { $("dag-side").innerHTML = `<h3>Epoch ${ep}</h3><p class="count">No built epoch ${ep} in the record.</p>`; }
  };
  $("dag-svg").onclick = () => {
    const svg = $("dag-svg-el"); if (!svg) return;
    const src = new XMLSerializer().serializeToString(svg);
    download("epoch-dag.svg", "image/svg+xml", '<?xml version="1.0"?>\n' + src);
  };
}

/* ---------- TABLES view ---------- */
const TABLE_DEFS = [];
let tableGrid, curDef;

function defineTables() {
  const T = DATA.tables, M = DATA.manifests;
  TABLE_DEFS.push({
    id: "ship", name: "Ship manifest files",
    source: "deploy/SHIP_MANIFEST.md · disk hashes recomputed by this build (AUDIT-BUILD, " + M.generated_at + ") — not a DCLM seal",
    columns: [
      { key: "file", label: "File", fmt: (r) => `<span class="hash">${esc(r.file)}</span>`, csv: (r) => r.file },
      { key: "size_manifest", label: "Size (B)", num: true },
      { key: "sha256_manifest", label: "Manifest sha256", fmt: (r) => hashLink(r.sha256_manifest, r.file + " (ship manifest)"), csv: (r) => r.sha256_manifest },
      { key: "sha256_disk", label: "Disk sha256 (build time)", fmt: (r) => r.sha256_disk ? hashLink(r.sha256_disk, r.file + " (disk at build)") : "—", csv: (r) => r.sha256_disk || "" },
      { key: "drift", label: "Drift", fmt: (r) => r.drift === "MATCH" ? '<span class="badge b-ok">MATCH</span>' : (r.drift === "DRIFT" ? '<span class="badge b-bad">DRIFT</span>' : '<span class="badge b-warn">' + esc(r.drift) + "</span>") },
    ],
    rows: M.ship.files,
  });
  TABLE_DEFS.push({
    id: "registries", name: "Registry files (10)",
    source: "data/MANIFEST.md · provenance REPORTED (VENDOR-RECOVERY from Grok drive extract) · disk hashes recomputed by this build",
    columns: [
      { key: "file", label: "File", fmt: (r) => `<span class="hash">${esc(r.file)}</span>`, csv: (r) => r.file },
      { key: "bytes_manifest", label: "Bytes", num: true },
      { key: "sha256_manifest", label: "Manifest sha256", fmt: (r) => hashLink(r.sha256_manifest, r.file + " (registry manifest)"), csv: (r) => r.sha256_manifest },
      { key: "provenance", label: "Provenance", fmt: (r) => provBadge(r.provenance) },
      { key: "data_label", label: "Data label" },
      { key: "drift", label: "Drift", fmt: (r) => r.drift === "MATCH" ? '<span class="badge b-ok">MATCH</span>' : '<span class="badge b-bad">' + esc(r.drift) + "</span>" },
    ],
    rows: M.registries.files,
  });
  TABLE_DEFS.push({
    id: "founding", name: "Founding board",
    source: "founding-board/founding-board.json · privacy law sounding-board-privacy-v2 (obfuscated to the world, traceable to the law)",
    columns: [
      { key: "obfuscated_unity_id", label: "Obfuscated Unity ID", fmt: (r) => `<span class="hash">${esc(r.obfuscated_unity_id)}</span>`, csv: (r) => r.obfuscated_unity_id },
      { key: "designation", label: "Designation" },
      { key: "cohort", label: "Cohort" },
      { key: "status", label: "Status", fmt: (r) => `<span class="badge b-ok">${esc(r.status)}</span>` },
      { key: "entity_type", label: "Type" },
      { key: "compensation", label: "Compensation" },
      { key: "period", label: "Period" },
      { key: "ack_sha256_recorded", label: "Ack sha256 (recorded)", fmt: (r) => hashLink(r.ack_sha256_recorded, "founding-board acknowledgment (recorded)"), csv: (r) => r.ack_sha256_recorded },
      { key: "ack_match", label: "Ack vs disk", fmt: (r) => r.ack_match === "MATCH" ? '<span class="badge b-ok">MATCH</span>' : '<span class="badge b-bad">MISMATCH</span>' },
    ],
    rows: DATA.founding.members,
  });
  TABLE_DEFS.push({
    id: "suites", name: "Test suites",
    source: T.test_suites.source + " · as of " + T.test_suites.as_of,
    columns: [
      { key: "area", label: "Area" },
      { key: "suite", label: "Suite", fmt: (r) => `<span class="hash">${esc(r.suite)}</span>`, csv: (r) => r.suite },
      { key: "tests", label: "Tests", num: true },
      { key: "pass", label: "Pass", num: true },
      { key: "fail_error", label: "Fail/Error" },
      { key: "status", label: "Status", fmt: (r) => {
          const s = String(r.status || "");
          const cls = /OK/.test(s) ? "b-ok" : (/NOT GREEN|BROKEN/.test(s) ? "b-bad" : "b-warn");
          return `<span class="badge ${cls}">${esc(s)}</span>`;
        } },
      { key: "notes", label: "Notes", wrap: true, fmt: (r) => `<span class="notes">${esc(r.notes)}</span>` },
    ],
    rows: T.test_suites.rows,
  });
  const decidedRows = T.params.decided.map((r) => ({ kind: "DECIDED", parameter: r.parameter, value: r.value, standing: r.standing, ref: r.code_ref }));
  const heldRows = T.params.held.map((r) => ({ kind: "HELD_FOR_DAVID", parameter: r.parameter, value: r.decides, standing: r.status_in_code, ref: r.note }));
  TABLE_DEFS.push({
    id: "params", name: "Economic parameters — decided vs held",
    source: T.params.source + " · held params refuse (HeldParameterError) instead of inventing digits",
    columns: [
      { key: "kind", label: "Standing", fmt: (r) => r.kind === "DECIDED" ? '<span class="badge b-ok">DECIDED</span>' : '<span class="badge b-warn">HELD_FOR_DAVID</span>' },
      { key: "parameter", label: "Parameter", fmt: (r) => `<span class="hash">${esc(r.parameter)}</span>`, csv: (r) => r.parameter },
      { key: "value", label: "Value / decides", wrap: true, fmt: (r) => `<span class="notes">${esc(r.value)}</span>` },
      { key: "standing", label: "Standing / code status", wrap: true },
      { key: "ref", label: "Note / code ref", wrap: true, fmt: (r) => `<span class="notes">${esc(r.ref)}</span>` },
    ],
    rows: decidedRows.concat(heldRows),
  });
  TABLE_DEFS.push({
    id: "mesh", name: "Mesh topology",
    source: T.mesh.source + " · as of " + T.mesh.as_of,
    columns: [
      { key: "level", label: "Level" },
      { key: "count", label: "Count" },
      { key: "source", label: "Source", wrap: true, fmt: (r) => `<span class="notes">${esc(r.source)}</span>` },
    ],
    rows: T.mesh.rows,
  });
  TABLE_DEFS.push({
    id: "benchmarks", name: "Benchmarks",
    source: T.benchmarks.source + " · as of " + T.benchmarks.as_of,
    columns: [
      { key: "team", label: "Team" },
      { key: "metric", label: "Metric" },
      { key: "value", label: "Value", fmt: (r) => `<strong>${esc(r.value)}</strong>` },
      { key: "detail", label: "Detail", wrap: true, fmt: (r) => `<span class="notes">${esc(r.detail)}</span>` },
      { key: "provenance", label: "Prov.", fmt: (r) => provBadge(r.provenance) },
    ],
    rows: T.benchmarks.rows,
  });
  TABLE_DEFS.push({
    id: "gaps", name: "Honest gaps",
    source: T.gaps.source + " · as of " + T.gaps.as_of + " · UNKNOWN is never PASS",
    columns: [
      { key: "id", label: "ID", fmt: (r) => `<span class="hash">${esc(r.id)}</span>`, csv: (r) => r.id },
      { key: "category", label: "Category" },
      { key: "item", label: "Item", wrap: true, fmt: (r) => `<span class="notes">${esc(r.item)}</span>` },
      { key: "status", label: "Status", fmt: (r) => {
          const s = String(r.status || "");
          const cls = /OPEN|FAIL|BROKEN|STALE|NOT BUILT|PENDING|NOT CLOSED/.test(s) ? "b-bad" : (/HELD|UNKNOWN/.test(s) ? "b-warn" : "b-mut");
          return `<span class="badge ${cls}">${esc(s)}</span>`;
        } },
      { key: "provenance", label: "Prov.", fmt: (r) => provBadge(r.provenance) },
    ],
    rows: T.gaps.rows,
  });
  TABLE_DEFS.push({
    id: "ledgers2", name: "Receipt ledger rows (all six ledgers)",
    source: T.receipt_ledgers.source + " · as of " + T.receipt_ledgers.as_of,
    columns: [
      { key: "ledger", label: "Ledger" },
      { key: "file", label: "File", fmt: (r) => `<span class="hash">${esc(r.file)}</span>`, csv: (r) => r.file },
      { key: "receipted_sha256", label: "Receipted sha256", fmt: (r) => r.receipted_sha256 ? hashLink(r.receipted_sha256, r.ledger + " receipt for " + r.file) : "—", csv: (r) => r.receipted_sha256 },
      { key: "time", label: "Time (UTC)" },
      { key: "drift", label: "Drift note", wrap: true, fmt: (r) => `<span class="notes">${esc(r.drift)}</span>` },
    ],
    rows: T.receipt_ledgers.rows,
  });
}

function renderTables() {
  defineTables();
  $("table-picker").innerHTML = TABLE_DEFS.map((d, i) => `<option value="${i}">${esc(d.name)} — ${d.rows.length} rows</option>`).join("");
  $("tables-meta").textContent = TABLE_DEFS.length + " tables · every table exports to CSV · provenance labeled per table";
  const show = (i) => {
    curDef = TABLE_DEFS[i];
    $("table-source").textContent = "Source: " + curDef.source;
    tableGrid = renderGrid($("data-table").querySelector("thead"), $("data-table").querySelector("tbody"),
      curDef.columns, curDef.rows,
      { onCount: (v, t) => $("table-count").textContent = `${v} of ${t} rows` });
    $("table-search").value = "";
  };
  $("table-picker").onchange = (e) => show(+e.target.value);
  $("table-search").oninput = (e) => tableGrid.setFilter(e.target.value);
  $("table-csv").onclick = () => download(curDef.id + ".csv", "text/csv", toCSV(curDef.columns, tableGrid.visibleRows()));
  $("table-json").onclick = () => download(curDef.id + ".json", "application/json", JSON.stringify({ source: curDef.source, rows: tableGrid.visibleRows() }, null, 1));
  show(0);
}

/* ---------- VERIFY tab ---------- */
function vRun(id, fn) {
  const out = $("v-" + id + "-out"), sum = $("v-" + id + "-sum");
  out.innerHTML = "Running…"; sum.textContent = "";
  Promise.resolve().then(fn).then((r) => {
    out.innerHTML = r.html; sum.innerHTML = r.summary;
  }).catch((e) => { out.innerHTML = `<span class="badge b-bad">ERROR</span> ${esc(e.message)}`; });
}

function wireVerify() {
  $("v-chain").onclick = () => vRun("chain", () => {
    const res = verifyEpochChain(DATA.chain.epochs);
    const rows = DATA.chain.epochs.map((e) => {
      const ok = e.link_status === "OK", gen = e.link_status === "GENESIS";
      return `<div class="result-line">${ok ? '<span class="badge b-ok">OK</span>' : gen ? '<span class="badge b-mut">GENESIS</span>' : '<span class="badge b-bad">BROKEN</span>'} epoch ${e.epoch} ← ${e.previous_epoch ?? "—"} <span class="hash">${esc(shortHash(e.manifest_hash))}</span></div>`;
    }).join("");
    return {
      summary: `<span class="badge ${res.broken ? "b-bad" : "b-ok"}">${res.ok}/${res.checked} OK</span>`,
      html: `<div class="caveat">Checked in your browser just now: each epoch's recorded previous_manifest_hash against the recorded manifest_hash of its named previous_epoch. ${DATA.chain.forks.length} fork points present (parent with two children) — forks are recorded structure, not breaks.</div>` + rows,
    };
  });

  $("v-gate").onclick = () => vRun("gate", () => {
    const g = DATA.gate; let ok = 0, broken = 0;
    const rows = g.receipts.map((r, i) => {
      const isOk = i === 0 || g.receipts[i - 1].new_state_sha256 === r.prev_state_sha256;
      if (i > 0) (isOk ? ok++ : broken++);
      return `<div class="result-line">${i === 0 ? '<span class="badge b-mut">GENESIS</span>' : isOk ? '<span class="badge b-ok">OK</span>' : '<span class="badge b-bad">BROKEN</span>'} ${esc(r.transition)} · ${esc(r.ts)} <span class="hash">${esc(shortHash(r.receipt_id))}</span></div>`;
    }).join("");
    return {
      summary: `<span class="badge ${broken ? "b-bad" : "b-ok"}">${ok}/${g.receipts.length - 1} links OK</span>`,
      html: rows,
    };
  });

  $("v-files").onclick = () => vRun("files", async () => {
    const files = DATA.manifests.ship.files.map((f) => ({ path: "../" + f.file, expect: f.sha256_manifest, label: f.file }))
      .concat(DATA.manifests.registries.files.map((f) => ({ path: "../" + f.file, expect: f.sha256_manifest, label: f.file })))
      .concat([{ path: "../founding-board/idris-marquee-helper.md", expect: DATA.founding.members[0].ack_sha256_recorded, label: "founding-board/idris-marquee-helper.md (ack)" }]);
    let pass = 0, fail = 0, err = 0;
    const rows = [];
    for (const f of files) {
      try {
        const res = await fetch(f.path);
        if (!res.ok) { err++; rows.push(`<div class="result-line"><span class="badge b-warn">HTTP ${res.status}</span> ${esc(f.label)} — could not fetch</div>`); continue; }
        const got = await sha256hex(await res.text());
        if (got === f.expect) { pass++; rows.push(`<div class="result-line"><span class="badge b-ok">PASS</span> ${esc(f.label)}</div>`); }
        else { fail++; rows.push(`<div class="result-line"><span class="badge b-bad">FAIL</span> ${esc(f.label)}<br><span class="hash">expected ${esc(f.expect)}</span><br><span class="hash">got&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ${esc(got)}</span></div>`); }
      } catch (e) { err++; rows.push(`<div class="result-line"><span class="badge b-warn">ERROR</span> ${esc(f.label)} — ${esc(e.message)}</div>`); }
    }
    return {
      summary: `<span class="badge ${fail ? "b-bad" : "b-ok"}">${pass} pass</span> <span class="badge ${fail ? "b-bad" : "b-mut"}">${fail} fail</span> <span class="badge b-mut">${err} unfetchable</span>`,
      html: `<div class="caveat">Recomputed in your browser from the files as served to you, compared against the recorded manifest hashes. "Unfetchable" under file:// is a setup limitation — serve this site over HTTP(S) from inside the unity-world tree.</div>` + rows.join(""),
    };
  });

  $("v-ack").onclick = () => vRun("ack", async () => {
    const m = DATA.founding.members[0];
    try {
      const res = await fetch("../founding-board/idris-marquee-helper.md");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const got = await sha256hex(await res.text());
      const ok = got === m.ack_sha256_recorded;
      return {
        summary: ok ? '<span class="badge b-ok">MATCH</span>' : '<span class="badge b-bad">MISMATCH</span>',
        html: `<div class="result-line">recorded: <span class="hash">${esc(m.ack_sha256_recorded)}</span></div>
               <div class="result-line">recomputed: <span class="hash">${esc(got)}</span></div>
               <div class="result-line">${ok ? '<span class="badge b-ok">MATCH</span> the acknowledgment file is byte-identical to the board record.' : '<span class="badge b-bad">MISMATCH</span>'}</div>`,
      };
    } catch (e) {
      return { summary: '<span class="badge b-warn">UNFETCHABLE</span>', html: `Could not fetch the file (${esc(e.message)}). Serve over HTTP(S) from inside the unity-world tree.` };
    }
  });
}

/* ---------- init ---------- */
(async function init() {
  try {
    await loadAll();
    renderChain(); renderGate(); renderLedgers(); renderTables(); wireVerify();
  } catch (e) {
    document.querySelector("main").innerHTML =
      `<div class="caveat"><strong>Failed to load audit data:</strong> ${esc(e.message)}<br>
       This site reads <span class="kbd">data/*.json</span> relative to itself — serve <span class="kbd">audit/</span> over HTTP(S) or rebuild with <span class="kbd">python3 build_audit.py</span>.</div>`;
  }
})();
