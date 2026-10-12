#!/usr/bin/env python3
"""Build a signed go-live intent with the OFFLINE root key.

David reviews the intent, signs it on the OFFLINE machine, and hands the
resulting envelope to the operator (or pastes it). golive.py verifies the
envelope before CUTOVER — the static "david:go-live" string is dead.

Usage:
  python3 tools/sign_intent.py --key dualiscapax-offline.key \
      --lane EUROPE --version v1.2.0 --bundle-hash <sha256> [--ttl 3600]
Prints the sealed envelope JSON.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from signing import intent as gi  # noqa: E402
from signing.keys import fingerprint  # noqa: E402
from signing import backend  # noqa: E402


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True)
    p.add_argument("--lane", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--bundle-hash", required=True)
    p.add_argument("--ttl", type=int, default=3600)
    ns = p.parse_args(argv)

    with open(ns.key, "rb") as f:
        seed = f.read().strip()
    if len(seed) != 32:
        print("key file does not hold a 32-byte seed", file=sys.stderr)
        return 1
    print("signing as key %s" % fingerprint(backend.publickey(seed)),
          file=sys.stderr)
    payload = gi.build_intent(ns.lane, ns.version, ns.bundle_hash,
                              ttl_s=ns.ttl)
    env = gi.seal_intent(payload, seed)
    print(json.dumps(env, indent=2, sort_keys=True))
    print("Hand this envelope to the operator. It expires in %ds and "
          "can be used exactly once." % ns.ttl, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
