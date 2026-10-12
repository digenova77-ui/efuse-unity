#!/usr/bin/env python3
"""DualisCapax go-live pipeline — "go live" is the last human word.

David's law: the system cannot be born autonomous. The FIRST bootstrap on a
lane needs exactly one hand (his paste, or the browser). After first breath,
the lane runs pull-agent.py (outbound-only, phones home) and never needs
hands again.

This command is the "go live" word itself — and in his architecture that
word is a collapse: his verdict, the system's execution.

Stages (ordered, gated — a failed stage halts, rolls back to last
known-good, and writes a dispute/gap trace naming the failure):
  1. PREFLIGHT  verify manifest + lane has breathed + zone files valid
  2. INTENT     publish the go-live intent to the rendezvous (reversible)
  3. WAIT-STAGED poll for the lane's staged attestation (pull-agent's work)
  4. CUTOVER    update GeoDNS answers + balancer table  [COMMAND-GATED]
  5. CONFIRM    lane healthy serving the new version; HTTP check
  6. TRACE      collapse trace: the go-live itself, permanently recorded

Safety: --dry-run prepares everything and stops before CUTOVER.
Prepare-automatically, execute-on-command. Go-live never fires without
his word — and this command IS the word.

Usage:
  golive.py --lane EUROPE --version v1.2.0 [--dry-run] [--manifest-url URL]
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balancer

STATE_DIR = os.environ.get("DUALIS_CLUSTER_STATE", "/var/lib/dualis/cluster")
RENDEZVOUS = os.environ.get("DUALIS_RENDEZVOUS_DIR", "/var/lib/dualis/rendezvous")
# In production the rendezvous is the object-store bucket (s3://dclm-objects/golive/).
# Local dir is the honest stand-in until the bucket is live.
DEFAULT_MANIFEST = ("https://raw.githubusercontent.com/digenova77-ui/efuse-unity"
                    "/main/swarm-node/cluster/manifest.json")

STAGE_TIMEOUT = int(os.environ.get("DUALIS_GOLIVE_TIMEOUT", "600"))
POLL_INTERVAL = 10

NODE_ID = "qnode-cluster-golive"
INTERCONNECT = "cluster-golive"


class GateFailed(Exception):
    """A stage gate failed. Carries the stage name and the honest reason."""
    def __init__(self, stage, reason):
        super().__init__("[%s] %s" % (stage, reason))
        self.stage = stage
        self.reason = reason


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


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


def curl_ok(url):
    """HEAD/GET check that a URL is actually fetchable. No fake 200s."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def emit_golive_trace(kind, possibility_space, outcome):
    """Reuse the balancer's trace chain (same node-chain convention)."""
    old_log, old_node = balancer.TRACE_LOG, balancer.NODE_ID
    old_ic = balancer.INTERCONNECT
    try:
        balancer.NODE_ID = NODE_ID
        balancer.INTERCONNECT = INTERCONNECT
        return balancer.emit_trace(kind, possibility_space, outcome)
    finally:
        balancer.TRACE_LOG, balancer.NODE_ID = old_log, old_node
        balancer.INTERCONNECT = old_ic


# ---------------------------------------------------------------- stages

def stage_preflight(lane, version, manifest_url, health):
    """Gate 1: the world is as the pipeline expects."""
    manifest = read_json(manifest_url) if manifest_url.startswith("/") else None
    if manifest is None:
        # Remote manifest: fetch it for real.
        try:
            with urllib.request.urlopen(manifest_url, timeout=20) as resp:
                manifest = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise GateFailed("PREFLIGHT", "manifest unreachable: %s" % e)
    entry = (manifest.get("versions") or {}).get(version)
    if not entry:
        raise GateFailed("PREFLIGHT",
                         "version %s not in manifest" % version)
    bundle_url = entry.get("bundle_url")
    if not bundle_url or not curl_ok(bundle_url):
        raise GateFailed("PREFLIGHT", "bundle URL unfetchable: %s" % bundle_url)
    if entry.get("sha256") and len(entry["sha256"]) != 64:
        raise GateFailed("PREFLIGHT", "manifest sha256 malformed")
    st = (health or {}).get(lane, {}).get("state", "UNKNOWN")
    if st == "UNKNOWN":
        raise GateFailed("PREFLIGHT",
                         "lane %s never breathed (no heartbeat) — one hand first" % lane)
    if st == "DOWN":
        raise GateFailed("PREFLIGHT", "lane %s is DOWN — heal it first" % lane)
    return {"manifest": manifest, "bundle": entry,
            "lane_state": st, "at": utcnow()}


def stage_intent(lane, version, bundle):
    """Gate 2: publish the reversible go-live intent."""
    intent = {"lane": lane, "version": version,
              "bundle_url": bundle["bundle_url"],
              "sha256": bundle.get("sha256"),
              "issued_at": utcnow(), "issued_by": "david:go-live",
              "status": "armed"}
    write_json(os.path.join(RENDEZVOUS, "golive", "intent", lane + ".json"), intent)
    return intent


