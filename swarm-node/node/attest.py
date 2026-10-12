#!/usr/bin/env python3
"""DualisCapax swarm node — lane attestation chain (two-lane loop, Layer 2 local).

Each lane appends hash-chained attestations for the shifts it runs, fully
autonomous — never blocks on the other lane. Lanes exchange ONLY these
proofs (deltas, never bulk state); the merge happens asynchronously elsewhere.

Record format (one JSON object per line in /var/lib/dualis/attestations.jsonl):
  lane, node_id, shift_id, seq, prev_hash, at_utc,
  claims_touched[], verdict_hashes{}, note, hash

The hash covers the canonical JSON of the record WITHOUT the hash field
itself, and includes prev_hash — so the chain is tamper-evident. GENESIS is
the prev_hash of the first record.

Usage:
  attest.py --shift-id ID --claims c1,c2 --verdict k1=hash1,k2=hash2 [--note TEXT]
  attest.py --verify            # verify the local chain, print result
  attest.py --export            # print the whole chain (for handoff to merge)
"""
import hashlib
import json
import os
import socket
import sys
from datetime import datetime, timezone

STATE_DIR = os.environ.get("DUALIS_STATE_DIR", "/var/lib/dualis")
ETC_DIR = os.environ.get("DUALIS_ETC_DIR", "/etc/dualis")
CHAIN = os.path.join(STATE_DIR, "attestations.jsonl")
NODE_ID_FILE = os.path.join(ETC_DIR, "node-id")
LANE_FILE = os.path.join(ETC_DIR, "lane")
GENESIS = "GENESIS"


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_chain():
    recs = []
    try:
        with open(CHAIN, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    except OSError:
        pass
    return recs


def node_id():
    try:
        with open(NODE_ID_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "uninitialized"


def lane_name():
    return (os.environ.get("DUALIS_LANE")
            or read_first(LANE_FILE)
            or socket.gethostname())


def read_first(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def verify(recs=None):
    recs = read_chain() if recs is None else recs
    prev = GENESIS
    for i, r in enumerate(recs):
        if r.get("prev_hash") != prev:
            return False, i, "prev_hash mismatch at seq %s" % r.get("seq")
        body = {k: v for k, v in r.items() if k != "hash"}
        if sha256(canonical(body)) != r.get("hash"):
            return False, i, "hash mismatch at seq %s" % r.get("seq")
        prev = r["hash"]
    return True, len(recs), "chain valid"


def cmd_append(args):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--shift-id", required=True)
    p.add_argument("--claims", default="")
    p.add_argument("--verdict", default="", dest="verdicts")
    p.add_argument("--note", default="")
    ns = p.parse_args(args)

    recs = read_chain()
    prev = recs[-1]["hash"] if recs else GENESIS
    verdict_hashes = {}
    for pair in ns.verdicts.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            verdict_hashes[k.strip()] = v.strip()

    body = {
        "lane": lane_name(),
        "node_id": node_id(),
        "shift_id": ns.shift_id,
        "seq": len(recs) + 1,
        "prev_hash": prev,
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claims_touched": [c.strip() for c in ns.claims.split(",") if c.strip()],
        "verdict_hashes": verdict_hashes,
        "note": ns.note,
    }
    body["hash"] = sha256(canonical(body))

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CHAIN, "a", encoding="utf-8") as f:
        f.write(canonical(body) + "\n")
    print(json.dumps({"seq": body["seq"], "hash": body["hash"],
                      "shift_id": body["shift_id"]}, indent=2))


def main(argv):
    if "--verify" in argv:
        ok, n, msg = verify()
        print(json.dumps({"valid": ok, "records": n, "detail": msg}, indent=2))
        return 0 if ok else 1
    if "--export" in argv:
        for r in read_chain():
            print(canonical(r))
        return 0
    return cmd_append(argv) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
