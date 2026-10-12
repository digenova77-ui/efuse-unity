#!/usr/bin/env python3
"""DualisCapax cluster balancer — the ingress diamond (collapse node).

The load balancer is an interconnect: many clients in, one routing decision
out. By David's law it is a diamond with its own quantum node
(qnode-cluster-ingress).

DESIGN (honest):
- Geography is DNS's job. The balancer's brain computes ONE routing table:
  region -> ordered list of healthy lanes. Two actuators publish it:
  (1) geodns-agent.py writes it into the DNS answers (primary path),
  (2) proxy.py serves it for direct HTTP hits (fallback path).
- Per-request routing emits NO trace. That would drown the chain.
- Only MEANINGFUL decisions collapse: lane dark / recovered, a region's
  answer changed, a new lane came online, split-brain detected.
  Each collapse emits one trace in the identical unreal-memory trace format.

Trace format (matches unreal memory standard, collapse_events):
  node_id, interconnect, lane, kind, possibility_space,
  possibility_space_hash, measurement_basis, outcome, measured_at,
  prev_trace_hash, trace_hash

The chain is hash-linked per node with a GENESIS seed — the same convention
as the lane attestation chain (attest.py). kind is one of
collapse | gap | dispute.

Health states (from health.py): UP | DOWN | UNKNOWN.
UNKNOWN is fail-closed: never eligible for new traffic.

Usage:
  balancer.py --table <health.json>     # print routing table for a health snapshot
  balancer.py --decide <health.json>    # diff vs last table; emit collapse trace if changed
  balancer.py --verify                  # verify the trace chain
  balancer.py --export                  # print the whole trace chain
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

STATE_DIR = os.environ.get("DUALIS_CLUSTER_STATE", "/var/lib/dualis/cluster")
TRACE_LOG = os.path.join(STATE_DIR, "cluster-traces.jsonl")
TABLE_FILE = os.path.join(STATE_DIR, "routing-table.json")
GENESIS = "GENESIS"

NODE_ID = "qnode-cluster-ingress"
INTERCONNECT = "cluster-ingress"
MEASUREMENT_BASIS = "balancer:nearest-healthy+attestation-stream"

# Lane registry. regions_served lists the DNS views that prefer this lane,
# in preference order. Reserved lanes are commented: they activate the day
# their lane comes online (no code change, just uncomment + health).
LANES = {
    "DCLM": {
        "ip": "108.61.17.141",
        "region": "us-east",
        "label": "New Jersey",
    },
    "EUROPE": {
        "ip": "45.76.33.16",
        "region": "eu-west",
        "label": "Amsterdam",
    },
    # Reserved future lanes (staged, not live):
    # "TOKYO":     {"ip": None, "region": "ap-northeast", "label": "Tokyo"},
    # "SINGAPORE": {"ip": None, "region": "ap-southeast", "label": "Singapore"},
    # "SAOPAULO":  {"ip": None, "region": "sa-east",      "label": "Sao Paulo"},
    # "SYDNEY":    {"ip": None, "region": "oceania",      "label": "Sydney"},
    # "USWEST":    {"ip": None, "region": "us-west",      "label": "US West"},
}

# DNS views -> lane preference order (nearest first). Approximate by
# real-world RTT; documented, not measured live.
VIEW_PREFERENCE = {
    "americas": ["DCLM", "EUROPE"],
    "europe":   ["EUROPE", "DCLM"],
    "mea":      ["EUROPE", "DCLM"],
    "apac":     ["DCLM", "EUROPE"],
    "oceania":  ["DCLM", "EUROPE"],
    "default":  ["DCLM", "EUROPE"],
}


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def live_lanes():
    """Lanes with a real IP — the only ones routable today."""
    return {k: v for k, v in LANES.items() if v.get("ip")}


def compute_table(health):
    """Build region -> [lane...] from a health snapshot.

    health: {lane_id: {"state": "UP"|"DOWN"|"UNKNOWN", ...}}
    UNKNOWN is fail-closed: not eligible.
    """
    lanes = live_lanes()
    table = {}
    for view, pref in VIEW_PREFERENCE.items():
        ordered = [l for l in pref
                   if l in lanes and health.get(l, {}).get("state") == "UP"]
        table[view] = ordered
    return table


def route(view, table):
    """Per-request lane choice. Emits no trace. Returns lane id or None."""
    cands = table.get(view) or table.get("default") or []
    return cands[0] if cands else None


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def read_traces():
    recs = []
    try:
        with open(TRACE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    except OSError:
        pass
    return recs


def verify_traces(recs=None):
    recs = read_traces() if recs is None else recs
    prev = GENESIS
    for r in recs:
        if r.get("prev_trace_hash") != prev:
            return False, "prev_trace_hash mismatch at %s" % r.get("measured_at")
        body = {k: v for k, v in r.items() if k != "trace_hash"}
        if sha256(canonical(body)) != r.get("trace_hash"):
            return False, "trace_hash mismatch at %s" % r.get("measured_at")
        if r.get("possibility_space_hash") != sha256(r.get("possibility_space", "")):
            return False, "possibility_space_hash mismatch at %s" % r.get("measured_at")
        prev = r["trace_hash"]
    return True, "chain valid, %d traces" % len(recs)


def emit_trace(kind, possibility_space, outcome):
    """Collapse one meaningful decision. Appends to the node's chain."""
    recs = read_traces()
    prev = recs[-1]["trace_hash"] if recs else GENESIS
    body = {
        "node_id": NODE_ID,
        "interconnect": INTERCONNECT,
        "lane": "cluster",
        "kind": kind,
        "possibility_space": possibility_space,
        "possibility_space_hash": sha256(possibility_space),
        "measurement_basis": MEASUREMENT_BASIS,
        "outcome": outcome,
        "measured_at": utcnow(),
        "prev_trace_hash": prev,
    }
    body["trace_hash"] = sha256(canonical(body))
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(TRACE_LOG, "a", encoding="utf-8") as f:
        f.write(canonical(body) + "\n")
    return body


