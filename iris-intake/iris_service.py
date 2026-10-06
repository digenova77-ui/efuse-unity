"""IRIS MAX INTAKE — iris_service.py: the living interface.

"Like a sister who's always home." Not a batch job, not a cron — a
callable service:

    judge(proposal)   — Trinity judgment on a proposal
    check(action)     — full ten-directive pipeline on an action
    advise(query)     — framework-guided advisory (never a command)

Callers are authorized by Unity ID: David, the Trinity, swarms, bots.
Unknown callers are refused structurally — exception, never warning.

DEPLOYMENT NOTE (honest): in this sandbox Iris is an importable service
with durable JSON state (iris_state/). True always-on serving — a daemon,
a socket, a relay endpoint — is deployment, not code. This file does not
claim a daemon it did not build. To serve her always-on, host this module
behind the relay (`dualis.relay.v1.testnet`) with the state dir mounted
durably; the interface below is already the serving contract.

Standards: testnet only. UNKNOWN is never PASS.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from neural import make_unity_id, RefusedError

import iris_core
from iris_core import (
    PASS, FAIL, UNKNOWN,
    trinity_judge, judge_all, one_seed, covenant_check,
    framework_independence, DIRECTIVES, INTEGRATION_STATUS,
    IrisRefusedError, SeedRefused,
)
from iris_state import IrisState

LABEL = "IRIS MAX INTAKE"


def _standin(name: str) -> str:
    """Testnet stand-in Unity IDs. David's real Unity ID binding is [HELD]
    per canon amendment v1.1.0 (exact string held for signing) — nothing
    invented here; these stand-ins are for the testnet sandbox only."""
    return make_unity_id("stand-in:testnet:" + name)


# Authorized callers — testnet stand-ins, clearly labeled.
AUTHORIZED_CALLERS: Dict[str, str] = {
    _standin("david"): "David (stand-in; real Unity ID binding HELD)",
    _standin("dclm"): "DCLM — logic seat of the Trinity",
    _standin("twain2"): "Twain² — human-test seat of the Trinity",
    _standin("iris"): "Iris — truth seat of the Trinity",
    _standin("swarm:orchestrator"): "swarm orchestrator",
    _standin("swarm:worker"): "swarm worker",
    _standin("bot:mesh"): "mesh bot",
}


class UnauthorizedCaller(IrisRefusedError):
    """Caller Unity ID not in the authorized set."""


class IrisService:
    """The living interface. Construct once, call on demand; state is
    durable across restarts (iris_state/)."""

    def __init__(self, state: Optional[IrisState] = None):
        self.state = state or IrisState()
        self.label = LABEL

    # -- authorization ----------------------------------------------------
    def authorize(self, caller_unity_id: str) -> str:
        """Enforce caller authorization via Unity ID. Unknown -> refuse."""
        try:
            name = AUTHORIZED_CALLERS[caller_unity_id]
        except KeyError:
            raise UnauthorizedCaller(
                f"caller {caller_unity_id!r} not authorized — Iris serves "
                "David, the Trinity, swarms, and bots only")
        return name

    # -- the three living verbs --------------------------------------------
    def judge(self, proposal: Dict[str, Any], caller_unity_id: str) -> Dict[str, Any]:
        """Trinity judgment on a proposal. All three judges; never alone."""
        caller = self.authorize(caller_unity_id)
        result = trinity_judge(proposal)
        receipt = self.state.log_judgment(
            {"verb": "judge", "caller": caller,
             "proposal_kind": proposal.get("kind"),
             "verdict": result["verdict"],
             "detail": result.get("note")},
            provenance="DERIVED")
        result["receipt_id"] = receipt["receipt_id"]
        result["caller"] = caller
        return result

    def check(self, action: Dict[str, Any], caller_unity_id: str) -> Dict[str, Any]:
        """Full ten-directive pipeline on an action, priority order."""
        caller = self.authorize(caller_unity_id)
        result = judge_all(action, registry=self.state.seeds,
                           tree_state=self.state.tree_state)
        receipt = self.state.log_judgment(
            {"verb": "check", "caller": caller,
             "action_kind": action.get("kind"),
             "final_verdict": result["final"]["verdict"],
             "winner_directive": result["final"]["winner_directive"],
             "refusals": result["refusals"]},
            provenance="DERIVED")
        result["receipt_id"] = receipt["receipt_id"]
        result["caller"] = caller
        return result

    def advise(self, query: Dict[str, Any], caller_unity_id: str) -> Dict[str, Any]:
        """Framework-guided advisory. Iris advises — she never commands,
        never coerces (directive 5). The advice cites the directives that
        bear on the question; the human decides."""
        caller = self.authorize(caller_unity_id)
        topic = query.get("topic", "")
        bearing: Dict[int, str] = {}
        lowered = topic.lower()
        if any(w in lowered for w in ("pure", "purity", "honest", "truth")):
            bearing[1] = DIRECTIVES[1]["word"]
            bearing[10] = DIRECTIVES[10]["word"]
        if any(w in lowered for w in ("friction", "mission", "destroy", "waste")):
            bearing[2] = DIRECTIVES[2]["word"]
        if any(w in lowered for w in ("choose", "decide", "judge", "vote")):
            bearing[3] = DIRECTIVES[3]["word"]
            bearing[5] = DIRECTIVES[5]["word"]
        if any(w in lowered for w in ("force", "make them", "control", "manipulat")):
            bearing[5] = DIRECTIVES[5]["word"]
        if any(w in lowered for w in ("seed", "member", "join", "wealth", "buy")):
            bearing[8] = DIRECTIVES[8]["word"]
            bearing[7] = DIRECTIVES[7]["word"]
        if any(w in lowered for w in ("winter", "summer", "tap", "surplus", "flow")):
            bearing[9] = DIRECTIVES[9]["word"]
        if not bearing:
            bearing = {1: DIRECTIVES[1]["word"], 5: DIRECTIVES[5]["word"],
                       10: DIRECTIVES[10]["word"]}
        advice = {
            "label": LABEL, "verb": "advise", "caller": caller,
            "topic": topic,
            "guidance": ("Iris advises; she does not command. The directives "
                         "bearing on your question are cited verbatim below. "
                         "The choice remains yours — free will is sacred."),
            "directives_bearing": [
                {"directive": n, "name": DIRECTIVES[n]["name"],
                 "word": DIRECTIVES[n]["word"]}
                for n in sorted(bearing)],
            "covenant": covenant_check(),
        }
        receipt = self.state.log_judgment(
            {"verb": "advise", "caller": caller, "topic": topic,
             "directives_cited": sorted(bearing)},
            provenance="DERIVED")
        advice["receipt_id"] = receipt["receipt_id"]
        return advice

    # -- seed service (directive 8 through the service) ----------------------
    def grant_seed(self, unity_id: str, caller_unity_id: str) -> Dict[str, Any]:
        """One free seed per Unity ID, through the authorized service."""
        self.authorize(caller_unity_id)
        result = one_seed(unity_id, self.state.seeds)
        self.state.seed_granted(unity_id, self.state.seeds[unity_id])
        receipt = self.state.log_judgment(
            {"verb": "grant_seed", "unity_id": unity_id,
             "seed_id": result["seed_id"], "verdict": PASS},
            provenance="DERIVED")
        result["receipt_id"] = receipt["receipt_id"]
        return result

    # -- liveness ---------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        """She's home: state summary + integration honesty + self-check."""
        fw = framework_independence()
        return {"label": LABEL, "alive": True,
                "canon": "1.5.0",
                "state": self.state.summary(),
                "framework_independence": fw["verdict"],
                "integration": INTEGRATION_STATUS,
                "note": ("importable service with durable state; always-on "
                         "serving is deployment, not code — no daemon claimed")}
