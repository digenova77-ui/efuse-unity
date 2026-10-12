"""Signed manifests and bundles — closing C1 (unsigned code enters lanes).

The manifest gains a top-level "signature" object: a detached signature
over the canonical descriptor:
  {"desired_version": ..., "versions": {ver: {"bundle_url","sha256","notes",
   "released_at"} for each version}, "downgrade_auths": [...]}

The pull-agent verifies this signature against the PINNED public key
(/etc/dualis/david-pubkey, written by bootstrap.sh at the one-hand
moment) BEFORE downloading anything. Unsigned or mis-signed manifest ->
refuse, attest the refusal, keep running the old version.

Bundles carry their own detached signature (defense in depth): the
manifest's versions[ver] entry may include "bundle_sig" over
{"version","sha256"}. The pull-agent verifies it after the sha256 check.

Downgrade protection (S1): desired_version must be NEWER than the running
version unless manifest["downgrade_auths"] carries a valid signed
{"type":"downgrade-auth","version","reason","issued_at"} from the offline
key. Every refusal is attested.
"""
from . import envelope


def manifest_descriptor(manifest):
    """The canonical signed content of a manifest."""
    versions = {}
    for ver, entry in (manifest.get("versions") or {}).items():
        versions[ver] = {k: entry.get(k) for k in
                         ("bundle_url", "sha256", "notes", "released_at")}
    return {"desired_version": manifest.get("desired_version"),
            "versions": versions,
            "downgrade_auths": manifest.get("downgrade_auths") or []}


def sign_manifest(manifest, seed):
    """Return a detached signature object for the manifest. David's offline
    machine runs this (see tools/sign_manifest.py)."""
    return envelope.sign_descriptor(manifest_descriptor(manifest), seed)


def verify_manifest(manifest, pubkey):
    """Verify manifest['signature'] against pubkey. Raises EnvelopeError."""
    sigobj = manifest.get("signature")
    if not sigobj:
        raise envelope.EnvelopeError("manifest is UNSIGNED — refused")
    return envelope.verify_descriptor(manifest_descriptor(manifest),
                                      sigobj, pubkey)


def bundle_descriptor(version, sha256):
    return {"version": version, "sha256": sha256}


def sign_bundle(version, sha256, seed):
    return envelope.sign_descriptor(bundle_descriptor(version, sha256), seed)


def verify_bundle(version, sha256, sigobj, pubkey):
    if not sigobj:
        raise envelope.EnvelopeError("bundle signature missing — refused")
    return envelope.verify_descriptor(bundle_descriptor(version, sha256),
                                      sigobj, pubkey)


def parse_version(v):
    """v1.1.0 -> (1,1,0). 'none'/'' -> (). Raises ValueError on garbage."""
    s = str(v).strip()
    if s.lower() in ("none", ""):
        return ()
    if s.startswith("v"):
        s = s[1:]
    parts = s.split(".")
    return tuple(int(p) for p in parts)


def is_newer(want, current):
    """True if want is strictly newer than current. 'none' < everything."""
    w, c = parse_version(want), parse_version(current)
    if not c:
        return True
    if not w:
        return False
    return w > c


def find_downgrade_auth(manifest, version, pubkey):
    """Return the valid downgrade auth for version, or None.

    A downgrade auth is {"type":"downgrade-auth","version","reason",
    "issued_at"} wrapped in a signed envelope by the offline key.
    Invalid/foreign envelopes are ignored (not errors) — the caller
    decides refusal.
    """
    for env in manifest.get("downgrade_auths") or []:
        try:
            payload = envelope.open_envelope(env, pubkey)
        except envelope.EnvelopeError:
            continue
        if (payload.get("type") == "downgrade-auth"
                and payload.get("version") == version):
            return payload
    return None
