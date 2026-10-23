/**
 * Drop-in routes for dualiscapax-landing/_worker.js
 * Pure, no-store, fail-closed.
 */
import {
  omniSnapshot,
  frontierReport,
  DEFAULT_FACETS,
  verifyReceiptChain,
  standingProbe,
} from "./diamond_edge.js";

export function edgeRoutes(url, request) {
  const p = url.pathname;
  if (p === "/omni" || p === "/omni/") return json(omniSnapshot(DEFAULT_FACETS));
  if (p === "/frontier" || p === "/frontier/") return json(frontierReport(DEFAULT_FACETS));
  if (p === "/purity" || p === "/purity/") return text(purityText());
  if (p === "/standing-probe" || p === "/standing-probe/") return json(standingProbe());
  if (p === "/receipts/verify" && request.method === "POST") {
    return request.json().then((body) => json(verifyReceiptChain(body.receipts || []))).catch(() => json({ ok: false, reason: "bad json" }, 400));
  }
  return null;
}

function purityText() {
  const o = omniSnapshot(DEFAULT_FACETS);
  const lines = ["DIAMOND PURITY (edge)", "floor: " + (o.diamond.floor_holds ? "HOLD" : "FAIL")];
  for (const f of o.diamond.facets) lines.push(`${f.verdict === "PASS" ? "◆" : "◇"} ${f.name} ${f.verdict}`);
  lines.push("frontier_claimable: " + o.frontier.ceiling_claimable);
  lines.push("boundary: NOT_FOR_EMISSION");
  return lines.join("\n");
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}
function text(body) {
  return new Response(body + "\n", {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}
