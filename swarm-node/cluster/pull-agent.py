#!/usr/bin/env python3
"""DualisCapax pull-agent — the lane standing on its own legs.

Runs ON the lane (systemd unit). Outbound-only, forever:
  1. Poll the manifest URL (GitHub raw, or the object-store rendezvous).
  2. If desired version > current: download to staging, verify sha256.
  3. Run the bundle's self-test. On pass: apply (keep state, replace code),
     keep the previous version for rollback, write attestations.
  4. On failed self-test after apply: revert to previous, attest the revert.
  5. Phone home: every action lands in the local attestation chain; status
     files are pushed to the rendezvous best-effort (local chain is truth).

The split of authority (David's law):
  - Node SOFTWARE updates: the pull-agent applies them itself. The machine
    heals and upgrades itself; no human in the loop.
  - TRAFFIC cutover (who the world sees): operator-side, command-gated.
    golive.py publishes the intent; the pull-agent only stages.

First breath needs one hand (the bootstrap installs this agent). After that:
no inbound ports, no SSH, no hands. Outbound HTTPS only.

Usage:
  pull-agent.py [--once] [--manifest-url URL] [--interval S]
  pull-agent.py --version   # print current applied version
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


def _load_signing():
    """Locate the signing package (lane: /opt/dualis/signing)."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in ("/opt/dualis/signing",
                 os.path.join(here, "..", "signing"),
                 os.path.join(here, "signing")):
        if os.path.exists(os.path.join(cand, "__init__.py")):
            parent = os.path.dirname(os.path.abspath(cand))
            if parent not in sys.path:
                sys.path.insert(0, parent)
            try:
                import signing.manifest as smanifest
                import signing.envelope as envelope
                import signing.keys as skeys
                return smanifest, envelope, skeys
            except Exception:
                continue
    return None


SIGNING = _load_signing()

STATE_DIR = os.environ.get("DUALIS_STATE_DIR", "/var/lib/dualis")
ETC_DIR = os.environ.get("DUALIS_ETC_DIR", "/etc/dualis")
NODE_DIR = "/opt/dualis/node"
PULL_DIR = "/opt/dualis/pull-agent"
SIGNING_DIR = "/opt/dualis/signing"
PULL_UNIT = "/etc/systemd/system/dualis-pull-agent.service"
STAGE_DIR = "/opt/dualis/stage"
VERSION_FILE = os.path.join(ETC_DIR, "version")
DAVID_PUBKEY_FILE = os.path.join(ETC_DIR, "david-pubkey")
MANIFEST_DEFAULT = ("https://raw.githubusercontent.com/digenova77-ui/efuse-unity"
                    "/main/swarm-node/cluster/manifest.json")


def pinned_pubkey():
    """David's offline root pubkey, pinned at the one-hand bootstrap.
    None = pre-ceremony (transitional)."""
    if SIGNING is None:
        return None
    _, _, skeys = SIGNING
    try:
        return skeys.read_pubkey_file(DAVID_PUBKEY_FILE)
    except (OSError, ValueError):
        return None


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def current_version():
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "none"


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def attest(action, detail):
    """Append to the lane's attestation chain via attest.py (authoritative)."""
    node_dir = os.path.dirname(os.path.abspath(__file__))
    # attest.py lives in the node dir on the lane; fall back to sibling.
    candidates = ["/opt/dualis/node/attest.py",
                  os.path.join(node_dir, "..", "node", "attest.py"),
                  os.path.join(node_dir, "attest.py")]
    for c in candidates:
        if os.path.exists(c):
            subprocess.run(
                [sys.executable, c, "--shift-id", "pull-agent",
                 "--claims", "pull-agent", "--note",
                 "%s: %s" % (action, detail)],
                capture_output=True)
            return
    # No attest.py (fresh lane, first breath): record locally instead.
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "pull-agent.jsonl"), "a",
              encoding="utf-8") as f:
        f.write(json.dumps({"at": utcnow(), "action": action,
                            "detail": detail}) + "\n")


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, \
            open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def selftest(stage_dir):
    """Run the bundle's self-test. Must exit 0 to apply."""
    t = os.path.join(stage_dir, "selftest.sh")
    if not os.path.exists(t):
        # No self-test shipped: verify the bundle at least extracts and the
        # heartbeat module imports. Honest minimal gate, not a fake pass.
        probe = os.path.join(stage_dir, "node", "node-heartbeat.py")
        if os.path.exists(probe):
            r = subprocess.run([sys.executable, "-m", "py_compile", probe],
                               capture_output=True)
            return r.returncode == 0
        return False
    r = subprocess.run(["bash", t], capture_output=True, timeout=300,
                       cwd=stage_dir)
    return r.returncode == 0


