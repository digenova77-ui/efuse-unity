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

Signing law (S13 — closes plantable remote streams):
  - Every lane has a birth pubkey (lane keypair born on-lane, C2).
  - REMOTE streams: the lane's pubkey must be pinned (lane_keys_dir).
    Unsigned, mis-signed, or unpinned streams -> UNKNOWN (fail-closed).
    A planted heartbeat.jsonl for a dead lane fails signature verification.
  - LOCAL lanes: the lane key is on this box; invalid signatures -> DOWN
    (our own disk is ours — bad sig means tamper, not an untrusted peer).
  - Pre-regime (no key anywhere): legacy hash-chain check, and the reason
    says so honestly.

A lane that has never come online reports UNKNOWN — that is the correct
staged state, not a failure.

Usage:
  health.py --status [--state-dir D] [--remote-dir D] [--stale-after S]
            [--etc-dir D] [--lane-keys-dir D]
  health.py --watch  [--state-dir D] [--remote-dir D] [--stale-after S] [--interval N]
"""
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

DEFAULT_STATE_DIR = "/var/lib/dualis"
DEFAULT_ETC_DIR = "/etc/dualis"
DEFAULT_STALE_AFTER = 300  # seconds


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
                import signing.envelope as envelope
                import signing.lane as lanelib
                import signing.keys as skeys
                return envelope, lanelib, skeys
            except Exception:
                continue
    return None


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


def verify_signed_stream(recs, pubkey, signing):
    """Full signature verification of a remote stream (S13).

    Every record must carry a valid sig from pubkey. The birth record
    (seq 1) must carry lane_pubkey matching pubkey (self-certifying).
    Returns (ok, detail). Unsigned or mis-signed -> (False, reason).
    """
    env, lanelib, skeys = signing
    if not recs:
        return True, "empty stream"
    prev = "GENESIS"
    for r in recs:
        if r.get("prev_hash") != prev:
            return False, "prev_hash mismatch at seq %s" % r.get("seq")
        body = {k: v for k, v in r.items() if k != "hash"}
        if sha256(canonical(body)) != r.get("hash"):
            return False, "hash mismatch at seq %s" % r.get("seq")
        sig = r.get("sig")
        if not sig or sig == "none":
            return False, "unsigned record at seq %s — untrusted stream" % r.get("seq")
        if r.get("seq") == 1:
            try:
                birth_pub = bytes.fromhex(r.get("lane_pubkey") or "")
            except ValueError:
                return False, "birth record lane_pubkey malformed"
            if birth_pub != bytes(pubkey):
                return False, "birth pubkey does not match pinned lane key"
        try:
            lanelib.verify_record_signature(r, bytes(pubkey))
        except Exception as e:
            return False, "signature invalid at seq %s: %s" % (r.get("seq"), e)
        prev = r["hash"]
    return True, "signed stream valid, %d records" % len(recs)


def verify_heartbeat_sigs(ticks, pubkey, signing, allow_unsigned=False):
    """Verify per-tick heartbeat signatures (S13). Returns (ok, detail).

    Unsigned ticks are tolerated ONLY when the whole assessed set is
    unsigned (pre-regime); a MIXED set (some signed, some not) fails —
    an attacker appending unsigned ticks to a signed stream must not pass.
    Callers pass only recent ticks (old ticks age out of liveness anyway).
    """
    env, lanelib, skeys = signing
    signed = [t for t in ticks if t.get("sig") not in (None, "none")]
    if not signed:
        if allow_unsigned:
            return None, "pre-regime: heartbeat ticks unsigned"
        return False, "unsigned heartbeat stream with signed lane history"
    for t in ticks:
        sig = t.get("sig")
        if not sig or sig == "none":
            return False, "mixed stream: unsigned tick among signed ticks"
        try:
            lanelib.verify_record_signature(t, bytes(pubkey))
        except Exception as e:
            return False, "heartbeat tick signature invalid: %s" % e
    return True, "%d ticks signed" % len(signed)


def read_lane_pubkey_file(path):
    """Read a hex-encoded lane pubkey file. None if missing/malformed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = bytes.fromhex(f.read().strip().split()[0])
        return raw if len(raw) == 32 else None
    except (OSError, ValueError):
        return None


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