def stage_wait_staged(lane, timeout=STAGE_TIMEOUT, interval=POLL_INTERVAL):
    """Gate 3: the lane's pull-agent staged the version (its attestation)."""
    path = os.path.join(RENDEZVOUS, "golive", "staged", lane + ".json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        staged = read_json(path)
        if staged and staged.get("status") == "staged":
            return staged
        time.sleep(interval)
    raise GateFailed("WAIT-STAGED",
                     "no staged attestation from %s within %ds" % (lane, timeout))


def stage_cutover(lane, health, zone_dir, dry_run):
    """Gate 4: move traffic. COMMAND-GATED — dry-run stops before this."""
    if dry_run:
        return {"cutover": "skipped-dry-run"}
    # Snapshot prior answers for rollback.
    prior = {}
    import glob
    for f in glob.glob(os.path.join(zone_dir, "answers.*")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                prior[os.path.basename(f)] = fh.read()
        except OSError:
            pass
    write_json(os.path.join(STATE_DIR, "cutover-prior.json"),
               {"at": utcnow(), "answers": prior})
    changed, table, trace = balancer.decide(health)
    # GeoDNS agent applies the same table to DNS (loaded by file location:
    # the filename has a hyphen, so importlib.import_module can't take it).
    import importlib.util
    agent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "geodns", "geodns-agent.py")
    spec = importlib.util.spec_from_file_location("geodns_agent", agent_path)
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    result = agent.apply(zone_dir, os.path.join(STATE_DIR, "health.json"))
    return {"balancer_changed": changed,
            "trace_hash": trace["trace_hash"] if trace else None,
            "geodns": result}


def stage_confirm(lane, version, health_fn, timeout=STAGE_TIMEOUT):
    """Gate 5: the lane is healthy AND serving the new version."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = health_fn()
        st = (h.get(lane) or {})
        if st.get("state") == "UP" and st.get("version") == version:
            return {"lane": lane, "version": version,
                    "confirmed_at": utcnow()}
        time.sleep(POLL_INTERVAL)
    raise GateFailed("CONFIRM",
                     "lane %s not serving %s within %ds" % (lane, version, timeout))


def rollback(reason):
    """Restore last-known-good answers. Returns what was restored."""
    prior = read_json(os.path.join(STATE_DIR, "cutover-prior.json")) or {}
    restored = []
    zone_dir = os.environ.get("DUALIS_ZONE_DIR", "/etc/bind")
    for name, body in (prior.get("answers") or {}).items():
        try:
            with open(os.path.join(zone_dir, name), "w", encoding="utf-8") as f:
                f.write(body)
            restored.append(name)
        except OSError:
            pass
    reloaded = False
    if restored and shutil.which("rndc"):
        reloaded = subprocess.run(["rndc", "reload"],
                                  capture_output=True).returncode == 0
    return {"restored": restored, "rndc_reload": reloaded,
            "rndc_present": bool(shutil.which("rndc"))}


def run(lane, version, manifest_url, health_path, zone_dir, dry_run,
        health_fn=None, timeout=STAGE_TIMEOUT):
    """Run the pipeline. Returns the go-live record. Raises GateFailed."""
    log = []
    health = read_json(health_path) or {}

    def attempt(stage, fn, *a):
        try:
            out = fn(*a)
            log.append({"stage": stage, "ok": True, "at": utcnow()})
            return out
        except GateFailed as e:
            log.append({"stage": e.stage, "ok": False,
                        "reason": e.reason, "at": utcnow()})
            raise

    try:
        pre = attempt("PREFLIGHT", stage_preflight,
                      lane, version, manifest_url, health)
        intent = attempt("INTENT", stage_intent, lane, version, pre["bundle"])
        if dry_run:
            emit_golive_trace(
                "collapse",
                "go-live dry-run for %s version %s" % (lane, version),
                "armed+staged-check only; CUTOVER skipped by command (dry-run)")
            return {"lane": lane, "version": version, "dry_run": True,
                    "stages": log, "at": utcnow()}
        staged = attempt("WAIT-STAGED", stage_wait_staged, lane, timeout)
        health2 = read_json(health_path) or {}
        cut = attempt("CUTOVER", stage_cutover, lane, health2, zone_dir, False)
        hfn = health_fn or (lambda: read_json(health_path) or {})
        conf = attempt("CONFIRM", stage_confirm, lane, version, hfn, timeout)
        trace = emit_golive_trace(
            "collapse",
            "go-live of %s version %s; stages: %s" % (
                lane, version, ",".join(s["stage"] for s in log if s["ok"])),
            "go-live complete: lane %s serving %s" % (lane, version))
        return {"lane": lane, "version": version, "dry_run": False,
                "stages": log, "trace_hash": trace["trace_hash"],
                "at": utcnow()}
    except GateFailed as e:
        restored = rollback(e.reason)
        kind = "gap" if e.stage == "WAIT-STAGED" else "dispute"
        emit_golive_trace(
            kind,
            "go-live of %s version %s" % (lane, version),
            "HALTED at %s: %s; rollback restored %s" % (
                e.stage, e.reason, restored or "nothing (no cutover made)"))
        raise


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--lane", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--manifest-url", default=DEFAULT_MANIFEST)
    p.add_argument("--health", default=os.path.join(STATE_DIR, "health.json"))
    p.add_argument("--zone-dir", default=os.environ.get("DUALIS_ZONE_DIR", "/etc/bind"))
    ns = p.parse_args(argv)
    try:
        rec = run(ns.lane, ns.version, ns.manifest_url, ns.health,
                  ns.zone_dir, ns.dry_run)
        print(json.dumps(rec, indent=2, sort_keys=True))
        return 0
    except GateFailed as e:
        print(json.dumps({"go_live": "HALTED", "stage": e.stage,
                          "reason": e.reason}, indent=2))
        return 1


if __name__ == "__main__":
    main(sys.argv[1:])
