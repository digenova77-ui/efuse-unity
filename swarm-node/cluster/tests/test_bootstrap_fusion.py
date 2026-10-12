#!/usr/bin/env python3
"""Fused bootstrap test: run bootstrap.sh twice against a fixture.

Proves the fusion: one paste installs the node runtime AND the cluster
middleware AND writes the birth trace; the second run is a no-op
(stable identity, exactly one birth record, chain still valid).

The fixture redirects the whole install tree under a temp dir
(DUALIS_PREFIX) and serves the working copy over local HTTP so RAW_BASE
behaves like production. Network-mutating steps are skipped
(DUALIS_FIXTURE=1). Nothing outside the temp dir is touched.

Run: python3 tests/test_bootstrap_fusion.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SWARM_NODE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                           "..", ".."))
BOOTSTRAP = os.path.join(SWARM_NODE, "bootstrap.sh")
FUSED_VERSION = "v1.1.0"


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run_bootstrap(env, lane):
    return subprocess.run(["bash", BOOTSTRAP, lane], env=env,
                          capture_output=True, text=True, timeout=300)


def fixture_env(prefix, port):
    env = dict(os.environ)
    env["DUALIS_PREFIX"] = prefix
    env["DUALIS_FIXTURE"] = "1"
    env["RAW_BASE"] = "http://127.0.0.1:%d" % port
    env["DUALIS_STATE_DIR"] = os.path.join(prefix, "var/lib/dualis")
    env["DUALIS_ETC_DIR"] = os.path.join(prefix, "etc/dualis")
    return env


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    tmp = tempfile.mkdtemp(prefix="dualis-fusion-")
    prefix = os.path.join(tmp, "root")
    srv = ThreadingHTTPServer(("127.0.0.1", 0),
                              partial(Quiet, directory=SWARM_NODE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    env = fixture_env(prefix, port)

    try:
        # --- DCLM lane, run twice: the idempotency proof ---
        r1 = run_bootstrap(env, "DCLM")
        assert r1.returncode == 0, \
            "first DCLM run failed:\n" + r1.stderr[-3000:]
        r2 = run_bootstrap(env, "DCLM")
        assert r2.returncode == 0, \
            "second DCLM run failed:\n" + r2.stderr[-3000:]
        assert "already born" in r2.stdout, \
            "second run did not report the birth skip:\n" + r2.stdout[-1500:]

        # identity stable across runs
        nid = read(os.path.join(prefix, "etc/dualis/node-id"))
        assert nid.startswith("node-"), nid
        assert read(os.path.join(prefix, "etc/dualis/lane")) == "DCLM"
        assert read(os.path.join(prefix, "etc/dualis/version")) == FUSED_VERSION

        # exactly one birth trace, and it is a cluster-registration claim
        chain = [json.loads(l) for l in
                 read(os.path.join(prefix,
                                   "var/lib/dualis/attestations.jsonl")).split("\n")
                 if l.strip()]
        births = [r for r in chain if r.get("shift_id") == "birth"]
        assert len(births) == 1, \
            "expected exactly one birth record, got %d" % len(births)
        b = births[0]
        assert b["lane"] == "DCLM", b["lane"]
        assert b["node_id"] == nid, (b["node_id"], nid)
        assert b["claims_touched"] == ["cluster-registration"], \
            b["claims_touched"]
        note = json.loads(b["note"])
        assert note["event"] == "birth", note
        assert note["region"] == "americas", note
        assert note["version"] == FUSED_VERSION, note
        assert note["cluster_node"] == "qnode-cluster-ingress", note

        # chain still valid after two runs
        v = subprocess.run(
            [sys.executable,
             os.path.join(prefix, "opt/dualis/node/attest.py"), "--verify"],
            env=env, capture_output=True, text=True)
        assert v.returncode == 0, v.stdout + v.stderr
        assert json.loads(v.stdout)["valid"] is True

        # cluster middleware installed from the single paste
        assert os.path.isfile(os.path.join(
            prefix, "opt/dualis/pull-agent/pull-agent.py"))
        assert os.path.isfile(os.path.join(
            prefix, "etc/systemd/system/dualis-pull-agent.service"))

        # heartbeats ticked (at least one per run)
        hb = [l for l in read(os.path.join(
            prefix, "var/lib/dualis/heartbeat.jsonl")).split("\n") if l.strip()]
        assert len(hb) >= 2, "expected >=2 heartbeat ticks, got %d" % len(hb)

        # --- EUROPE lane, run once: region mapping + object-store staging ---
        prefix2 = os.path.join(tmp, "root-eu")
        env2 = fixture_env(prefix2, port)
        r3 = run_bootstrap(env2, "EUROPE")
        assert r3.returncode == 0, \
            "EUROPE run failed:\n" + r3.stderr[-3000:]
        chain2 = [json.loads(l) for l in
                  read(os.path.join(prefix2,
                                    "var/lib/dualis/attestations.jsonl")).split("\n")
                  if l.strip()]
        births2 = [r for r in chain2 if r.get("shift_id") == "birth"]
        assert len(births2) == 1
        note2 = json.loads(births2[0]["note"])
        assert note2["region"] == "europe", note2
        assert note2["lane"] == "EUROPE", note2
        for f in ("object-init", "object-status", "s3.py", "garage.service"):
            assert os.path.isfile(os.path.join(
                prefix2, "opt/dualis/node", f)), "missing EUROPE file: " + f
        assert os.path.isfile(os.path.join(
            prefix2, "opt/dualis/pull-agent/pull-agent.py"))

        print("FUSION OK: DCLM x2 (one birth, stable identity, chain valid) + "
              "EUROPE x1 (region europe, object-store staged) — "
              "pull-agent installed from the single paste in all runs.")
        return 0
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
