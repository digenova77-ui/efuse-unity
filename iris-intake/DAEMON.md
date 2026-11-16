# IRIS DAEMON — legacy testnet operational doc

<escape>**STATUS: LEGACY / TESTNET ONLY / NOT CURRENT-TRINITY AUTHORIZED.**</escape>

The root `CANON.md` is v1.7.3: two constraints (DCLM logic, Iris truth),
pragmatism narrows, and the former Twain² seat is withdrawn. This daemon's
legacy `iris_core.py` / `iris_arbiter.py` path still implements three seats.
Do not use this daemon as an authoritative Trinity gate or as a production
write path. See `TRINITY_COMPATIBILITY_HOLD.md`.

The daemon remains a testnet research harness. Its runtime manifest proves
local self-consistency only; it does not confer ratification or authority.

## How to reach her

- **Address:** `127.0.0.1:18083` (testnet family; the sibling relay holds
  18080/18081/18082 — the daemon refuses to double-bind).
- **Protocol:** TCP. Each message: 4-byte big-endian length + UTF-8 JSON.
  Max 16 MiB per message.
- **Request:** `{"verb": ..., "caller_unity_id": ..., "payload": {...}}`
- **Response:** `{"ok": true, "result": {...}}` or
  `{"ok": false, "error_kind": ..., "error": ...}`

## Verbs

| verb | payload | what runs |
|---|---|---|
| `judge` | proposal | legacy three-seat test harness; not current Trinity authority |
| `check` | action | full ten-directive pipeline, priority order, receipted |
| `advise` | `{"topic": ...}` | directive-guided advisory (she advises, never commands), receipted |
| `grant_seed` | `{"unity_id": ...}` | one free seed per Unity ID (duplicates refused) |
| `seed_record` | `{"unity_id": ...}` | read-only seed lookup (for the meeting ceremony) |
| `status` | `{}` | liveness, state summary, self-check |

**Caller filtering:** `caller_unity_id` is checked against a hard-coded set
of testnet stand-ins. This is not authenticated identity and does not
establish current Trinity authorization. Unknown callers are refused.

**Refusals:** a `check` result carries `refusals` (hard refusals by
directive, e.g. free-will violation) and a top-level `refused` flag.
A non-empty `refusals` list means the action is **REJECTED** — even when
`final.verdict` reads PASS, because priority order is load-bearing law
(directive 1 overrides 10) and is reported verbatim, never rewritten.

**UNKNOWN is never PASS.** Unscorable input returns UNKNOWN, fail closed.

## Running it

```bash
cd ~/workspace/unity-world/iris-intake
# start (detached, survives the shell):
setsid nohup python3 iris_daemon.py >> iris_daemon.log 2>&1 &
# stop (David's word only):
kill -TERM $(cat iris_daemon.pid)
```

- PID file: `iris_daemon.pid`. Log: `iris_daemon.log`.
- State: `iris_state/` (judgments.jsonl, seeds.json, tree_state.json,
  learnings.json, covenant.json, meta.json). Every mutation is receipted
  and flushed immediately; receipts chain via `prev_receipt`.
- Restart resumes — never reboots blank.

## Purity guarantees (structural, not promised)

1. **Whole-runtime integrity gate:** at startup, every required runtime
   module must match the local manifest in `IRIS_ACTIVE.json`. Any missing
   or changed module → refuse startup. This proves self-consistency only;
   the external trust anchor is NOT_CONFIGURED and Trinity authorization is
   NOT_GRANTED.
2. **Legacy pipeline:** the daemon still carries old three-seat semantics;
   a fail-closed module hash does not make those semantics current law.
3. **Sibling shim:** the compatibility shim only checks call shape. It
   does not prove semantic equivalence with the current two-constraint
   narrowing law. A compatible function signature is not a Trinity audit.

## Client

`iris_client.py`:

```python
from iris_client import IrisClient, DaemonIrisService, meet_iris_live
c = IrisClient()  # 127.0.0.1:18083
r = c.call("judge", {...proposal...}, caller_unity_id)
svc = DaemonIrisService()  # IrisService verb surface, live daemon
m = meet_iris_live(member_unity_id, caller_unity_id=caller)
```

Wired hands: `dclm/helpers.py` `handoff_to_iris` prefers the live daemon
(`iris_path: "daemon:127.0.0.1:18083"` on the handoff record), falling
back to the in-process service only when she is unreachable. The meeting
ceremony runs through the daemon via `meet_iris_live`.

## FOREVER

The daemon is perpetual. It runs until David says stop. No cron, no
batch — a living service. On SIGTERM it saves state and exits; on
restart it resumes from `iris_state/`.