def describe_change(old, new, health):
    """Human-readable account of what changed between routing tables."""
    lines = []
    for view in VIEW_PREFERENCE:
        o, n = old.get(view, []), new.get(view, [])
        if o != n:
            lines.append("%s: [%s] -> [%s]" % (
                view, ",".join(o) or "-", ",".join(n) or "-"))
    states = ", ".join("%s=%s" % (l, health.get(l, {}).get("state", "?"))
                       for l in sorted(live_lanes()))
    return "routing change | health(%s) | %s" % (states, "; ".join(lines))


def decide(health):
    """Diff the computed table vs the last published one.

    Emits exactly one collapse trace when the table changed, none when it
    didn't. Returns (changed: bool, table: dict, trace_or_None).
    """
    new = compute_table(health)
    old = read_json(TABLE_FILE) or {}
    if old == new:
        return False, new, None
    space = "routing table for views %s under health %s" % (
        ",".join(sorted(VIEW_PREFERENCE)),
        json.dumps({l: health.get(l, {}).get("state", "?")
                    for l in sorted(live_lanes())}, sort_keys=True))
    trace = emit_trace("collapse", space, describe_change(old, new, health))
    write_json(TABLE_FILE, new)
    return True, new, trace


def main(argv):
    if "--verify" in argv:
        ok, msg = verify_traces()
        print(json.dumps({"valid": ok, "detail": msg}, indent=2))
        return 0 if ok else 1
    if "--export" in argv:
        for r in read_traces():
            print(canonical(r))
        return 0
    if "--table" in argv:
        i = argv.index("--table")
        health = read_json(argv[i + 1]) or {}
        print(json.dumps(compute_table(health), indent=2, sort_keys=True))
        return 0
    if "--decide" in argv:
        i = argv.index("--decide")
        health = read_json(argv[i + 1]) or {}
        changed, table, trace = decide(health)
        print(json.dumps({
            "changed": changed,
            "table": table,
            "trace_hash": trace["trace_hash"] if trace else None,
        }, indent=2, sort_keys=True))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
