#!/usr/bin/env python3
"""DualisCapax cluster proxy — the optional HTTP front for the balancer.

Most traffic is routed by GeoDNS (the primary path). This proxy exists for
direct hits on the balancer itself: it applies the same routing table and
either redirects (302) to the chosen lane or answers an honest 503 naming
the cause when no lane is healthy.

No fake upstreaming: this proxy does NOT fetch from lanes and re-serve.
It redirects, so the client holds a direct, auditable connection to the
lane. stdlib only.

Usage:
  proxy.py [--port P] [--table PATH] [--health PATH]
  The routing table is read per request (written by balancer.py --decide).
  The health snapshot is read per request (written by health.py --status).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

TABLE_PATH = os.environ.get("DUALIS_ROUTING_TABLE", "/var/lib/dualis/cluster/routing-table.json")
HEALTH_PATH = os.environ.get("DUALIS_HEALTH_SNAPSHOT", "/var/lib/dualis/cluster/health.json")

LANE_URL = {
    "DCLM": "http://108.61.17.141",
    "EUROPE": "http://45.76.33.16",
}

VIEW_BY_HOST = {}  # optional: {"eu.example.com": "europe"} — configured at deploy


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "dualis-cluster-proxy/1"

    def log_message(self, *a):
        pass

    def _view(self):
        host = self.headers.get("Host", "").split(":")[0].lower()
        return VIEW_BY_HOST.get(host, "default")

    def do_GET(self):
        table = read_json(TABLE_PATH) or {}
        health = read_json(HEALTH_PATH) or {}
        view = self._view()
        cands = table.get(view) or table.get("default") or []
        if cands and cands[0] in LANE_URL:
            lane = cands[0]
            dest = LANE_URL[lane] + self.path
            self.send_response(302)
            self.send_header("Location", dest)
            self.send_header("X-Dualis-Lane", lane)
            self.send_header("X-Dualis-View", view)
            self.end_headers()
            return
        # Honest 503: name the cause, never a blank failure.
        states = ", ".join("%s=%s" % (l, (health.get(l) or {}).get("state", "?"))
                           for l in sorted(set(list(table.get("default", [])) +
                                                  list(health.keys()))))
        body = ("no healthy lane for view '%s'%s\n" %
                (view, (" (health: %s)" % states) if states else ""))
        data = body.encode()
        self.send_response(503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Dualis-View", view)
        self.end_headers()
        self.wfile.write(data)

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8080)
    ns = p.parse_args(argv)
    srv = HTTPServer(("127.0.0.1", ns.port), Handler)
    print("dualis cluster proxy on 127.0.0.1:%d" % ns.port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
