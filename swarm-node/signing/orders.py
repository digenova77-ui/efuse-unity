"""Standing orders as a hash chain with countersignatures — closing S7.

Tier-1 enactments required a countersignature (second, independent
coordinator or DCLM verifies reversibility, internality, ledgering, then
co-signs). Each order record carries: order hash, author key_id, reason,
reversal path, countersigner key_id, prev hash. An order without a valid
countersignature is not an order — it's a suggestion.

Record (one JSON per line, canonical):
  {"seq", "order_id", "order_sha256", "title", "author_key_id",
   "author_sig" (over the enactment descriptor),
   "reason", "reversal", "tier",
   "countersigner_key_id", "countersig" (over the record sans countersig),
   "prev_hash", "hash", "at_utc"}

Genesis: the five existing STANDING-ORDER-*.md files, hashed in, marked
"pre-regime genesis", countersigned at regime birth by the ceremony key.
"""
import base64
import hashlib
import json
import os
from datetime import datetime, timezone

from . import envelope
from .keys import fingerprint

GENESIS_MARK = "GENESIS"


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_chain(path):
    recs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    except OSError:
        pass
    return recs


def _hash_record(rec):
    body = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def enact(chain_path, order_path, title, tier, reason, reversal,
         author_seed):
    """Stage an order enactment (author signs). Returns the PENDING record
    (no countersignature yet — not an order until countersigned)."""
    recs = read_chain(chain_path)
    prev = recs[-1]["hash"] if recs else GENESIS_MARK
    descriptor = {"order_sha256": sha256_file(order_path),
                  "title": title, "tier": tier, "reason": reason,
                  "reversal": reversal}
    from . import backend
    pub = backend.publickey(author_seed)
    sig = envelope.sign_descriptor(descriptor, author_seed)
    rec = {"seq": len(recs) + 1,
           "order_id": os.path.basename(order_path),
           "order_sha256": descriptor["order_sha256"],
           "title": title, "tier": tier,
           "author_key_id": fingerprint(pub),
           "author_sig": sig,
           "reason": reason, "reversal": reversal,
           "countersigner_key_id": None, "countersig": None,
           "prev_hash": prev, "at_utc": utcnow(),
           "status": "PENDING-COUNTERSIGNATURE"}
    rec["hash"] = _hash_record(rec)
    return rec


def countersign(record, countersigner_seed, registry):
    """Co-sign a pending record. registry: {key_id: pubkey_bytes} of valid
    countersigners. Returns the sealed record (a real order now)."""
    from . import backend
    pub = backend.publickey(countersigner_seed)
    kid = fingerprint(pub)
    if kid not in registry:
        raise ValueError("countersigner %s not in registry" % kid)
    if record.get("status") != "PENDING-COUNTERSIGNATURE":
        raise ValueError("record is not pending countersignature")
    body = {k: v for k, v in record.items()
            if k not in ("countersigner_key_id", "countersig", "status", "hash")}
    sig = envelope.sign_descriptor(body, countersigner_seed)
    record["countersigner_key_id"] = kid
    record["countersig"] = sig
    record["status"] = "SEALED"
    record["hash"] = _hash_record(record)
    return record


def append(chain_path, record):
    d = os.path.dirname(chain_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(chain_path, "a", encoding="utf-8") as f:
        f.write(canonical(record) + "\n")


def verify_chain(chain_path, author_registry, counter_registry):
    """Full verification. Returns (ok, n, detail).

    author_registry / counter_registry: {key_id: pubkey_bytes}.
    Checks: hash links, author signatures, countersignatures, sealed status.
    Genesis records (pre-regime) are checked for the genesis mark and the
    ceremony countersignature only.
    """
    recs = read_chain(chain_path)
    prev = GENESIS_MARK
    for r in recs:
        if r.get("prev_hash") != prev:
            return False, r.get("seq"), "prev_hash break"
        if _hash_record(r) != r.get("hash"):
            return False, r.get("seq"), "record hash mismatch"
        if r.get("status") != "SEALED":
            return False, r.get("seq"), "record not sealed (no countersignature)"
        # Author signature over the enactment descriptor.
        adesc = {"order_sha256": r["order_sha256"], "title": r["title"],
                 "tier": r["tier"], "reason": r["reason"],
                 "reversal": r["reversal"]}
        apub = author_registry.get(r.get("author_key_id"))
        if apub is None:
            return False, r.get("seq"), "unknown author key"
        try:
            envelope.verify_descriptor(adesc, r["author_sig"], apub)
        except envelope.EnvelopeError as e:
            return False, r.get("seq"), "author sig invalid: %s" % e
        # Countersignature over the record sans countersignature fields.
        cpub = counter_registry.get(r.get("countersigner_key_id"))
        if cpub is None:
            return False, r.get("seq"), "unknown countersigner key"
        cbody = {k: v for k, v in r.items()
                 if k not in ("countersigner_key_id", "countersig",
                              "status", "hash")}
        try:
            envelope.verify_descriptor(cbody, r["countersig"], cpub)
        except envelope.EnvelopeError as e:
            return False, r.get("seq"), "countersig invalid: %s" % e
        prev = r["hash"]
    return True, len(recs), "order chain valid, %d sealed orders" % len(recs)


def seed_genesis(chain_path, order_files, ceremony_seed):
    """Hash the pre-regime standing orders in as genesis records,
    countersigned at regime birth by the ceremony key. Idempotent: does
    nothing if the chain file already exists."""
    if os.path.exists(chain_path):
        return 0
    n = 0
    for path in sorted(order_files):
        rec = enact(chain_path, path,
                    title=os.path.basename(path).replace(".md", "").replace("-", " "),
                    tier="pre-regime",
                    reason="pre-regime genesis: enacted before the signing regime; hashed in at regime birth",
                    reversal="n/a (genesis)",
                    author_seed=ceremony_seed)
        # The ceremony key both authors (as witness) and countersigns genesis.
        from .keys import fingerprint as _fp
        from . import backend as _b
        rec["genesis"] = True  # set BEFORE countersign so it's in the hash
        rec["hash"] = _hash_record(rec)
        reg = {_fp(_b.publickey(ceremony_seed)): _b.publickey(ceremony_seed)}
        rec = countersign(rec, ceremony_seed, reg)
        append(chain_path, rec)
        n += 1
    return n
