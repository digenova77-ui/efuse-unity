/**
 * Drop-in for dualiscapax-landing/_worker.js
 * Serves pure Omni / frontier status at the edge.
 * No secrets. No mutation. Fail-closed.
 *
 * Add near the top:
 *   import { omniSnapshot, frontierReport, DEFAULT_FACETS } from "./edge/diamond_edge.js";
 * (or inline the functions if the worker is a single file)
 *
 * Then in the fetch handler, before ASSETS fallback:
 */
export function edgeRoutes(url) {
  if (url.pathname === "/omni" || url.pathname === "/omni/") {
    return json(omniSnapshot(DEFAULT_FACETS));
  }
  if (url.pathname === "/frontier" || url.pathname === "/frontier/") {
    return json(frontierReport(DEFAULT_FACETS));
  }
  return null;
}

function json(body) {
  return new Response(JSON.stringify(body, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

// Re-export so a bundler or single-file worker can include them.
export { omniSnapshot, frontierReport, DEFAULT_FACETS } from "./diamond_edge.js";
