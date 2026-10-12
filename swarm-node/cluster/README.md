# DualisCapax cluster — the layer above the lanes

Two lanes exist (DCLM/New Jersey, EUROPE/Amsterdam). This is everything that
sits above them: geographic routing, the balancer diamond, health, and the
go-live pipeline.

## The shape

```
                    ┌─────────────┐
  client ──GeoDNS──▶│  balancer   │──▶ nearest healthy lane
  (region)  (DNS)   │  (diamond)  │
                    └──────┬──────┘
                           │ collapse traces (meaningful decisions only)
                    ┌──────▼──────┐
                    │   health    │◀── lane attestation/heartbeat stream
                    │  consumer   │    (the only source of truth)
                    └─────────────┘
```

Geography is DNS's job. Health is the stream's job. The balancer's brain
computes one routing table; GeoDNS answers and the HTTP proxy publish it.

## Files

| File | What it is |
|---|---|
| `balancer.py` | The ingress diamond. `compute_table(health)` → region→lanes; `decide()` diffs vs last table and emits exactly one collapse trace per real change. Per-request `route()` emits nothing. |
| `health.py` | The health consumer. UP = fresh heartbeat (+valid chain); DOWN = stale/broken; UNKNOWN = no data (fail-closed, never invented). |
| `proxy.py` | Optional stdlib HTTP front: 302 to the chosen lane, honest 503 naming the cause when none is healthy. Redirects — never re-serves. |
| `golive.py` | The "go live" word. Six gated stages; a failed stage halts, rolls back, and traces the failure. `--dry-run` prepares, never cuts over. |
| `pull-agent.py` | Runs ON the lane, outbound-only. Polls the manifest, stages + self-tests + applies node updates itself, phones home via attestations. Traffic cutover stays command-gated. |
| `manifest.json` | Version manifest the pull-agent polls. Bundle URLs curl-verified; sha256 enforced. |
| `geodns/` | BIND9 views + per-view zone answers + `geodns-agent.py` (health → answers → rndc). |
| `bundles/` | Versioned node bundles the pull-agent applies. |
| `tests/` | 27 tests, stdlib unittest. Run: `python3 tests/test_balancer.py` etc. The bootstrap fusion is a fixture script: `python3 tests/test_bootstrap_fusion.py` (one paste, run twice — proves idempotency). |

## The law, in one paragraph

The balancer is an interconnect, so it is a diamond with its own quantum
node (`qnode-cluster-ingress`, interconnect `cluster-ingress`). Its traces
use the identical unreal-memory trace format and chain with the GENESIS
convention. Only meaningful decisions collapse — lane dark/recovered,
region answer changed, new lane online, split-brain. Per-request routing
is silent; the chain would drown otherwise.

## Status (honest)

The lanes are not live yet — the swarm bootstrap awaits David's hand.
Everything here is built and tested against fixtures; the health consumer
reports UNKNOWN for both lanes until they breathe, and the balancer
fail-closes on UNKNOWN. Staged to activate per-lane, nothing pretended.