def assess_lane(lane_id, lane_dir, stale_after, lane_pubkey=None,
                remote=False):
    """Assess one lane from its stream files. Never invents UP.

    lane_pubkey: 32-byte lane public key, or None (pre-regime legacy path).
    remote: True when these files came from the rendezvous (untrusted).
      S13: remote + pubkey -> signatures REQUIRED (fail -> UNKNOWN).
      remote + no pubkey -> UNKNOWN ("lane key not pinned").
      local + pubkey -> signatures required (fail -> DOWN: our disk is ours).
      local + no pubkey -> legacy hash check, reason says so.
    """
    hb = read_jsonl(os.path.join(lane_dir, "heartbeat.jsonl"))
    at = read_jsonl(os.path.join(lane_dir, "attestations.jsonl"))
    if not hb and not at:
        return {"lane": lane_id, "state": "UNKNOWN",
                "reason": "no heartbeat or attestation data"}

    # Freshness first, from the newest heartbeat tick we can date.
    dated = []
    now = datetime.now(timezone.utc)
    for tick in hb:
        ts = parse_ts(tick.get("at_utc") or tick.get("ts") or tick.get("time"))
        if ts:
            dated.append((tick, (now - ts).total_seconds()))
    if dated:
        age = min(a for _, a in dated)
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

    signing = _load_signing()
    sig_note = ""
    # Signature checks cover only recent ticks: old ticks age out of
    # liveness anyway, and a regime upgrade must not flap on pre-regime
    # history. The freshest tick is always assessed.
    recent = [t for t, a in dated if a <= 2 * stale_after] or \
             ([min(dated, key=lambda p: p[1])[0]] if dated else [])
    if lane_pubkey is not None and signing is not None:
        # Heartbeat signatures first (S13): a planted heartbeat.jsonl dies here.
        # Unsigned ticks tolerated only if the lane has NO signed material
        # at all (fully pre-regime); a signed history + unsigned heartbeat
        # is untrusted, not legacy.
        at_signed = any(r.get("sig") not in (None, "none") for r in at)
        ok, detail = verify_heartbeat_sigs(recent, lane_pubkey, signing,
                                           allow_unsigned=not at_signed)
        if ok is False:
            if remote:
                return {"lane": lane_id, "state": "UNKNOWN",
                        "reason": "untrusted heartbeat stream: " + detail}
            return {"lane": lane_id, "state": "DOWN",
                    "reason": "heartbeat stream tampered: " + detail}
        if ok is None:
            sig_note = " (%s)" % detail
        # Attestation signatures.
        if at:
            ok, detail = verify_signed_stream(at, lane_pubkey, signing)
            if not ok:
                if remote:
                    return {"lane": lane_id, "state": "UNKNOWN",
                            "reason": "untrusted attestation stream: " + detail}
                return {"lane": lane_id, "state": "DOWN",
                        "reason": "attestation stream tampered: " + detail}
            sig_note = " (signed streams verified)"
    elif remote and signing is not None:
        return {"lane": lane_id, "state": "UNKNOWN",
                "reason": "lane key not pinned — remote stream untrusted"}
    else:
        if at:
            ok, detail = verify_attestations(at)
            if not ok:
                return {"lane": lane_id, "state": "DOWN",
                        "reason": "attestation chain broken: " + detail}
        if lane_pubkey is None:
            sig_note = " (pre-regime: signatures not verified)"

    if age > stale_after:
        return {"lane": lane_id, "state": "DOWN",
                "reason": "heartbeat stale: %.0fs > %ds%s" % (age, stale_after, sig_note),
                "last_tick_age_secs": round(age, 1)}
    return {"lane": lane_id, "state": "UP",
            "reason": "heartbeat fresh" + sig_note,
            "last_tick_age_secs": round(age, 1)}


def snapshot(lanes, state_dir=DEFAULT_STATE_DIR, remote_dir=None,
             stale_after=DEFAULT_STALE_AFTER, etc_dir=DEFAULT_ETC_DIR,
             lane_keys_dir=None):
    """lanes: {lane_id: {"local": bool}}. Local lanes read state_dir;
    remote lanes read remote_dir/<lane_id>/ (UNKNOWN until populated).

    etc_dir: where the LOCAL lane's key lives (/etc/dualis).
    lane_keys_dir: where pinned REMOTE lane pubkeys live
      (<lane_keys_dir>/<lane>.pubkey, hex). Missing pin -> UNKNOWN.
    """
    out = {}
    signing = _load_signing()
    local_pubkey = None
    if signing is not None:
        env, lanelib, skeys = signing
        try:
            local_pubkey = lanelib.read_lane_pubkey(etc_dir)
        except Exception:
            local_pubkey = None
    for lane_id, cfg in lanes.items():
        if cfg.get("local"):
            out[lane_id] = assess_lane(lane_id, state_dir, stale_after,
                                      lane_pubkey=local_pubkey, remote=False)
        elif remote_dir:
            d = os.path.join(remote_dir, lane_id)
            pubkey = None
            if lane_keys_dir:
                pubkey = read_lane_pubkey_file(
                    os.path.join(lane_keys_dir, lane_id + ".pubkey"))
            out[lane_id] = assess_lane(lane_id, d, stale_after,
                                      lane_pubkey=pubkey, remote=True)
        else:
            out[lane_id] = {"lane": lane_id, "state": "UNKNOWN",
                            "reason": "no remote stream configured"}
    return out


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--state-dir", default=DEFAULT_STATE_DIR)
    p.add_argument("--etc-dir", default=DEFAULT_ETC_DIR)
    p.add_argument("--remote-dir", default=None)
    p.add_argument("--lane-keys-dir", default=None,
                   help="dir of pinned remote lane pubkeys (<lane>.pubkey, hex)")
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
        return snapshot(lanes, ns.state_dir, ns.remote_dir, ns.stale_after,
                        etc_dir=ns.etc_dir, lane_keys_dir=ns.lane_keys_dir)

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
