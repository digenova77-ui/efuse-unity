#!/usr/bin/env python3
"""THE KEY CEREMONY — David's hand, offline machine, once.

This script generates the OFFLINE ROOT SIGNING KEY: the instrument that
closes C1 (unsigned code) and C2 (unsigned history). It must run on an
OFFLINE machine (no network — air-gapped, or at minimum wifi off and
cable unplugged). The private key it creates must NEVER:
  - leave this machine except into David's secure store / hardware key,
  - enter git, chat, email, a lane, or any online system.

What the ceremony produces:
  1. dualiscapax-offline.key  — the private key (0600). YOU secure this.
  2. The public key (armored) + fingerprint — printed. THIS is what gets
     published: pasted into bootstrap.sh's DAVID_PUBKEY, the deploy doc,
     and the allowlist config. Public keys are public; no secrecy needed.
  3. The exact lines to paste, and the rotation procedure.

After the ceremony:
  - Run tools/sign_manifest.py on this same offline machine to sign the
    manifest (and bundles). Copy ONLY the signature objects to the online
    world — never the key.
  - Key rotation (if ever needed): the OLD key signs the NEW pubkey in a
    rotation record; lanes accept rotation only with the old key's
    signature. The old key is then retired, never reused.

Usage: python3 ceremony.py   (on the OFFLINE machine)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend import generate, backend_name  # noqa: E402
from keys import fingerprint, armor_pubkey, write_secret_file  # noqa: E402


def warn_offline():
    print("=" * 70)
    print("  THE KEY CEREMONY — offline root signing key")
    print("=" * 70)
    print()
    print("  Before continuing, confirm:")
    print("    [ ] This machine is OFFLINE (wifi off, cable unplugged).")
    print("    [ ] Nobody is watching the screen.")
    print("    [ ] You have a secure store ready for the private key")
    print("        (hardware key, encrypted USB, or the secure vault).")
    print()
    ans = input("  Type YES (all caps) to confirm, anything else to abort: ")
    if ans.strip() != "YES":
        print("  Aborted. Nothing was generated.")
        return 1
    return 0


def main():
    if warn_offline():
        return 1
    here = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(os.getcwd(), "dualiscapax-offline.key")

    if os.path.exists(key_path):
        print("  A key already exists at %s" % key_path)
        print("  The ceremony runs ONCE. To rotate, use the rotation")
        print("  procedure (old key signs new pubkey) — never overwrite.")
        return 1

    print()
    print("  Generating Ed25519 keypair (backend: %s)..." % backend_name())
    seed, pub = generate()
    write_secret_file(key_path, seed, 0o600)
    fp = fingerprint(pub)

    print()
    print("  PRIVATE KEY written to: %s  (mode 0600)" % key_path)
    print("  >>> Move this file to your secure store NOW. <<<")
    print("  It must never enter git, chat, email, or a lane.")
    print()
    print("  PUBLIC KEY (publish this freely):")
    print()
    print(armor_pubkey(pub))
    print("  Fingerprint: %s" % fp)
    print()
    print("  PASTE INTO bootstrap.sh (replacing the placeholder):")
    print()
    print('  DAVID_PUBKEY="%s"' % pub.hex())
    print()
    print("  EXPECTED FINGERPRINT (for the deploy doc, out-of-band):")
    print("    %s" % fp)
    print("  At the one-hand paste moment, the bootstrap prints the signer's")
    print("  fingerprint — compare it to this. One glance, then paste.")
    print()
    print("  NEXT: on this same offline machine, sign the manifest:")
    print("    python3 tools/sign_manifest.py --key %s \\" % key_path)
    print("        --manifest swarm-node/cluster/manifest.json")
    print("  Copy ONLY the printed signature object online. Never the key.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
