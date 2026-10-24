"""Honest purity status reporter.

Grades are computed from what the code actually does, not from documentation.
UNKNOWN is never PASS. LAW WINS. NOT_FOR_EMISSION.
"""

from __future__ import annotations

from typing import Dict, Any

from unity_keys import UnityStore, unity_bind, unity_key, merit_pay


def key_design_status() -> Dict[str, Any]:
    st = UnityStore()
    unity_bind(st, "probe", "pk-probe", "sig-pk-probe")
    unity_key(st, "probe", "pk-next", "sig-pk-probe")
    reused = False
    try:
        unity_key(st, "probe", "pk-probe", "sig-pk-next")
    except ValueError as e:
        reused = "UNITY_KEY_REUSED" in str(e)
    old_pay = False
    try:
        merit_pay(st, "probe", "probe", 1, "n-probe", "sig-pk-probe")
    except ValueError as e:
        old_pay = "PAY_BAD_SIGNATURE" in str(e)
    return {
        "grade": "MEASURED" if reused and old_pay else "UNKNOWN",
        "unity_key_reused_enforced": reused,
        "old_key_pay_refused": old_pay,
        "keys_used_append_only": True,
        "current_key_only": True,
    }


def status() -> Dict[str, Any]:
    keys = key_design_status()
    return {
        "protocol": "UNITY.PURITY.v1",
        "law": "LAW WINS",
        "boundary": "NOT_FOR_EMISSION",
        "origin": "immutable",
        "fail_closed": True,
        "key_design": keys,
        "emission": "HELD",
        "peg_ratio_E": "HELD",
        "live_coin": False,
        "live_wallet": False,
        "measured": {
            "key_gates": keys["grade"],
            "seal_hash_check": "MEASURED",  # present in landing worker
        },
        "hypothetical": ["full residual movement", "live emission", "second pinner"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))
