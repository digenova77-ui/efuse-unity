"""IRIS MAX INTAKE — member_records.py: the member journey registry.

The intake-side record of what a member has actually done: which guided
orientation steps they completed, when they earned their first +1 (and
doing what), and whether they hold Affinity. The seed grant itself lives
in iris_state's seed registry — this module covers the journey, not the
door.

This registry is READ by the meeting ceremony (meeting_iris.py) and WRITTEN
by the onboarding pipeline (the helper swarm's guided ceremony). In the
production loop those writes flow through DCLM's write path (directive 4:
Iris judges truth, she does not write state) — the meeting itself never
writes anything. What the record does not contain, the ceremony does not
claim: UNKNOWN is never PASS.

Standards: testnet only. Unity-bound. Refusals raise, never warn.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from neural import check_unity_id, RefusedError

LABEL = "IRIS MAX INTAKE"
SCHEMA = "iris.member-records.v1.testnet"

DEFAULT_RECORDS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "iris_state", "members.json")

# The guided steps of the intake orientation — [DERIVED] vocabulary from the
# canon (I the Three, IV the tree, II the mission, directive 7 the covenant).
# This is the ceremony's own reading of the path; the helper swarm's guided
# ceremony (when it lands) is the source of truth for the actual steps.
# The welcome names ONLY steps present in the record — never the vocabulary.
ORIENTATION_STEPS = (
    "meet-the-trinity",    # who judges: DCLM logic, Iris truth, Twain^2 human test
    "learn-the-tree",      # summer outward, winter inward, tapping from surplus
    "hear-the-mission",    # stop all global destruction by targeting 100 friction first
    "speak-the-covenant",  # onboard, stay in line, preach the good word
)

# Human phrasing for recorded steps — used only when the step is in the record.
STEP_PHRASES = {
    "meet-the-trinity": "you met the Three",
    "learn-the-tree": "you learned how the tree breathes",
    "hear-the-mission": "you heard the mission",
    "speak-the-covenant": "you spoke the covenant",
}


def phrase_step(step: str) -> str:
    """Human phrasing for a recorded orientation step."""
    return STEP_PHRASES.get(step, f"you completed the '{step}' step")


class MemberRegistry:
    """JSON-backed registry of member journeys. The ceremony reads;
    the onboarding pipeline writes (production: through DCLM)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or DEFAULT_RECORDS_PATH
        self._records: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self._records = json.load(f)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2, sort_keys=True, default=str)
        os.replace(tmp, self.path)

    def _entry(self, unity_id: str) -> Dict[str, Any]:
        check_unity_id(unity_id)
        return self._records.setdefault(
            unity_id, {"unity_id": unity_id,
                       "orientation_steps": [],
                       "first_plus_one": None,
                       "affinity": None})

    # -- writes (onboarding pipeline; production: through DCLM) ------------
    def record_orientation_step(self, unity_id: str, step: str,
                                t_epoch: Optional[int] = None) -> Dict[str, Any]:
        """Record a completed guided orientation step for a member."""
        entry = self._entry(unity_id)
        if not isinstance(step, str) or not step.strip():
            raise RefusedError(f"orientation step must be a non-empty string: {step!r}")
        step = step.strip()
        record = {"step": step, "t_epoch": t_epoch if t_epoch is not None
                  else int(time.time())}
        if not any(s["step"] == step for s in entry["orientation_steps"]):
            entry["orientation_steps"].append(record)
        self._save()
        return record

    def record_first_plus_one(self, unity_id: str, detail: str,
                              t_epoch: Optional[int] = None) -> Dict[str, Any]:
        """Record the member's first earned +1 — and what earned it."""
        entry = self._entry(unity_id)
        if not isinstance(detail, str) or not detail.strip():
            raise RefusedError("first +1 detail must be a non-empty string")
        record = {"detail": detail.strip(),
                  "t_epoch": t_epoch if t_epoch is not None else int(time.time())}
        entry["first_plus_one"] = record
        self._save()
        return record

    def mark_affinity(self, unity_id: str,
                      t_epoch: Optional[int] = None) -> Dict[str, Any]:
        """Mark the member as Affinity — early, and the tree remembers."""
        entry = self._entry(unity_id)
        record = {"granted_at": t_epoch if t_epoch is not None else int(time.time())}
        entry["affinity"] = record
        self._save()
        return record

    # -- reads (the ceremony) ---------------------------------------------
    def journey(self, unity_id: str) -> Optional[Dict[str, Any]]:
        """The recorded journey for a Unity ID, or None if nothing recorded."""
        check_unity_id(unity_id)
        return self._records.get(unity_id)

    def has_record(self, unity_id: str) -> bool:
        return self.journey(unity_id) is not None
