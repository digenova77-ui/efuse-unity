#!/usr/bin/env python3
"""DualisCapax swarm node heartbeat — Layer 1 (the diamond floor), portable edition.

Runs on a stock Ubuntu 22.04 box. Pure Python 3 standard library — no pip
packages, no network calls, no agent runtime required.

Every run appends ONE tick to /var/lib/dualis/heartbeat.jsonl:
  node_id, box label, logical tick, UTC time, uptime, load, disk, memory.

Each tick is SIGNED with the lane key (born on-lane at first breath, see
signing/lane.py) — S13: remote health streams are signed by the lane key,
so a planted heartbeat.jsonl for a dead lane fails verification. Unsigned
ticks (pre-regime) carry an honest marker.

Honesty law (same as the main loop): where a figure is not measurable,
record UNKNOWN, never zero.

Usage:
  node-heartbeat.py [--label NAME]     # one tick, print the entry
  node-heartbeat.py --init             # create /etc/dualis/node-id if missing
"""
import json
import os
import platform
import socket
import sys
import time
from datetime import datetime, timezone


def _load_signing():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in ("/opt/dualis/signing",
                 os.path.join(here, "..", "signing"),
                 os.path.join(here, "signing")):
        if os.path.exists(os.path.join(cand, "__init__.py")):
            parent = os.path.dirname(os.path.abspath(cand))
            if parent not in sys.path:
                sys.path.insert(0, parent)
            try:
                import signing.lane as lanelib
                return lanelib
            except Exception:
                continue
    return None

STATE_DIR = os.environ.get("DUALIS_STATE_DIR", "/var/lib/dualis")
ETC_DIR = os.environ.get("DUALIS_ETC_DIR", "/etc/dualis")
LOG = os.path.join(STATE_DIR, "heartbeat.jsonl")
NODE_ID_FILE = os.path.join(ETC_DIR, "node-id")
TICK_FILE = os.path.join(STATE_DIR, "tick")


def read_first(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def ensure_node_id():
    os.makedirs(ETC_DIR, exist_ok=True)
    nid = read_first(NODE_ID_FILE)
    if nid:
        return nid
    import secrets
    nid = "node-" + secrets.token_hex(6)
    tmp = NODE_ID_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(nid + "\n")
    os.replace(tmp, NODE_ID_FILE)
    return nid


def next_tick():
    last = 0
    try:
        with open(TICK_FILE, "r", encoding="utf-8") as f:
            last = int(f.read().strip() or 0)
    except (OSError, ValueError):
        pass
    nxt = last + 1
    tmp = TICK_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(nxt) + "\n")
    os.replace(tmp, TICK_FILE)
    return nxt


def uptime_seconds():
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError):
        return None


def mem_info():
    try:
        info = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0].rstrip(":") in (
                        "MemTotal", "MemAvailable"):
                    info[parts[0].rstrip(":")] = int(parts[1])  # kB
        return info or None
    except OSError:
        return None


def disk_info():
    try:
        import shutil
        u = shutil.disk_usage("/")
        return {"total_gb": round(u.total / 1e9, 2),
                "free_gb": round(u.free / 1e9, 2)}
    except OSError:
        return None


def main(argv):
    label = None
    for i, a in enumerate(argv):
        if a == "--label" and i + 1 < len(argv):
            label = argv[i + 1]
        if a == "--init":
            print(ensure_node_id())
            return 0

    os.makedirs(STATE_DIR, exist_ok=True)
    node_id = ensure_node_id()
    tick = next_tick()
    up = uptime_seconds()
    try:
        load = list(os.getloadavg())
    except OSError:
        load = None

    entry = {
        "node_id": node_id,
        "label": label or os.environ.get("DUALIS_LABEL")
                 or socket.gethostname(),
        "loop_tick": tick,
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument": "swarm-node/node-heartbeat.py — Layer 1, portable",
        "box": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uptime_seconds": up if up is not None else "UNKNOWN",
            "load_1_5_15": load if load is not None else "UNKNOWN",
            "memory_kb": mem_info() if mem_info() is not None else "UNKNOWN",
            "disk": disk_info() if disk_info() is not None else "UNKNOWN",
            "boot_epoch": int(time.time() - up) if up else "UNKNOWN",
        },
    }

    # Sign the tick with the lane key (S13) BEFORE writing — one JSON
    # object per line, signature included. Unsigned only if the signing
    # module or lane key is unavailable — marked honestly, never faked.
    lanelib = _load_signing()
    if lanelib is not None:
        try:
            seed, _pub = lanelib.ensure_lane_keypair(ETC_DIR)
            sig_b64, key_id = lanelib.sign_record_body(entry, seed)
            entry["sig"] = sig_b64
            entry["key_id"] = key_id
        except Exception as e:
            entry["sig"] = "none"
            entry["sig_error"] = "signing failed: %s" % str(e)[:80]
    else:
        entry["sig"] = "none"
        entry["sig_note"] = "signing module unavailable (pre-regime)"

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(json.dumps({"node_id": node_id, "label": entry["label"],
                      "loop_tick": tick, "at_utc": entry["at_utc"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
