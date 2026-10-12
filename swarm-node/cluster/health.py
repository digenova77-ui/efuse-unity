#!/usr/bin/env python3
"""DualisCapax cluster health consumer — one source of truth, no new stack.

Reads the lanes' own attestation/heartbeat stream and exposes lane UP/DOWN.
The balancer AND the GeoDNS agent consume this. No separate monitoring.

Sources (in priority order):
  1. Local lane files:  <lane_state_dir>/heartbeat.jsonl + attestations.jsonl
     (authoritative for the lane this box IS).
  2. Remote lane exports: <remote_dir>/<lane>/heartbeat.jsonl (populated by
     the object-store rendezvous when it exists; see the deploy doc).

Honesty law:
  - UP      = fresh heartbeat AND (no attestation chain OR a valid one).
  - DOWN    = heartbeat stale beyond stale_after_secs, OR attestation chain
              broken (tamper/corruption — never route there).
  - UNKNOWN = no heartbeat data at all. Fail-closed: not eligible for traffic.
              Reported as UNKNOWN, never invented as UP.

A lane that has never come online reports UNKNOWN — that is the correct
staged state, not a failure.

Usage:
  health.py --status [--state-dir D] [--remote-dir D] [--stale-after S]
  health.py --watch  [--state-dir D] [--remote-dir D] [--stale-after S] [--interval N]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

DEFAULT_STATE_DIR = "/var/lib/dualis"
DEFAULT_STALE_AFTER = 300  # seconds


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_jsonl(path):
    recs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return recs


def verify_attestations(recs):
    """Same chain rule as attest.py: GENESIS seed, hash-linked."""
    prev = "GENESIS"
    for r in recs:
        if r.get("prev_hash") != prev:
            return False, "prev_hash mismatch at seq %s" % r.get("seq")
        body = {k: v for k, v in r.items() if k != "hash"}
        if sha256(canonical(body)) != r.get("hash"):
            return False, "hash mismatch at seq %s" % r.get("seq")
        prev = r["hash"]
    return True, "chain valid, %d records" % len(recs)


def parse_ts(s):
    """Parse the heartbeat/attestation timestamps we emit. None if unknown."""
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def assess_lane(lane_id, lane_dir, stale_after):
    """Assess one lane from its stream files. Never invents UP."""
    hb = read_jsonl(os.path.join(lane_dir, "heartbeat.jsonl"))
    at = read_jsonl(os.path.join(lane_dir, "attestations.jsonl"))
    if not hb and not at:
        return {"lane": lane_id, "state": "UNKNOWN",
                "reason": "no heartbeat or attestation data"}

    # Freshness from the newest heartbeat tick we can date.
    ages = []
    now = datetime.now(timezone.utc)
    for tick in hb:
        ts = parse_ts(tick.get("at_utc") or tick.get("ts") or tick.get("time"))
        if ts:
            ages.append((now - ts).total_seconds())
    if ages:
        age = min(ages)
    elif at:
        # No dated heartbeats but attestations exist: fall back to the
        # newest attestation timestamp.
        ts = parse_ts(at[-1].get("at_utc"))
        age = (now - ts).total_seconds() if ts else None
    else:
        age = None

    if age is None:
        return {"lane": lane_id, "state": "UNKNOWN",
                "reason": "data present but undated"}
    if age < 0:
        return {"lane": lane_id, "state": "UNKNOWN",
                "reason": "clock skew: tick from the future"}

    if at:
        ok, detail = verify_attestations(at)
        if not ok:
            return {"lane": lane_id, "state": "DOWN",
                    "reason": "attestation chain broken: " + detail,
                    "last_tick_age_secs": round(age, 1)}
    if age > stale_after:
        return {"lane": lane_id, "state": "DOWN",
                "reason": "heartbeat stale: %.0fs > %ds" % (age, stale_after),
                "last_tick_age_secs": round(age, 1)}
    return {"lane": lane_id, "state": "UP",
            "reason": "heartbeat fresh",
            "last_tick_age_secs": round(age, 1)}


def snapshot(lanes, state_dir=DEFAULT_STATE_DIR, remote_dir=None,
             stale_after=DEFAULT_STALE_AFTER):
    """lanes: {lane_id: {"local": bool}}. Local lanes read state_dir;
    remote lanes read remote_dir/<lane_id>/ (UNKNOWN until populated)."""
    out = {}
    for lane_id, cfg in lanes.items():
        if cfg.get("local"):
            d = state_dir
        elif remote_dir:
            d = os.path.join(remote_dir, lane_id)
        else:
            out[lane_id] = {"lane": lane_id, "state": "UNKNOWN",
                            "reason": "no remote stream configured"}
            continue
        out[lane_id] = assess_lane(lane_id, d, stale_after)
    return out


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--state-dir", default=DEFAULT_STATE_DIR)
    p.add_argument("--remote-dir", default=None)
    p.add_argument("--stale-after", type=int, default=DEFAULT_STALE_AFTER)
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--lanes", default="DCLM:local,EUROPE:remote",
                   help="lane_id:local|remote,...")
    ns = p.parse_args(argv)

    lanes = {}
    for item in ns.lanes.split(","):
        if ":" in item:
            lid, kind = item.split(":", 1)
            lanes[lid.strip()] = {"local": kind.strip() == "local"}

    def one():
        return snapshot(lanes, ns.state_dir, ns.remote_dir, ns.stale_after)

    if ns.watch:
        last = None
        while True:
            cur = one()
            if cur != last:
                print(json.dumps(cur, indent=2, sort_keys=True), flush=True)
                last = cur
            time.sleep(ns.interval)
        return 0
    if ns.status or True:
        print(json.dumps(one(), indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
