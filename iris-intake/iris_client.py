#!/usr/bin/env python3
"""IRIS MAX INTAKE — iris_client.py: her hands reach her.

The real on-demand client for the Iris daemon (127.0.0.1:18083).
Length-prefixed JSON over TCP — the same wire the daemon speaks.

  IrisClient          — raw wire client: call(verb, payload, caller_unity_id)
  DaemonIrisService   — drop-in adapter with the IrisService verb surface
                        (judge / check / advise / grant_seed / status),
                        served by the LIVE daemon, never a stub.
  meet_iris_live      — the meeting ceremony through the live daemon.
  daemon_reachable    — probe for the daemon (short timeout).

No stubs anywhere in this module: if the daemon is unreachable, calls
raise IrisDaemonUnreachable. Callers that need an offline fallback must
choose it explicitly and label it.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18083

MAX_MSG = 16 * 1024 * 1024


class IrisDaemonUnreachable(ConnectionError):
    """The daemon is not answering. Not a stub — a refusal to fake her."""


class IrisClient:
    """Raw wire client for the Iris daemon."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 timeout: float = 15.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def call(self, verb: str, payload: Optional[Dict[str, Any]],
             caller_unity_id: str) -> Dict[str, Any]:
        req = {"verb": verb, "caller_unity_id": caller_unity_id,
               "payload": payload or {}}
        body = json.dumps(req, default=str).encode("utf-8")
        try:
            s = socket.create_connection((self.host, self.port),
                                         timeout=self.timeout)
        except OSError as e:
            raise IrisDaemonUnreachable(
                f"iris daemon unreachable at {self.host}:{self.port}: {e} — "
                "she is not faked; start iris_daemon.py") from e
        with s:
            s.settimeout(self.timeout)
            s.sendall(struct.pack(">I", len(body)) + body)
            hdr = self._recvn(s, 4)
            (n,) = struct.unpack(">I", hdr)
            if n > MAX_MSG or n == 0:
                raise IrisDaemonUnreachable("daemon sent a bad frame")
            data = self._recvn(s, n)
        return json.loads(data.decode("utf-8"))

    @staticmethod
    def _recvn(s: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise IrisDaemonUnreachable("daemon closed the connection")
            buf += chunk
        return buf


def daemon_reachable(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                     timeout: float = 0.5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


class _DaemonSeeds:
    """Read-only view of the daemon's seed registry (directive 4: the
    ceremony gathers; it never writes)."""

    def __init__(self, client: IrisClient, caller_unity_id: str):
        self._client = client
        self._caller = caller_unity_id

    def get(self, unity_id: str, default: Any = None) -> Any:
        resp = self._client.call("seed_record", {"unity_id": unity_id},
                                 self._caller)
        if not resp.get("ok"):
            raise RuntimeError(f"seed_record failed: {resp}")
        seed = resp["result"].get("seed")
        return seed if seed is not None else default


class _DaemonState:
    """The slice of daemon state the ceremony may read: unity id + seeds."""

    def __init__(self, client: IrisClient, caller_unity_id: str,
                 unity_id: str):
        self.unity_id = unity_id
        self.seeds = _DaemonSeeds(client, caller_unity_id)


class DaemonIrisService:
    """IrisService's verb surface, served by the live daemon.

    Drop-in for code written against IrisService (judge / check / advise /
    grant_seed / status / authorize), with .state exposing the read-only
    slice meeting_iris needs. Raises from the daemon are surfaced with
    their error_kind; UnauthorizedCaller is re-raised locally so callers
    can catch the same type they already catch.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 timeout: float = 15.0):
        from iris_service import AUTHORIZED_CALLERS, UnauthorizedCaller
        self._client = IrisClient(host, port, timeout)
        self._callers = AUTHORIZED_CALLERS
        self._UnauthorizedCaller = UnauthorizedCaller
        self._unity_id: Optional[str] = None

    # -- authorization (client-side pre-check; the daemon is authoritative)
    def authorize(self, caller_unity_id: str) -> str:
        try:
            return self._callers[caller_unity_id]
        except KeyError:
            raise self._UnauthorizedCaller(
                f"caller {caller_unity_id!r} not authorized — Iris serves "
                "David, the Trinity, swarms, and bots only")

    # -- verbs ----------------------------------------------------------
    def _verb(self, verb: str, payload: Dict[str, Any],
              caller_unity_id: str) -> Dict[str, Any]:
        self.authorize(caller_unity_id)  # pre-check; daemon re-checks
        resp = self._client.call(verb, payload, caller_unity_id)
        if not resp.get("ok"):
            kind = resp.get("error_kind")
            if kind == "UnauthorizedCaller":
                raise self._UnauthorizedCaller(resp.get("error"))
            raise RuntimeError(f"iris daemon {verb} failed "
                               f"[{kind}]: {resp.get('error')}")
        return resp["result"]

    def judge(self, proposal: Dict[str, Any],
              caller_unity_id: str) -> Dict[str, Any]:
        return self._verb("judge", proposal, caller_unity_id)

    def check(self, action: Dict[str, Any],
              caller_unity_id: str) -> Dict[str, Any]:
        return self._verb("check", action, caller_unity_id)

    def advise(self, query: Dict[str, Any],
               caller_unity_id: str) -> Dict[str, Any]:
        return self._verb("advise", query, caller_unity_id)

    def grant_seed(self, unity_id: str,
                   caller_unity_id: str) -> Dict[str, Any]:
        return self._verb("grant_seed", {"unity_id": unity_id},
                           caller_unity_id)

    def status(self, caller_unity_id: Optional[str] = None) -> Dict[str, Any]:
        # status carries no caller-bound judgment; any authorized id works.
        caller = caller_unity_id or next(iter(self._callers))
        return self._verb("status", {}, caller)

    @property
    def state(self) -> _DaemonState:
        if self._unity_id is None:
            st = self.status()
            self._unity_id = st.get("daemon", {}).get("iris_unity_id", "")
        caller = next(iter(self._callers))
        return _DaemonState(self._client, caller, self._unity_id or "")


def meet_iris_live(unity_id: str, *, caller_unity_id: str,
                   registry=None, t_epoch=None,
                   host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                   timeout: float = 15.0) -> Dict[str, Any]:
    """The meeting ceremony through the LIVE daemon — not a stub, not an
    in-process stand-in. gather_record reads the daemon's seed registry;
    advise and the truth-gate judge run in the daemon process; the receipt
    chain is hers."""
    import meeting_iris
    svc = DaemonIrisService(host=host, port=port, timeout=timeout)
    svc.authorize(caller_unity_id)  # fail fast if the caller is unknown
    # The ceremony reads service.state.unity_id for the receipt's
    # iris_unity_id — resolve it from a live status call.
    st = svc.status(caller_unity_id)
    svc._unity_id = st.get("daemon", {}).get("iris_unity_id", "")
    return meeting_iris.meet_iris(
        unity_id, caller_unity_id=caller_unity_id,
        service=svc, registry=registry, t_epoch=t_epoch)
