"""Honest purity status reporter — canonical emission (estate.purity.v1).

Grades are computed from what the code actually does, not from documentation.
UNKNOWN is never PASS. LAW WINS. NOT_FOR_EMISSION.

ADOPTION.md Step 7 retirement (disposition D-T3-7, option A — native
canonical emission): status() now emits the canonical shape natively
— schema "estate.purity.v1", protocol exactly "PURITY.v1" — instead
of the legacy dialect string "UNITY.PURITY.v1". The legacy string and
every dialect-unique field are preserved under dialect_extras;
nothing is deleted. The field set mirrors
canon_registry/purity_canonical.py emit_canonical() in the
canon-registry, extended with this surface's probed field grades.

D3 ride-along: unknown_never_pass is now an explicit field of the
emitted record (evidence "native_declaration"), not only docstring
plus grade logic. The matching canon-registry register update is
prepared alongside this change (D3-REGISTER-UPDATE.patch in this
change's landing package): adapt_efuse learns to accept the explicit
field with evidence "explicit_field". Until both changes land
together, the live adapter still refuses an efuse-shaped object
carrying the field (D3-DRIFT) — that refusal is the tripwire working
as designed, and it is why the two changes must land in one act.

D8 ride-along: keys_used_append_only / current_key_only are no
longer literal True. key_design_status() probes both at runtime
against unity_keys: append-only is measured by snapshotting
keys_used across bind / rotate / refused reuse / refused payment /
refused old-key rotation / unbind / re-bind / current-key rotation
and requiring every step to be a prefix-extension that never
deletes; current-key-only is measured by an old-key payment refused,
an old-key rotation refused, and a current-key rotation accepted
(the control that proves the gate is key-specific, not a blanket
refusal). If a probe fails, its flag is False and its canonical
grade is UNKNOWN — never a literal dressed as a measurement.

D4 stands under every option: measured.seal_hash_check is still
only asserted by this file ("present in landing worker"), so its
canonical grade stays UNKNOWN. The asserted value survives as data
under dialect_extras; it grants nothing.
"""

from __future__ import annotations

from typing import Dict, Any, List

from unity_keys import UnityStore, unity_bind, unity_key, unity_unbind, merit_pay


def _is_prefix(shorter: List[str], longer: List[str]) -> bool:
    return len(longer) >= len(shorter) and longer[:len(shorter)] == shorter


def key_design_status() -> Dict[str, Any]:
    st = UnityStore()
    snapshots: List[List[str]] = []

    def snap() -> List[str]:
        keys = list(st.unity["probe"].keys_used)
        snapshots.append(keys)
        return keys

    unity_bind(st, "probe", "pk-probe", "sig-pk-probe")
    snap()
    unity_key(st, "probe", "pk-next", "sig-pk-probe")
    snap()
    reused = False
    try:
        unity_key(st, "probe", "pk-probe", "sig-pk-next")
    except ValueError as e:
        reused = "UNITY_KEY_REUSED" in str(e)
    snap()
    old_pay = False
    try:
        merit_pay(st, "probe", "probe", 1, "n-probe", "sig-pk-probe")
    except ValueError as e:
        old_pay = "PAY_BAD_SIGNATURE" in str(e)
    snap()
    # D8 probe — current-key-only, refusal half: the OLD key (pk-probe,
    # rotated away from) must not authorize a rotation either.
    old_rotation_refused = False
    try:
        unity_key(st, "probe", "pk-third", "sig-pk-probe")
    except ValueError as e:
        old_rotation_refused = "KEY_BAD_SIGNATURE" in str(e)
    snap()
    # D8 probe — append-only under unbind: unbinding deletes nothing.
    unity_unbind(st, "probe")
    after_unbind = snap()
    # Re-bind with the current key so the control rotation can run;
    # binding an already-used key must not duplicate or delete it.
    unity_bind(st, "probe", "pk-next", "sig-pk-next")
    snap()
    # D8 probe — current-key-only, control half: the CURRENT key
    # (pk-next) DOES authorize a rotation, to pk-third.
    current_rotation_accepted = False
    try:
        unity_key(st, "probe", "pk-third", "sig-pk-next")
        current_rotation_accepted = st.unity["probe"].pubkey == "pk-third"
    except ValueError:
        current_rotation_accepted = False
    snap()

    append_only = (
        all(_is_prefix(a, b) for a, b in zip(snapshots, snapshots[1:]))
        and after_unbind == ["pk-probe", "pk-next"]
        and snapshots[-1] == ["pk-probe", "pk-next", "pk-third"]
    )
    current_key_only = bool(
        old_pay and old_rotation_refused and current_rotation_accepted
    )
    return {
        "grade": "MEASURED" if reused and old_pay else "UNKNOWN",
        "unity_key_reused_enforced": reused,
        "old_key_pay_refused": old_pay,
        "old_key_rotation_refused": old_rotation_refused,
        "current_key_rotation_accepted": current_rotation_accepted,
        "keys_used_append_only": append_only,
        "current_key_only": current_key_only,
    }


def status() -> Dict[str, Any]:
    keys = key_design_status()
    probed_grade = "PROVEN (measured)" if keys["grade"] == "MEASURED" else "UNKNOWN"

    def flag_grade(flag: bool) -> str:
        # A probed flag grades PROVEN (measured) only when its probe
        # passed; a failed probe is UNKNOWN, never REPORTED-as-True.
        return "PROVEN (measured)" if flag else "UNKNOWN"

    return {
        "schema": "estate.purity.v1",
        "dialect": "canonical",
        "protocol": "PURITY.v1",
        "source_protocol": "PURITY.v1",
        "law": "LAW WINS",
        "boundary": "NOT_FOR_EMISSION",
        "emission": "HELD",
        "unknown_never_pass": True,
        "unknown_never_pass_evidence": "native_declaration",
        "field_grades": {
            "law": "REPORTED",
            "boundary": "REPORTED",
            "emission": "REPORTED",
            "unknown_never_pass": "REPORTED",
            "key_design": probed_grade,
            "measured.key_gates": probed_grade,
            "seal_hash_check": "UNKNOWN",
            "keys_used_append_only": flag_grade(keys["keys_used_append_only"]),
            "current_key_only": flag_grade(keys["current_key_only"]),
        },
        "dialect_extras": {
            "legacy_protocol": "UNITY.PURITY.v1",
            "origin": "immutable",
            "fail_closed": True,
            "key_design": keys,
            "peg_ratio_E": "HELD",
            "live_coin": False,
            "live_wallet": False,
            "measured": {
                "key_gates": keys["grade"],
                # Asserted here, not probed by this file ("present in
                # landing worker") — canonical grade UNKNOWN (D4).
                "seal_hash_check": "MEASURED",
            },
            "hypothetical": ["full residual movement", "live emission", "second pinner"],
        },
        "translation_grade": "NATIVE",
        "translation_losses": [],
        # D4 is carried, not waived: the seal claim stays UNKNOWN.
        "tripwires": ["D4"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))
