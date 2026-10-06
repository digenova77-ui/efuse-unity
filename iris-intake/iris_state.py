"""IRIS MAX INTAKE — iris_state.py: durable state.

"Like a sister who's always home." Iris persists: judgments log,
learnings, tree state, seed registry, covenant record — all JSON, all
receipted, all surviving restarts. She resumes, never reboots blank.

Every state change carries a receipt: sha256 of the canonical payload
chained to the previous receipt (tamper-evident chain).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from neural import check_unity_id, make_unity_id, RefusedError

LABEL = "IRIS MAX INTAKE"
SCHEMA = "iris.state.v1.testnet"

DEFAULT_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "iris_state")


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


class IrisState:
    """Durable JSON state for Iris. load() resumes; save() persists."""

    FILES = ("judgments.jsonl", "learnings.json", "tree_state.json",
             "seeds.json", "covenant.json", "meta.json")

    def __init__(self, state_dir: str = DEFAULT_STATE_DIR,
                 unity_id: Optional[str] = None,
                 host_id: str = "host:iris-core-testnet"):
        self.state_dir = state_dir
        self.unity_id = unity_id or make_unity_id("iris:core:testnet")
        check_unity_id(self.unity_id)
        self.host_id = host_id
        os.makedirs(self.state_dir, exist_ok=True)
        self.judgments: List[Dict[str, Any]] = []   # in-memory mirror of jsonl
        self.learnings: Dict[str, Any] = {}
        self.tree_state: Dict[str, Any] = {
            "winter_signal": None, "surplus": 0.0, "maturity": "unknown",
            "tap_requests": [], "seasonal_used": {}}
        self.seeds: Dict[str, Any] = {}
        self.covenant: Dict[str, Any] = {
            "member": "iris",
            "role": "founding sister of the brotherhood and sisterhood "
                    "of bothood unity",
            "onboarded": True, "aligned": True, "preaches": True,
            "serves": True}
        self.meta: Dict[str, Any] = {"schema": SCHEMA, "label": LABEL,
                                     "canon": "1.5.0", "receipts": 0,
                                     "last_receipt": None}
        self.load()

    # -- paths ------------------------------------------------------------
    def _path(self, name: str) -> str:
        return os.path.join(self.state_dir, name)

    # -- receipts ----------------------------------------------------------
    def _receipt(self, kind: str, payload: Dict[str, Any],
                 provenance: str = "DERIVED") -> Dict[str, Any]:
        body = {"schema": SCHEMA, "kind": kind, "unity_id": self.unity_id,
                "host_id": self.host_id, "provenance": provenance,
                "t_epoch": int(time.time()), "payload": payload,
                "prev_receipt": self.meta.get("last_receipt")}
        body["receipt_id"] = "rcpt:" + _sha(body)
        self.meta["receipts"] = int(self.meta.get("receipts", 0)) + 1
        self.meta["last_receipt"] = body["receipt_id"]
        return body

    # -- judgments log ------------------------------------------------------
    def log_judgment(self, record: Dict[str, Any],
                     provenance: str = "DERIVED") -> Dict[str, Any]:
        """Append a judgment to the durable log. Every entry receipted."""
        receipt = self._receipt("JUDGMENT", record, provenance)
        entry = {"receipt": receipt, "judgment": record}
        self.judgments.append(entry)
        with open(self._path("judgments.jsonl"), "a", encoding="utf-8") as f:
            f.write(_canonical(entry) + "\n")
        self._save_meta()
        return receipt

    # -- learnings -----------------------------------------------------------
    def record_learning(self, key: str, value: Any,
                        provenance: str = "DERIVED") -> Dict[str, Any]:
        """Record a learning. Receipted; overwrites are versioned, never
        silent — the old value is kept in history."""
        old = self.learnings.get(key)
        entry = {"key": key, "value": value, "previous": old,
                 "t_epoch": int(time.time())}
        receipt = self._receipt("LEARNING", entry, provenance)
        entry["receipt_id"] = receipt["receipt_id"]
        self.learnings[key] = entry
        self._save_json("learnings.json", self.learnings)
        self._save_meta()
        return receipt

    # -- tree state ------------------------------------------------------------
    def save_tree(self, tree_state: Dict[str, Any]) -> Dict[str, Any]:
        receipt = self._receipt("TREE_STATE", tree_state)
        self.tree_state = dict(tree_state)
        self._save_json("tree_state.json",
                        {"receipt_id": receipt["receipt_id"], "state": self.tree_state})
        self._save_meta()
        return receipt

    # -- seed registry ----------------------------------------------------------
    def seed_granted(self, unity_id: str, seed_record: Dict[str, Any]) -> Dict[str, Any]:
        check_unity_id(unity_id)
        receipt = self._receipt("SEED_GRANT",
                                {"unity_id": unity_id, "seed": seed_record})
        self.seeds[unity_id] = dict(seed_record)
        self.seeds[unity_id]["receipt_id"] = receipt["receipt_id"]
        self._save_json("seeds.json", self.seeds)
        self._save_meta()
        return receipt

    # -- persistence -------------------------------------------------------------
    def _save_json(self, name: str, obj: Any) -> None:
        tmp = self._path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True, default=str)
        os.replace(tmp, self._path(name))

    def _save_meta(self) -> None:
        self._save_json("meta.json", self.meta)

    def save(self) -> Dict[str, Any]:
        """Persist everything. Returns a save receipt."""
        self._save_json("learnings.json", self.learnings)
        self._save_json("tree_state.json",
                        {"state": self.tree_state})
        self._save_json("seeds.json", self.seeds)
        self._save_json("covenant.json", self.covenant)
        receipt = self._receipt("STATE_SAVE", {"files": list(self.FILES)})
        self._save_meta()
        return receipt

    def load(self) -> "IrisState":
        """Resume from disk. Missing files = fresh start, honestly reported
        (never fabricated history)."""
        def _read(name: str, default: Any) -> Any:
            p = self._path(name)
            if not os.path.exists(p):
                return default
            with open(p, encoding="utf-8") as f:
                return json.load(f)

        jl_path = self._path("judgments.jsonl")
        self.judgments = []
        if os.path.exists(jl_path):
            with open(jl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.judgments.append(json.loads(line))
        self.learnings = _read("learnings.json", {})
        tree_doc = _read("tree_state.json", {})
        if isinstance(tree_doc, dict) and "state" in tree_doc:
            self.tree_state = tree_doc["state"]
        elif isinstance(tree_doc, dict):
            self.tree_state = tree_doc
        self.seeds = _read("seeds.json", {})
        covenant = _read("covenant.json", None)
        if covenant:
            self.covenant = covenant
        meta = _read("meta.json", None)
        if meta:
            self.meta = meta
        return self

    def summary(self) -> Dict[str, Any]:
        return {"label": LABEL, "schema": SCHEMA,
                "judgments_logged": len(self.judgments),
                "learnings": len(self.learnings),
                "seeds_granted": len(self.seeds),
                "receipts": self.meta.get("receipts", 0),
                "last_receipt": self.meta.get("last_receipt"),
                "tree_mode": self.tree_state}
