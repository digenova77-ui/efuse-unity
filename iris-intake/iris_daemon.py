"""IRIS MAX INTAKE — legacy testnet daemon.

The daemon serves a read-only IrisService. Its 2P5L output is diagnostic
evidence only; the canonical DCLM Narrow adapter and lawful x/y mapping
are not wired, so the service returns STALEMATE and never FLAWLESS.

Iris does not write state and cannot issue seeds. DCLM owns rights and
writes; seed issuance belongs to dclm.seed.Seeder through the binding
gate, rights check, and dclm_commit path. The old iris_core / arbiter
three-seat implementation remains historical and is not called by this
service path.

Startup verifies every required runtime module against the local
IRIS_SELF_CHECK.json manifest. This is self-consistency only, not an
independent witness, ratification, or Trinity authorization. Testnet only.
"""

from __future__ import annotations

import argparse
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
# Integrity gate — her directives are immutable.
# ---------------------------------------------------------------------------

def integrity_gate() -> None:
    """Refuse startup unless the complete runtime matches its local manifest.

    A matching local manifest is a self-consistency result only. It does
    not establish independent authority or grant Trinity authorization.
    """
    import re
    import iris_core  # legacy core version only; no three-seat call is made
    from iris_integrity import verify_runtime_manifest

    receipt_path = os.path.join(HERE, "IRIS_SELF_CHECK.json")
    try:
        with open(receipt_path, encoding="utf-8") as handle:
            receipt = json.load(handle)
    except Exception as exc:
        log(f"INTEGRITY REFUSED: activation receipt unavailable or invalid: {exc}")
        sys.exit(3)

    if iris_core.CANON_VERSION != receipt.get("canon_version"):
        log(f"INTEGRITY REFUSED: legacy core version {iris_core.CANON_VERSION} != "
            f"pinned {receipt.get('canon_version')}.")
        sys.exit(3)

    canon_path = os.path.join(HERE, "..", "CANON.md")
    try:
        with open(canon_path, encoding="utf-8") as handle:
            canon_source = handle.read()
        match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", canon_source)
        current_canon = match.group(1) if match else "UNKNOWN"
    except OSError:
        current_canon = "UNKNOWN"
    if current_canon == "UNKNOWN" or current_canon != receipt.get("source_canon_version"):
        log("INTEGRITY REFUSED: current root canon version is missing or differs from receipt.")
        sys.exit(3)

    if receipt.get("receipt_kind") != "IRIS_SELF_CHECK":
        log("INTEGRITY REFUSED: receipt is not an IRIS_SELF_CHECK.")
        sys.exit(3)

    if receipt.get("integrity_level") != "SELF_CONSISTENCY_ONLY":
        log("INTEGRITY REFUSED: receipt does not declare SELF_CONSISTENCY_ONLY.")
        sys.exit(3)

    if receipt.get("external_trust_anchor") != "NOT_CONFIGURED":
        log("INTEGRITY REFUSED: external trust-anchor state is missing or ambiguous.")
        sys.exit(3)

    if receipt.get("trinity_compatibility") != "LEGACY_TESTNET_HARNESS_ONLY":
        log("INTEGRITY REFUSED: legacy testnet compatibility state is missing.")
        sys.exit(3)

    if receipt.get("trinity_authorization") != "NOT_GRANTED":
        log("INTEGRITY REFUSED: local activation receipt cannot grant Trinity authority.")
        sys.exit(3)

    result = verify_runtime_manifest(
        receipt.get("runtime_manifest"),
        receipt.get("runtime_manifest_sha256"),
        os.path.dirname(HERE),
    )
    if not result.get("ok"):
        log(f"INTEGRITY REFUSED: whole-runtime verification failed: "
            f"{result.get('reason')}; {result.get('mismatches', [])}")
        sys.exit(3)

    log(
        f"SELF-CONSISTENCY PASS: {result['module_count']} runtime modules "
        f"match manifest {result['manifest_sha256'][:24]}…; "
        f"root canon v{current_canon}; legacy core v{iris_core.CANON_VERSION}."
    )
    log(
        "AUTHORITY HELD: external trust anchor NOT_CONFIGURED; "
        "Trinity authorization NOT_GRANTED; testnet only."
    )


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
                # The current service remains STALEMATE until canonical
                # Narrow is wired. Never promote diagnostic evidence to PASS.
                result["refused"] = result.get("verdict") != "FLAWLESS"
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
                    "decision_path": "2P5L two-primary diagnostic only",
                    "narrowing": "NOT_WIRED",
                    "authority": "NOT_GRANTED",
                    "note": "testnet only; Iris does not write state",
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
