#!/usr/bin/env python3
"""DualisCapax swarm node — lane attestation chain (two-lane loop, Layer 2 local).

Each lane appends hash-chained attestations for the shifts it runs, fully
autonomous — never blocks on the other lane. Lanes exchange ONLY these
proofs (deltas, never bulk state); the merge happens asynchronously elsewhere.

Record format (one JSON object per line in /var/lib/dualis/attestations.jsonl):
  lane, node_id, shift_id, seq, prev_hash, at_utc,
  claims_touched[], verdict_hashes{}, note,
  lane_pubkey (hex, on the birth record — seq 1),
  sig (Ed25519 over the canonical body), key_id (signer fingerprint),
  hash

The hash covers the canonical JSON of the record WITHOUT the hash field
itself (but INCLUDING sig/key_id), and includes prev_hash — so the chain
is tamper-evident. Signatures make it tamper-PROOF against anyone without
the lane key: chain verification is signature verification (C2 closed).

Lane identity = the birth pubkey. The birth record (seq 1) carries
lane_pubkey and is self-certifying: its sig must verify against the
pubkey it carries. Later records bind via key_id.

If the signing module is unavailable (pre-regime bundle), records are
written UNSIGNED with an honest marker — availability of the heartbeat
outranks purity during transition, and verifiers treat unsigned records
per their own rules (never as proven).

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


def _load_signing():
    """Locate the signing package: /opt/dualis/signing on the lane,
    sibling ../signing in the repo, or ./signing. Returns the module or None."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in ("/opt/dualis/signing",
                 os.path.join(here, "..", "signing"),
                 os.path.join(here, "signing")):
        init = os.path.join(cand, "__init__.py")
        if os.path.exists(init):
            parent = os.path.dirname(os.path.abspath(cand))
            if parent not in sys.path:
                sys.path.insert(0, parent)
            try:
                import signing.envelope as envelope
                import signing.lane as lanelib
                import signing.backend as bend
                return envelope, lanelib, bend
            except Exception:
                continue
    return None

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
    """Verify hash links AND signatures. Returns (ok, n, detail).

    Signature rule: the birth record (seq 1) must carry lane_pubkey and be
    self-certifying (sig verifies against the pubkey it carries). Later
    records must carry a sig whose key_id matches the birth pubkey.
    Records without sig are LEGACY (pre-regime): hash-checked only, and
    the detail says so honestly — never counted as proven.
    """
    recs = read_chain() if recs is None else recs
    signing = _load_signing()
    prev = GENESIS
    lane_pub = None
    signed_n = 0
    for i, r in enumerate(recs):
        if r.get("prev_hash") != prev:
            return False, i, "prev_hash mismatch at seq %s" % r.get("seq")
        body = {k: v for k, v in r.items() if k != "hash"}
        if sha256(canonical(body)) != r.get("hash"):
            return False, i, "hash mismatch at seq %s" % r.get("seq")
        sig = r.get("sig")
        if signing is not None and sig and sig != "none":
            env, lanelib, bend = signing
            try:
                if r.get("seq") == 1:
                    if not r.get("lane_pubkey"):
                        return False, i, "birth record lacks lane_pubkey"
                    lane_pub = bytes.fromhex(r["lane_pubkey"])
                    if len(lane_pub) != 32:
                        return False, i, "birth lane_pubkey malformed"
                if lane_pub is None:
                    return False, i, "no lane pubkey pinned before seq %s" % r.get("seq")
                lanelib.verify_record_signature(r, lane_pub)
                signed_n += 1
            except Exception as e:
                return False, i, "signature invalid at seq %s: %s" % (r.get("seq"), e)
        prev = r["hash"]
    detail = "chain valid, %d records, %d/%d signed" % (len(recs), signed_n, len(recs))
    if signing is None:
        detail += " (signing module unavailable — legacy check only)"
    elif signed_n < len(recs):
        detail += " (legacy unsigned records present — not proven)"
    return True, len(recs), detail


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
    # Sign the record (C2). The lane keypair is born on-lane at first
    # breath and never leaves it. Birth record carries the pubkey.
    signing = _load_signing()
    if signing is not None:
        env, lanelib, bend = signing
        try:
            seed, pub = lanelib.ensure_lane_keypair(ETC_DIR)
            if body["seq"] == 1:
                body["lane_pubkey"] = pub.hex()
            sig_b64, key_id = lanelib.sign_record_body(body, seed)
            body["sig"] = sig_b64
            body["key_id"] = key_id
        except Exception as e:
            body["sig"] = "none"
            body["sig_error"] = "signing failed: %s" % str(e)[:80]
    else:
        body["sig"] = "none"
        body["sig_note"] = "signing module unavailable (pre-regime)"
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