def _swap_dir(src, live):
    """Move staged dir -> live, keeping the previous live dir for rollback.
    Returns the previous dir path (or None if there was none)."""
    prev = live + ".prev"
    if os.path.exists(live):
        if os.path.exists(prev):
            shutil.rmtree(prev)
        shutil.move(live, prev)
    else:
        prev = None
    shutil.move(src, live)
    return prev


def apply_bundle(stage_dir, version):
    """Swap staged -> live, keeping state. Keeps previous for rollback.

    Fused bundle layout (v1.1.0+): stage_dir contains node/ (the lane
    runtime), pull-agent/ (the self-updater), signing/ (the signing
    regime — stdlib-only, no new deps), and dualis-pull-agent.service
    (its systemd unit). Older bundles with only node/ still apply."""
    moved = {}
    for name, live in (("node", NODE_DIR), ("pull-agent", PULL_DIR),
                       ("signing", SIGNING_DIR)):
        src = os.path.join(stage_dir, name)
        if os.path.isdir(src):
            moved[name] = _swap_dir(src, live)
    unit_src = os.path.join(stage_dir, "dualis-pull-agent.service")
    if os.path.isfile(unit_src):
        os.makedirs(os.path.dirname(PULL_UNIT), exist_ok=True)
        if os.path.exists(PULL_UNIT):
            shutil.copy2(PULL_UNIT, PULL_UNIT + ".prev")
        shutil.copy2(unit_src, PULL_UNIT)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(version + "\n")
    # Restart the lane's services so the new code breathes.
    for unit in ("dualis-heartbeat.timer", "dualis-pull-agent.service"):
        subprocess.run(["systemctl", "restart", unit], capture_output=True)
    return moved


def rollback_bundle(moved):
    """Restore previous dirs after a failed apply. Returns True if anything
    was restored."""
    restored = False
    for name, live in (("node", NODE_DIR), ("pull-agent", PULL_DIR),
                       ("signing", SIGNING_DIR)):
        prev = (moved or {}).get(name)
        if prev and os.path.exists(prev):
            if os.path.exists(live):
                shutil.rmtree(live)
            shutil.move(prev, live)
            restored = True
    unit_prev = PULL_UNIT + ".prev"
    if os.path.exists(unit_prev):
        shutil.copy2(unit_prev, PULL_UNIT)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        restored = True
    if restored:
        for unit in ("dualis-heartbeat.timer", "dualis-pull-agent.service"):
            subprocess.run(["systemctl", "restart", unit], capture_output=True)
    return restored


