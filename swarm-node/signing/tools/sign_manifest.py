#!/usr/bin/env python3
"""Sign the version manifest with the OFFLINE root key.

Runs on David's OFFLINE machine (the same one that ran ceremony.py).
Prints the signature object as JSON — copy ONLY this object into the
online manifest's "signature" field. The key never leaves this machine.

Usage:
  python3 tools/sign_manifest.py --key dualiscapax-offline.key \
      --manifest /path/to/manifest.json [--bundle-version v1.2.0 --bundle-sha256 <hex>]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from signing import manifest as sm  # noqa: E402
from signing.keys import fingerprint  # noqa: E402
from signing import backend  # noqa: E402


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True, help="offline private key file")
    p.add_argument("--manifest", required=True)
    p.add_argument("--bundle-version", default=None)
    p.add_argument("--bundle-sha256", default=None)
    p.add_argument("--downgrade-auth", nargs=2, metavar=("VERSION", "REASON"),
                   default=None, help="also emit a signed downgrade authorization")
    ns = p.parse_args(argv)

    with open(ns.key, "rb") as f:
        seed = f.read().strip()
    if len(seed) != 32:
        print("key file does not hold a 32-byte seed", file=sys.stderr)
        return 1
    pub = backend.publickey(seed)
    print("signing as key %s" % fingerprint(pub), file=sys.stderr)

    with open(ns.manifest, "r", encoding="utf-8") as f:
        man = json.load(f)

    out = {"manifest_signature": sm.sign_manifest(man, seed)}
    if ns.bundle_version and ns.bundle_sha256:
        out["bundle_signature"] = sm.sign_bundle(ns.bundle_version,
                                                ns.bundle_sha256, seed)
        out["bundle_version"] = ns.bundle_version
    if ns.downgrade_auth:
        from signing import envelope
        ver, reason = ns.downgrade_auth
        auth = {"type": "downgrade-auth", "version": ver, "reason": reason,
                "issued_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")}
        out["downgrade_auth_envelope"] = envelope.seal(auth, seed)
    print(json.dumps(out, indent=2, sort_keys=True))
    print("Copy ONLY the signature objects into the online manifest. "
          "Never the key.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
