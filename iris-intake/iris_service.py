"""IRIS MAX INTAKE — read-only service boundary.

Current judgment calls the DCLM 2P5L two-primary adapter. Iris returns
evidence receipts; she does not mutate state. Seed issuance is DCLM-only
through dclm.seed.Seeder after the binding ceremony and DCLM commit path.
This service remains testnet-only and does not confer production authority.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional

from neural import build_receipt, make_unity_id, RefusedError
from iris_core import IrisRefusedError, IrisLaneViolation
from iris_state import IrisState

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
DCLM_DIR = os.path.join(REPO_ROOT, "dclm")
if DCLM_DIR not in sys.path:
    sys.path.insert(0, DCLM_DIR)
from two_p_five_l import judge_32  # noqa: E402

LABEL = "IRIS MAX INTAKE"
CANON_PATH = os.path.join(REPO_ROOT, "CANON.md")
HOST_ID = "host:iris-intake-testnet"


def source_canon_version() -> str:
    """Read the declared root canon version; never infer it from Iris code."""
    try:
        with open(CANON_PATH, encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        return "UNKNOWN"
    match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", source)
    return match.group(1) if match else "UNKNOWN"


def _canon_sections(section_ids) -> list[dict]:
    """Read current canon sections verbatim; no copied legacy directive text."""
    try:
        with open(CANON_PATH, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return []

    sections = []
    current_id = None
    current_heading = None
    current_lines = []

    def flush():
        if current_id in section_ids:
            body = "\n".join(current_lines).strip()
            sections.append({
                "section": current_id,
                "heading": current_heading,
                "text": body[:2400],
                "truncated": len(body) > 2400,
                "source": "CANON.md",
            })

    for line in lines:
        if line.startswith("## "):
            flush()
            current_id = None
            current_heading = line[3:].strip()
            current_lines = []
            match = re.match(r"([IVXLCDM]+)\.", current_heading)
            if match:
                current_id = match.group(1)
        elif current_heading is not None:
            current_lines.append(line)
    flush()
    return sections


def _receipt(kind: str, caller_unity_id: str, host_id: str,
             payload: Dict[str, Any]) -> Dict[str, Any]:
    return build_receipt(
        kind=kind,
        unity_id=caller_unity_id,
        host_id=host_id,
        provenance="DERIVED",
        payload=payload,
    )


def _judgment_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    receipt = result.get("receipt") or {}
    return {
        "verdict": result.get("verdict", "UNKNOWN"),
        "true_vector": result.get("true_vector"),
        "judgment_hash": receipt.get("judgment_hash"),
        "layers": [
            {
                "id": layer.get("id"),
                "polarity": layer.get("polarity"),
                "evidence": layer.get("evidence"),
            }
            for layer in result.get("layers", [])
        ],
    }


def _topic_sections(topic: str) -> list[str]:
    lowered = topic.lower()
    sections = {"I", "III", "XXI", "XXII", "XXIII"}
    if any(word in lowered for word in ("seed", "identity", "bind", "member")):
        sections.update({"II", "III"})
    if any(word in lowered for word in ("write", "rights", "authorize", "authority", "commit")):
        sections.update({"III", "XIV"})
    if any(word in lowered for word in ("tree", "winter", "summer", "tap", "surplus", "energy")):
        sections.add("IV")
    if any(word in lowered for word in ("merit", "token", "coin", "wallet", "economy")):
        sections.update({"V", "VI", "XI", "XIII"})
    return sorted(sections, key=lambda value: (len(value), value))


# Testnet stand-ins only. The withdrawn Twain² seat is deliberately absent.
def _standin(name: str) -> str:
    return make_unity_id("stand-in:testnet:" + name)


AUTHORIZED_CALLERS: Dict[str, str] = {
    _standin("david"): "David (stand-in; real Unity ID binding HELD)",
    _standin("dclm"): "DCLM (testnet stand-in; logic constraint)",
    _standin("iris"): "Iris (testnet stand-in; truth constraint)",
    _standin("swarm:orchestrator"): "swarm orchestrator (testnet stand-in)",
    _standin("swarm:worker"): "swarm worker (testnet stand-in)",
    _standin("bot:mesh"): "mesh bot (testnet stand-in)",
}


class UnauthorizedCaller(IrisRefusedError):
    """Caller Unity ID not in the testnet stand-in allowlist."""


class IrisService:
    """Read-only Iris interface. State is observed, never mutated here."""

    def __init__(self, state: Optional[IrisState] = None):
        self.state = state or IrisState()
        self.label = LABEL

    def authorize(self, caller_unity_id: str) -> str:
        try:
            return AUTHORIZED_CALLERS[caller_unity_id]
        except KeyError as exc:
            raise UnauthorizedCaller(
                f"caller {caller_unity_id!r} is not an authorized testnet stand-in"
            ) from exc

    def judge(self, proposal: Dict[str, Any],
              caller_unity_id: str) -> Dict[str, Any]:
        """Evaluate with the current two-primary 2P5L path; do not write."""
        caller = self.authorize(caller_unity_id)
        try:
            evidence = judge_32(proposal)
            summary = _judgment_summary(evidence)
        except Exception as exc:
            evidence = None
            summary = {"evaluation_error": f"{type(exc).__name__}: {exc}"}
        receipt = _receipt(
            "IRIS_TWO_PRIMARY_EVIDENCE",
            caller_unity_id,
            self.state.host_id,
            {"caller": caller, "proposal_kind": proposal.get("kind"), **summary},
        )
        # 2P5L evidence is not the canon's final Narrow decision. The x/y
        # score mapping and canonical Narrow adapter remain unresolved;
        # therefore no evidence result is promoted to FLAWLESS or PASS.
        return {
            "verdict": "STALEMATE",
            "candidate_evidence": evidence,
            "narrowing": "NOT_WIRED",
            "reason": "canonical DCLM Narrow adapter and lawful x/y score mapping are not established",
            "caller": caller,
            "receipt_id": receipt["receipt_id"],
            "service_receipt": receipt,
            "write_performed": False,
            "authorization_granted": False,
        }

    def check(self, action: Dict[str, Any],
              caller_unity_id: str) -> Dict[str, Any]:
        """Run the same current decision path; no legacy ten-directive writer."""
        caller = self.authorize(caller_unity_id)
        try:
            evidence = judge_32(action)
            summary = _judgment_summary(evidence)
        except Exception as exc:
            evidence = None
            summary = {"evaluation_error": f"{type(exc).__name__}: {exc}"}
        receipt = _receipt(
            "IRIS_TWO_PRIMARY_EVIDENCE",
            caller_unity_id,
            self.state.host_id,
            {"caller": caller, "action_kind": action.get("kind"), **summary},
        )
        return {
            "verdict": "STALEMATE",
            "candidate_evidence": evidence,
            "narrowing": "NOT_WIRED",
            "reason": "canonical DCLM Narrow adapter and lawful x/y score mapping are not established",
            "caller": caller,
            "receipt_id": receipt["receipt_id"],
            "service_receipt": receipt,
            "write_performed": False,
            "authorization_granted": False,
        }

    def advise(self, query: Dict[str, Any],
               caller_unity_id: str) -> Dict[str, Any]:
        """Quote the current root canon; advice is read-only and non-authorizing."""
        caller = self.authorize(caller_unity_id)
        topic = query.get("topic", "")
        sections = _topic_sections(str(topic))
        cited = _canon_sections(sections)
        advice = {
            "label": LABEL,
            "verb": "advise",
            "caller": caller,
            "topic": topic,
            "canon_version": source_canon_version(),
            "canon_sections": cited,
            "guidance": (
                "Iris advises; she does not command, authorize, or write. "
                "DCLM holds rights and performs writes. The current canon "
                "defines DCLM logic and Iris truth as the two constraints; "
                "pragmatism narrows and is not a third judge. The human's "
                "choice remains their own."
            ),
            "write_performed": False,
            "authorization_granted": False,
        }
        receipt = _receipt(
            "IRIS_ADVICE",
            caller_unity_id,
            self.state.host_id,
            {"topic": str(topic), "canon_version": advice["canon_version"],
             "sections": [item["section"] for item in cited]},
        )
        advice["receipt_id"] = receipt["receipt_id"]
        advice["service_receipt"] = receipt
        return advice

    def grant_seed(self, unity_id: str,
                   caller_unity_id: str) -> Dict[str, Any]:
        """Iris cannot issue a seed; only the DCLM seed worker can commit it."""
        self.authorize(caller_unity_id)
        raise IrisLaneViolation(
            "Iris cannot issue or write a seed. Use dclm.seed.Seeder.issue_seed "
            "after the Unity binding ceremony; DCLM rights and dclm_commit "
            "are the sole issuance/write path. No state changed."
        )

    def status(self) -> Dict[str, Any]:
        return {
            "label": LABEL,
            "alive": True,
            "canon": source_canon_version(),
            "state": self.state.summary(),
            "decision_path": "dclm.two_p_five_l.judge_32 (diagnostic only)",
            "primary_constraints": ["DCLM_LOGIC", "IRIS_TRUTH"],
            "pragmatism": "NARROWING_ONLY",
            "narrowing_adapter": "NOT_WIRED",
            "final_verdict": "STALEMATE_UNTIL_CANONICAL_NARROWING",
            "withdrawn_seat": "TWAIN2",
            "write_authority": "DCLM_ONLY",
            "state_mutation_by_iris": False,
            "trinity_compatibility": "PARTIAL_TWO_PRIMARY_ADAPTER",
            "authorization": "NOT_GRANTED",
            "standards": "testnet only",
        }