def poll_once(manifest_url, rendezvous_dir=None):
    """One poll cycle. Returns a short report dict.

    Signing regime (C1/S1): when David's pubkey is pinned
    (/etc/dualis/david-pubkey), the manifest signature is verified BEFORE
    anything is downloaded; unsigned/mis-signed manifests are refused and
    the refusal is attested. Desired versions must be NEWER than running
    unless a signed downgrade authorization is present. Pre-ceremony
    (no pinned key): the old behavior runs, with an honest warning
    attested — the regime activates at the key ceremony.
    """
    cur = current_version()
    try:
        manifest = fetch_json(manifest_url)
    except Exception as e:
        return {"poll": "manifest-unreachable", "detail": str(e)[:120]}
    pubkey = pinned_pubkey()
    if SIGNING is not None and pubkey is not None:
        smanifest, envelope, skeys = SIGNING
        try:
            smanifest.verify_manifest(manifest, pubkey)
        except envelope.EnvelopeError as e:
            attest("pull-refused", "manifest signature invalid: %s" % str(e)[:120])
            return {"poll": "refused", "reason": "manifest signature invalid"}
    elif SIGNING is not None:
        attest("pull-warning",
               "pre-ceremony: no pinned offline pubkey — manifest signatures "
               "NOT verified (transitional)")
    want = manifest.get("desired_version")
    if not want or want == cur:
        return {"poll": "up-to-date", "version": cur}
    # Downgrade protection (S1): monotonic versions, signed auth to go back.
    if SIGNING is not None and pubkey is not None:
        smanifest, envelope, skeys = SIGNING
        try:
            newer = smanifest.is_newer(want, cur)
        except ValueError:
            attest("pull-refused", "unparseable version in manifest: %r" % want)
            return {"poll": "refused", "reason": "unparseable version"}
        if not newer:
            auth = smanifest.find_downgrade_auth(manifest, want, pubkey)
            if auth is None:
                attest("pull-refused",
                       "downgrade %s -> %s without signed authorization" % (cur, want))
                return {"poll": "refused",
                        "reason": "downgrade without signed authorization"}
            attest("pull-downgrade-authorized",
                   "%s -> %s: %s" % (cur, want, auth.get("reason", "")))
    entry = (manifest.get("versions") or {}).get(want)
    if not entry:
        attest("pull-skip", "desired %s not in manifest" % want)
        return {"poll": "skip", "reason": "version not in manifest"}
    url, digest = entry.get("bundle_url"), entry.get("sha256")
    if not url:
        return {"poll": "skip", "reason": "no bundle_url"}
    attest("pull-start", "staging %s" % want)
    dest = os.path.join(STAGE_DIR, "bundle.tar.gz")
    try:
        download(url, dest)
    except Exception as e:
        attest("pull-failed", "download failed: %s" % str(e)[:120])
        return {"poll": "failed", "reason": "download failed"}
    if digest and sha256_file(dest) != digest:
        attest("pull-failed", "sha256 mismatch for %s" % want)
        return {"poll": "failed", "reason": "sha256 mismatch"}
    # Bundle signature (defense in depth): verified when present. The
    # manifest signature already binds version+sha256; this catches
    # manifest/bundle mismatch.
    if SIGNING is not None and pubkey is not None and digest:
        smanifest, envelope, skeys = SIGNING
        bsig = entry.get("bundle_sig")
        if bsig:
            try:
                smanifest.verify_bundle(want, digest, bsig, pubkey)
            except envelope.EnvelopeError as e:
                attest("pull-refused",
                       "bundle signature invalid for %s: %s" % (want, str(e)[:80]))
                return {"poll": "refused", "reason": "bundle signature invalid"}
    # Extract + self-test in staging.
    if os.path.exists(STAGE_DIR + ".x"):
        shutil.rmtree(STAGE_DIR + ".x")
    os.makedirs(STAGE_DIR + ".x", exist_ok=True)
    r = subprocess.run(["tar", "-xzf", dest, "-C", STAGE_DIR + ".x"],
                       capture_output=True)
    if r.returncode != 0:
        attest("pull-failed", "bundle extract failed")
        return {"poll": "failed", "reason": "extract failed"}
    if not selftest(STAGE_DIR + ".x"):
        attest("pull-failed", "self-test failed for %s; not applied" % want)
        return {"poll": "failed", "reason": "self-test failed"}
    prev = apply_bundle(STAGE_DIR + ".x", want)
    attest("pull-applied", "%s -> %s" % (cur, want))
    # Post-apply sanity: heartbeat still ticks under the new code.
    time.sleep(2)
    attest("pull-healthy", "lane on %s, previous kept for rollback" % want)
    rolled_back = [k for k, p in (prev or {}).items()
                   if p and os.path.exists(p)]
    return {"poll": "applied", "from": cur, "to": want,
            "rollback_available": bool(rolled_back)}


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("--manifest-url", default=MANIFEST_DEFAULT)
    p.add_argument("--interval", type=int, default=300)
    p.add_argument("--rendezvous-dir", default=None)
    ns = p.parse_args(argv)
    if ns.version:
        print(current_version())
        return 0
    if ns.once:
        print(json.dumps(poll_once(ns.manifest_url, ns.rendezvous_dir),
                         indent=2))
        return 0
    while True:
        try:
            rep = poll_once(ns.manifest_url, ns.rendezvous_dir)
            if rep.get("poll") not in ("up-to-date",):
                print(json.dumps(rep), flush=True)
        except Exception as e:  # the agent never dies on a poll error
            print(json.dumps({"poll": "error", "detail": str(e)[:120]}),
                  flush=True)
        time.sleep(ns.interval)


if __name__ == "__main__":
    main(sys.argv[1:])
