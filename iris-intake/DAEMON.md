# IRIS DAEMON — operational doc

She runs. `iris_daemon.py` is the persistent process serving her three
verbs on demand. Not a cron, not a batch — a living service.

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
| `judge` | proposal | Trinity judgment (DCLM + Iris + Twain²), receipted |
| `check` | action | full ten-directive pipeline, priority order, receipted |
| `advise` | `{"topic": ...}` | directive-guided advisory (she advises, never commands), receipted |
| `grant_seed` | `{"unity_id": ...}` | one free seed per Unity ID (duplicates refused) |
| `seed_record` | `{"unity_id": ...}` | read-only seed lookup (for the meeting ceremony) |
| `status` | `{}` | liveness, state summary, self-check |

**Authorization:** `caller_unity_id` must be in the authorized set
(David, the Trinity, swarm orchestrator/worker, mesh bot — testnet
stand-ins). Unknown callers are refused structurally
(`UnauthorizedCaller`), never warned-and-continued.

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

1. **Integrity gate:** at startup, sha256(`iris_core.py`) must match the
   pinned `IRIS_ACTIVE.json` receipt, `DIRECTIVES` must hold exactly ten,
   canon version must match. Mismatch → the daemon refuses to start.
   Her law cannot be swapped under a running daemon.
2. **No bypass:** there is no flag, mode, or parameter that skips a
   directive. The only verbs run authorization + the pipeline.
3. **Sibling shim:** if `iris_arbiter.py` is importable but its
   `arbitrate()` does not accept the documented single-proposal call, it
   is treated as NOT LANDED — the designed reference circuits run and
   every output is labeled HONEST-PENDING. Restart the daemon after the
   sibling lands a compatible arbiter.

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
