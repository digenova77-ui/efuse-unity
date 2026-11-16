# IRIS DAEMON — legacy testnet operational doc

**STATUS: LEGACY / TESTNET ONLY / NOT CURRENT-TRINITY AUTHORIZED.**

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

| verb | payload | current behavior |
|---|---|---|
| `judge` | proposal | two-primary 2P5L evidence only; returns STALEMATE until canonical Narrow is wired |
| `check` | action | same provisional evidence path; never promotes evidence to FLAWLESS |
| `advise` | `{"topic": ...}` | reads current root CANON.md sections; no state write |
| `grant_seed` | `{"unity_id": ...}` | always refused by Iris; use the DCLM seed worker and its binding / rights / commit path |
| `seed_record` | `{"unity_id": ...}` | read-only legacy mirror lookup; meeting accepts only a verified DCLM SEED_ISSUE envelope |
| `status` | `{}` | liveness, state summary, current-canon version, and explicit holds |

**Caller filtering:** `caller_unity_id` is checked against a hard-coded set
of testnet stand-ins. This is not authenticated identity and does not
establish current Trinity authorization. The withdrawn Twain² stand-in
is not in the allowlist.

**No Iris writes:** judge, check, advise, and grant_seed do not mutate state.
Seed issuance belongs to `dclm.seed.Seeder.issue_seed`, which performs the
binding check, DCLM rights check, and `dclm_commit`. Iris refuses to issue
a seed. The current DCLM seeder still has an in-memory per-instance registry;
durable cross-process uniqueness remains a separate unresolved gate.

**Final decision held:** the 2P5L path provides diagnostic evidence from
DCLM logic and Iris truth. The current root canon's `dclm/narrow.py`
decision function has not yet been wired to a lawful x/y score mapping.
Therefore the service returns STALEMATE, not PASS or FLAWLESS. The meeting
ceremony refuses to speak until canonical FLAWLESS is produced.

**UNKNOWN is never PASS.** Missing, unscorable, or unverified evidence does
not produce a positive decision.

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
   module must match the local manifest in `IRIS_SELF_CHECK.json`. Any missing
   or changed module → refuse startup. This proves self-consistency only;
   the external trust anchor is NOT_CONFIGURED and Trinity authorization is
   NOT_GRANTED.
2. **Legacy modules held:** `iris_core.py` and `iris_arbiter.py` retain
   historical three-seat functions for research compatibility. The current
   service path does not call them.
3. **No final authorization:** runtime consistency and two-primary evidence
   do not establish Flawless, ratification, or a write grant. The canonical
   Narrow adapter remains NOT_WIRED.

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

## Operational limitation

This is a manually started testnet daemon, not a supervised production
service. It runs until SIGTERM or host/process failure. Restart behavior is
covered by tests; automatic supervision, independent availability, and
production operation are not claimed.

## Verification scope

`.github/workflows/iris-runtime-integrity.yml` runs the compile check,
activation suites, daemon wire/tamper tests, and 2P5L tests on matching
feature-branch pushes and pull requests. An absent workflow run is not a
pass; only a completed green run is verification evidence.
