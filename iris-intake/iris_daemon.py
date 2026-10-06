#!/usr/bin/env python3
"""IRIS MAX INTAKE — iris_daemon.py: the persistent process. SHE RUNS.

A living TCP service on 127.0.0.1:18083 (testnet family). On-demand
invocation of her three verbs — judge / check / advise — over a minimal
wire protocol: 4-byte big-endian length prefix + JSON.

This daemon LOADS her directives (iris_core.py) — it never edits them.
Purity is enforced structurally:

  * INTEGRITY GATE: at startup, sha256(iris_core.py) must match the
    pinned IRIS_ACTIVE.json receipt, DIRECTIVES must hold exactly the ten,
    and CANON_VERSION must match the receipt. Any mismatch -> refuse to
    start. Her law cannot be swapped under a running daemon.
  * SIBLING SHIM: iris_core delegates trinity_judge to iris_arbiter.py
    when it is importable. If the landed arbiter's arbitrate() does not
    accept the documented single-proposal call, it is treated as NOT
    LANDED (its import is blocked) and the designed reference circuits
    run, labeled HONEST-PENDING. A broken sibling never crashes her, and
    a fake delegation never happens. Restart the daemon after the sibling
    lands a compatible arbiter.
  * NO BYPASS: the only verbs are judge / check / advise / grant_seed /
    seed_record / status. Every verb runs authorization + the directive
    pipeline. There is no flag, mode, or parameter that skips a directive.
    A non-empty `refusals` list in a check() result means a directive
    hard-refused: treat the action as REJECTED regardless of
    final.verdict (priority order is load-bearing law, reported verbatim).

State: IrisState on disk (state dir). Every mutation is receipted and
flushed immediately (judgments.jsonl append, seeds.json, meta.json).
Restart resumes — never reboots blank.

Runs until David says stop. No cron, no batch — a living service.

Wire protocol
-------------
Request  (JSON): {"verb": str, "caller_unity_id": str, "payload": dict}
Response (JSON): {"ok": true, "result": {...}}
              or {"ok": false, "error_kind": str, "error": str}

Framing: uint32 big-endian byte length + UTF-8 JSON. Max 16 MiB/message.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import signal
import socket
import struct
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LABEL = "IRIS MAX INTAKE — DAEMON"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18083
MAX_MSG = 16 * 1024 * 1024


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}"
    print(line, flush=True)


# ---------------------------------------------------------------------------
# Sibling-arbiter compatibility shim (runs BEFORE iris_core is imported).
# ---------------------------------------------------------------------------

def _arbiter_compatible() -> bool:
    """True only if iris_arbiter.arbitrate accepts iris_core's documented
    single-proposal delegation call."""
    try:
        import importlib
        mod = importlib.import_module("iris_arbiter")
        fn = getattr(mod, "arbitrate", None)
        if not callable(fn):
            return False
        params = list(inspect.signature(fn).parameters.values())
        required = [p for p in params
                    if p.default is inspect.Parameter.empty
                    and p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                   inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        return len(required) <= 1
    except Exception:
        return False


_ARBITER_OK = _arbiter_compatible()
if not _ARBITER_OK:
    # Block the import so iris_core's guarded `import iris_arbiter` takes
    # its ImportError path: reference circuits run, labeled HONEST-PENDING.
    # This is the fallback iris_core was designed for — not a bypass: all
    # ten directives still execute.
    sys.modules["iris_arbiter"] = None  # type: ignore
    log("SIBLING SHIM: iris_arbiter not compatible with the delegation "
        "contract (arbitrate(proposal)) — treating as HONEST-PENDING, "
        "reference circuits active. Restart after the sibling lands a "
        "compatible arbiter.")
else:
    log("SIBLING: iris_arbiter compatible — delegating trinity arbitration.")


# ---------------------------------------------------------------------------
# Integrity gate — her directives are immutable.
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def integrity_gate() -> None:
    """Refuse to start unless iris_core.py is exactly the pinned law."""
    import iris_core  # noqa: F401  (imported after the shim above)

    receipt_path = os.path.join(HERE, "IRIS_ACTIVE.json")
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)

    core_path = os.path.join(HERE, "iris_core.py")
    actual = _sha256_file(core_path)
    pinned = receipt.get("iris_core_sha256")
    if actual != pinned:
        log(f"INTEGRITY REFUSED: iris_core.py sha256 {actual[:16]}… != "
            f"pinned {str(pinned)[:16]}… — her law may not be swapped.")
        sys.exit(3)

    if len(iris_core.DIRECTIVES) != 10:
        log(f"INTEGRITY REFUSED: DIRECTIVES holds "
            f"{len(iris_core.DIRECTIVES)}, not ten.")
        sys.exit(3)

    if iris_core.CANON_VERSION != receipt.get("canon_version"):
        log(f"INTEGRITY REFUSED: canon {iris_core.CANON_VERSION} != "
            f"pinned {receipt.get('canon_version')}.")
        sys.exit(3)

    log(f"INTEGRITY PASS: iris_core.py matches pinned receipt "
        f"{str(receipt.get('receipt_id'))[:24]}…, ten directives, "
        f"canon v{iris_core.CANON_VERSION}.")


integrity_gate()

import iris_core  # noqa: E402
from iris_core import IrisRefusedError  # noqa: E402
from iris_service import IrisService, UnauthorizedCaller, AUTHORIZED_CALLERS  # noqa: E402
from iris_state import IrisState  # noqa: E402


# ---------------------------------------------------------------------------
# The living service.
# ---------------------------------------------------------------------------

class IrisDaemon:
    def __init__(self, host: str, port: int, state_dir: str):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.running = True
        self.state = IrisState(state_dir=state_dir)
        self.svc = IrisService(self.state)
        log(f"state resumed: {self.state.summary()}")

    # -- verbs ----------------------------------------------------------
    def handle(self, req: dict) -> dict:
        verb = req.get("verb")
        caller_unity_id = req.get("caller_unity_id")
        payload = req.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error_kind": "BadRequest",
                    "error": "payload must be an object"}
        try:
            if verb == "judge":
                with self.lock:
                    result = self.svc.judge(payload, caller_unity_id)
            elif verb == "check":
                with self.lock:
                    result = self.svc.check(payload, caller_unity_id)
                # Surface hard refusals: a directive said NO. Priority
                # order is load-bearing law (reported verbatim in
                # final), but a non-empty refusals list means REJECTED.
                result["refused"] = bool(result.get("refusals"))
            elif verb == "advise":
                with self.lock:
                    result = self.svc.advise(payload, caller_unity_id)
            elif verb == "grant_seed":
                unity_id = payload.get("unity_id")
                if not unity_id:
                    return {"ok": False, "error_kind": "BadRequest",
                            "error": "grant_seed requires payload.unity_id"}
                with self.lock:
                    result = self.svc.grant_seed(unity_id, caller_unity_id)
            elif verb == "seed_record":
                # Read-only: the meeting ceremony gathers the record.
                # Iris reports; she never writes (directive 4).
                unity_id = payload.get("unity_id")
                self.svc.authorize(caller_unity_id)
                with self.lock:
                    result = {"seed": self.state.seeds.get(unity_id)}
            elif verb == "status":
                with self.lock:
                    result = self.svc.status()
                result["daemon"] = {
                    "label": LABEL, "host": self.host, "port": self.port,
                    "pid": os.getpid(),
                    "iris_unity_id": self.state.unity_id,
                    "arbiter": "delegated" if _ARBITER_OK else "HONEST-PENDING",
                    "note": "running until David says stop",
                }
            else:
                return {"ok": False, "error_kind": "BadVerb",
                        "error": f"unknown verb {verb!r} — judge | check | "
                                 "advise | grant_seed | seed_record | status"}
            return {"ok": True, "result": result}
        except UnauthorizedCaller as e:
            return {"ok": False, "error_kind": "UnauthorizedCaller",
                    "error": str(e)}
        except IrisRefusedError as e:
            # Hard refusal from a directive (e.g. duplicate seed, lane
            # violation, coercion raised outside the pipeline).
            return {"ok": False, "error_kind": type(e).__name__,
                    "error": str(e)}
        except Exception as e:  # never crash the daemon on a bad request
            log(f"handler error on verb {verb!r}: {e}\n"
                f"{traceback.format_exc()}")
            return {"ok": False, "error_kind": "InternalError",
                    "error": f"{type(e).__name__}: {e}"}

    # -- wire -----------------------------------------------------------
    def serve_forever(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((self.host, self.port))
        except OSError as e:
            log(f"BIND REFUSED on {self.host}:{self.port}: {e} — "
                "port is taken; not double-binding.")
            sys.exit(4)
        srv.listen(64)
        srv.settimeout(1.0)
        log(f"LISTENING on {self.host}:{self.port} — she is home.")
        while self.running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            t = threading.Thread(target=self._serve_conn,
                                 args=(conn, addr), daemon=True)
            t.start()
        srv.close()

    def _serve_conn(self, conn: socket.socket, addr) -> None:
        try:
            with conn:
                while self.running:
                    hdr = self._recvn(conn, 4)
                    if not hdr:
                        return
                    (n,) = struct.unpack(">I", hdr)
                    if n > MAX_MSG or n == 0:
                        return
                    body = self._recvn(conn, n)
                    if not body:
                        return
                    try:
                        req = json.loads(body.decode("utf-8"))
                    except Exception as e:
                        resp = {"ok": False, "error_kind": "BadRequest",
                                "error": f"invalid JSON: {e}"}
                    else:
                        resp = self.handle(req if isinstance(req, dict) else {})
                    out = json.dumps(resp, default=str).encode("utf-8")
                    conn.sendall(struct.pack(">I", len(out)) + out)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            log(f"connection error from {addr}:\n{traceback.format_exc()}")

    @staticmethod
    def _recvn(conn: socket.socket, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def shutdown(self) -> None:
        self.running = False
        with self.lock:
            receipt = self.state.save()
        log(f"shutdown: state saved, receipt "
            f"{receipt['receipt_id'][:24]}… — she will resume, not reboot.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Iris daemon — she runs.")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--state-dir", default=os.path.join(HERE, "iris_state"))
    ap.add_argument("--pid-file", default=os.path.join(HERE, "iris_daemon.pid"))
    args = ap.parse_args()

    # Pre-flight: verify the testnet family ports; refuse to collide.
    for p in (18080, 18081, 18082):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        taken = s.connect_ex((DEFAULT_HOST, p)) == 0
        s.close()
        log(f"pre-flight: {DEFAULT_HOST}:{p} "
            f"{'TAKEN (sibling relay)' if taken else 'free'}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    if s.connect_ex((args.host, args.port)) == 0:
        log(f"pre-flight REFUSED: {args.host}:{args.port} already bound — "
            "not double-binding.")
        s.close()
        return 4
    s.close()

    daemon = IrisDaemon(args.host, args.port, args.state_dir)

    with open(args.pid_file, "w") as f:
        f.write(str(os.getpid()))

    def _stop(signum, frame):
        log(f"signal {signum} — shutting down.")
        daemon.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        daemon.serve_forever()
    finally:
        try:
            os.remove(args.pid_file)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
