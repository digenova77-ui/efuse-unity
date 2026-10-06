"""
DCLM DATA SERVING LAYER — telemetrics and data ingestion for the unity world.

Testnet only. Nothing invented, nothing presented as live that isn't.

Sources:
  1. Vendored Grok registries (~/workspace/unity-world/data/) — recovered
     from /tmp/grok-drive-extract/public/registry/ (ephemeral; vendored copy
     is the durable record). Provenance: REPORTED.
  2. ~/workspace/keys/PRICES.md — 51 decisions with labeled figures.
  3. ~/MEMORY.md — REAL Drive-sourced RTE figures (Ontario education,
     QHC/KHSC healthcare pilot).
  4. Six live feeds — architecture only; every feed is PENDING until a real
     reading + hash exists. Never presented as live.
  5. Sealed factory verdicts from ~/workspace (corporate helpers seals,
     encyclopedia wave adjudications) + the Trinity verdict packet
     (data/trinity-verdict.json).

Figure labels: the full figure-level label set is
    REAL / REPORTED / MODELED / DERIVED / UNKNOWN
("REPORTED" covers PRICES.md's REPORTED-via-secondary/UNAUDITED variants;
"DERIVED" covers PRICES.md's MODELED-DERIVED arithmetic; REAL is the
PRICES.md/MEMORY.md convention for Drive-sourced verified figures.)
The subset crossing into compute.py's WorldState (registry_digest,
feed_status entries) uses compute.py's exact enum:
    REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN
UNKNOWN is never PASS.
"""

import hashlib
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "data"))
PRICES_MD = os.path.normpath(
    os.path.join(_HERE, "..", "..", "keys", "PRICES.md")
)
MEMORY_MD = os.path.normpath(
    os.path.join(os.path.expanduser("~"), "MEMORY.md")
)
SEAL_DIR = os.path.normpath(
    os.path.join(
        os.path.expanduser("~"),
        "workspace", "goals", "rte-wave-program-the-next-meaningful-things",
        "hidden_files",
    )
)

# compute.py's enum — the labels that enter the signed WorldState.
from compute import (  # noqa: E402
    PROVENANCE_LABELS as _COMPUTE_LABELS,
    compute_world_state,
)
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    PurificationRefused,
    purify_input,
    purify_output,
)

# Figure-level labels (superset used for served figures; REAL is the
# PRICES.md/MEMORY.md convention for Drive-sourced verified figures).
FIGURE_LABELS = frozenset(
    {"REAL", "VERIFIED", "REPORTED", "MODELED", "DERIVED", "UNKNOWN"}
)
assert _COMPUTE_LABELS <= FIGURE_LABELS, "compute.py enum changed"
PROVENANCE_LABELS = FIGURE_LABELS


# ---------------------------------------------------------------------------
# registry loading with schema sanity checks
# ---------------------------------------------------------------------------
# name -> (kind, required_top_keys, per-item required keys, min_count)
_REGISTRY_SCHEMA = {
    "countries": ("dict", {"countries"}, {"a3", "name", "continent"}, 1),
    "cities": ("dict", {"cities"}, {"name", "lat", "lon"}, 1),
    "chambers": ("list", set(), {"key", "title", "status"}, 1),
    "jurisdictions": ("list", set(), {"name", "iso"}, 1),
    "doctrine": ("dict", {"definition", "hook", "manifesto"}, set(), 0),
    "rtes": ("list", set(), {"key", "name", "status"}, 1),
    "canada": ("list", set(), {"key", "name"}, 1),
    "sectors": ("list", set(), {"key", "name"}, 1),
    "pharmacology": ("dict", {"key", "name"}, set(), 0),
    "trinity-verdict": ("dict", {"packet", "packetSha256", "decisions"},
                        {"id", "disposition"}, 1),
}


def load_registry(name):
    """Load and validate a vendored registry dataset.

    Applies schema sanity checks (shape, required keys, item counts) and
    raises honestly on corrupt or missing data — no silent UNKNOWN fill.
    Returns the parsed JSON object.
    """
    if name not in _REGISTRY_SCHEMA:
        raise ValueError(f"unknown registry dataset: {name!r}")
    kind, top_keys, item_keys, min_count = _REGISTRY_SCHEMA[name]
    path = os.path.join(DATA_DIR, name + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"registry dataset missing: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"registry dataset {name!r} is corrupt: {exc}")

    if kind == "dict":
        if not isinstance(data, dict):
            raise ValueError(f"registry {name!r}: expected dict, got {type(data).__name__}")
        missing = top_keys - set(data.keys())
        if missing:
            raise ValueError(f"registry {name!r}: missing keys {sorted(missing)}")
        items = [data[k] for k in top_keys if isinstance(data[k], list)]
    else:
        if not isinstance(data, list):
            raise ValueError(f"registry {name!r}: expected list, got {type(data).__name__}")
        items = data

    # item-key checks on the first list found (or the list itself)
    checked = 0
    for seq in (items if kind == "list" else items):
        seq_list = seq if isinstance(seq, list) else [seq]
        for entry in seq_list:
            if isinstance(entry, dict) and item_keys:
                missing = item_keys - set(entry.keys())
                if missing:
                    raise ValueError(
                        f"registry {name!r}: item missing keys {sorted(missing)}"
                    )
                checked += 1
    if kind == "list" and len(data) < min_count:
        raise ValueError(f"registry {name!r}: only {len(data)} items, need >= {min_count}")
    if kind == "dict" and min_count and checked < min_count:
        raise ValueError(f"registry {name!r}: only {checked} items, need >= {min_count}")
    return data


def registry_summary():
    """Per-dataset counts + sha256 for the vendored set."""
    summary = {}
    for name in sorted(_REGISTRY_SCHEMA):
        path = os.path.join(DATA_DIR, name + ".json")
        if not os.path.exists(path):
            summary[name] = {"status": "MISSING", "provenance": "UNKNOWN"}
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        data = load_registry(name)
        kind, top_keys, _, _ = _REGISTRY_SCHEMA[name]
        if kind == "dict":
            counts = {
                k: (len(v) if isinstance(v, list) else 1)
                for k, v in data.items() if k in top_keys
            }
        else:
            counts = {"items": len(data)}
        summary[name] = {
            "counts": counts,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "provenance": "REPORTED",  # recovered artifacts, reported as-found
        }
    return summary


# ---------------------------------------------------------------------------
# pricing index (PRICES.md)
# ---------------------------------------------------------------------------
# PRICES.md label variants -> canonical figure labels.
_LABEL_MAP = {
    "REAL": "REAL",
    "REPORTED": "REPORTED",
    "REPORTED-via-secondary": "REPORTED",
    "UNAUDITED": "REPORTED",
    "MODELED": "MODELED",
    "MODELED-DERIVED": "DERIVED",
    "UNKNOWN": "UNKNOWN",
    "N/A": "UNKNOWN",
}

# A dollar/figure token followed by its own parenthesized label, e.g.
#   FY2024 net revenues $56,334M (REPORTED-via-secondary)
_FIGURE_RE = re.compile(
    r"(?P<context>[^;|]*?\$[\d,.]+\s*(?:[BMKT]|/visit|/standard stay|bps)?"
    r"(?:\s*/\s*\w+)?\s*\([^)]*\))"
    r"|(?P<plain>[\d,.]+\s*(?:school boards|students FTE|schools|beds|ED visits))",
)
_FIGURE_LABEL_RE = re.compile(
    r"^(?P<text>.*?)\s*\((?P<label>[A-Za-z\-/ ]+)\)$"
)


def _canonical_label(raw):
    raw = (raw or "").strip()
    return _LABEL_MAP.get(raw, "UNKNOWN")


def _extract_figures(cost_text):
    """Split a cost-on-record cell into labeled figure rows.

    Never invents: text that carries no parenthesized label is emitted
    with label UNKNOWN and its raw context preserved.
    """
    figures = []
    for chunk in re.split(r";\s*", cost_text):
        chunk = chunk.strip().rstrip(".")
        if not chunk:
            continue
        m = _FIGURE_LABEL_RE.match(chunk)
        if m and any(tok in chunk for tok in ("$", "%", "M", "B", "T", "bps")):
            text, raw_label = m.group("text").strip(), m.group("label").strip()
            label = _canonical_label(raw_label)
            figures.append({
                "figure": text,
                "label": label,
                "raw_label": raw_label,
                "context": chunk,
            })
        else:
            figures.append({
                "figure": chunk,
                "label": "UNKNOWN",
                "raw_label": None,
                "context": chunk,
            })
    return figures


def _parse_markdown_table(md_text, start_marker):
    """Parse the first markdown table at/after start_marker into row dicts."""
    lines = md_text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if start_marker in l)
    except StopIteration:
        return []
    rows, header = [], None
    in_table = False
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not in_table:
                header = cells
                in_table = True
                continue
            if set("".join(cells)) <= set("-: |"):
                continue
            if header and len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
        elif in_table:
            break
    return rows


def pricing_index(prices_path=PRICES_MD):
    """Parse PRICES.md's 51 decisions into structured rows.

    Returns {"rows": [...], "parsed": n, "expected": 51, "unknown_rows": m,
              "provenance": "REPORTED"}.
    Rows that resist clean parsing are kept with label UNKNOWN — never
    dropped, never invented.
    """
    rows = []
    expected = 51
    if not os.path.exists(prices_path):
        return {
            "rows": [], "parsed": 0, "expected": expected,
            "unknown_rows": 0, "provenance": "UNKNOWN",
            "note": f"PRICES.md not found at {prices_path}",
        }
    with open(prices_path, encoding="utf-8") as fh:
        md = fh.read()

    # 1. Factory verdicts table (33 rows).
    for r in _parse_markdown_table(md, "### 1. Factory verdicts"):
        try:
            rows.append({
                "class": "factory-verdict",
                "index": r.get("#"),
                "company": r.get("Company"),
                "decision": r.get("Decision (#1 vector)"),
                "figures": _extract_figures(r.get("Cost on record", "")),
                "claim_hash": (r.get("Claim hash") or "").strip("`").rstrip("…"),
                "provenance": "REPORTED",
            })
        except Exception as exc:  # keep the row, honestly flagged
            rows.append({
                "class": "factory-verdict", "parse_error": str(exc),
                "raw": r, "provenance": "UNKNOWN",
            })

    # 2. RTE decisions (2 rows, prose form — structured from the section text).
    rte_section = md.split("### 2. RTE decisions")[1].split("### 3.")[0] \
        if "### 2. RTE decisions" in md else ""
    for key, title in (("RTE-EDU", "Ontario education residual friction"),
                       ("RTE-HEALTH", "QHC vs KHSC pilot")):
        block = ""
        for para in rte_section.split("\n\n"):
            if key in para:
                block = para
                break
        rows.append({
            "class": "rte-decision",
            "index": key,
            "company": title,
            "decision": block.split("\n")[0].replace("**", "").strip() if block else "",
            "figures": _extract_figures(" ".join(
                ln.strip("- ").strip() for ln in block.splitlines()[1:]
            )) if block else [],
            "claim_hash": None,
            "provenance": "REAL" if block else "UNKNOWN",
        })

    # 3. Claims register table (16 rows) — the verdict IS the price.
    for r in _parse_markdown_table(md, "### 3. Claims register"):
        rows.append({
            "class": "claims-adjudication",
            "index": r.get("Claim"),
            "company": r.get("Title"),
            "decision": r.get("Adjudication"),
            "figures": [{
                "figure": "N/A — a judgment has no dollar cost",
                "label": "UNKNOWN",
                "raw_label": "N/A",
                "context": r.get("$ cost", ""),
            }],
            "claim_hash": None,
            "provenance": "REPORTED",
        })

    unknown_rows = sum(
        1 for r in rows
        if r.get("parse_error") or r.get("provenance") == "UNKNOWN"
    )
    return {
        "rows": rows,
        "parsed": len(rows),
        "expected": expected,
        "unknown_rows": unknown_rows,
        "provenance": "REPORTED",
    }


# ---------------------------------------------------------------------------
# RTE real telemetry (MEMORY.md — Drive-sourced REAL figures)
# ---------------------------------------------------------------------------
def rte_telemetry():
    """The REAL-labeled RTE figures, exactly as banked in MEMORY.md.

    Every metric: (metric, value, unit, label=REAL, source note).
    """
    src = "MEMORY.md — Drive-sourced figures (Sept 2026); Google Docs/Drive connected Sept 27, 2026"
    edu = [
        ("combined_operating_envelope", "$32.02B", "USD", "REAL",
         "Ontario education — 72 school boards", src),
        ("recoverable_nonclassroom_friction", "$1,273.5M/yr", "USD/yr", "REAL",
         "Ontario education — recoverable non-classroom friction", src),
        ("five_year_cumulative", "$6.08B", "USD", "REAL",
         "Ontario education — 5-year cumulative", src),
        ("school_boards", "72", "count", "REAL", "Ontario education scale", src),
        ("students_fte", "2,071,550", "count", "REAL", "Ontario education scale", src),
        ("schools", "4,684", "count", "REAL", "Ontario education scale", src),
        ("year1_board_retention", "81%", "percent", "REAL",
         "Ontario education — terms, Zero-OpEx", src),
        ("year3_board_retention", "100%", "percent", "REAL",
         "Ontario education — terms, Zero-OpEx", src),
    ]
    health = [
        ("qhc_revenue", "$348.5M", "USD", "REAL",
         "Quinte Health — revenue (pilot-mode modeled analysis; input figures REAL disclosures)", src),
        ("qhc_beds", "320", "count", "REAL", "Quinte Health — beds", src),
        ("qhc_ed_visits", "144,200", "count", "REAL",
         "Quinte Health — ED visits (corporation-wide)", src),
        ("qhc_cost_per_ed_visit", "$215/visit", "USD/visit", "REAL",
         "Quinte Health — cost per ED visit", src),
        ("qhc_cost_per_standard_stay", "$5,940/standard stay", "USD/stay", "REAL",
         "Quinte Health — cost per standard stay", src),
        ("khsc_revenue", "$812.4M", "USD", "REAL",
         "KHSC — revenue (pilot-mode modeled analysis; input figures REAL disclosures)", src),
        ("khsc_beds", "575", "count", "REAL", "KHSC — beds", src),
        ("khsc_ed_visits", "112,500", "count", "REAL", "KHSC — ED visits", src),
        ("khsc_kgh_cost_per_ed_visit", "$340/visit", "USD/visit", "REAL",
         "KHSC (KGH) — cost per ED visit", src),
        ("khsc_cost_per_standard_stay", "$6,820/standard stay", "USD/stay", "REAL",
         "KHSC — cost per standard stay", src),
        ("both_over_100pct_occupancy", "over 100%", "percent", "REAL",
         "QHC and KHSC — occupancy", src),
    ]
    rows = [
        {"metric": m, "value": v, "unit": u, "label": lbl,
         "context": ctx, "source": s}
        for (m, v, u, lbl, ctx, s) in (edu + health)
    ]
    return {"rows": rows, "count": len(rows), "provenance": "REAL"}


# ---------------------------------------------------------------------------
# live feeds — architecture only; PENDING until a real reading + hash exists
# ---------------------------------------------------------------------------
_FEED_NAMES = [
    ("air", "Air quality"),
    ("moira_river", "Moira River"),
    ("earthquakes", "Earthquakes"),
    ("iss", "ISS position"),
    ("kp_index", "Kp index"),
    ("britain_grid_carbon", "Britain grid carbon intensity"),
]


# ---------------------------------------------------------------------------
# feed sources — every feed source is Unity-bound
#
# A feed is not an anonymous pipe: each feed's source (the operator or
# instrument that reports its readings) is bound to a Unity identity.
# register_feed_source() binds it; ingest_reading() refuses readings
# from unbound or mismatched sources. No anonymous feeds, anywhere.
# ---------------------------------------------------------------------------

_FEED_SOURCES = {}  # feed name -> Unity-bound source identity

_FEED_SOURCE_PREFIX = "unity:testnet:"


def register_feed_source(feed, source_identity):
    """Bind a feed's source to a Unity identity. The identity must be
    "unity:testnet:..." — anything else raises ValueError and binds
    nothing. Re-binding overwrites (the binding is operational, not a
    token — audit history lives in the ingest receipts)."""
    known = [name for name, _ in _FEED_NAMES]
    if feed not in known:
        raise ValueError(f"unknown feed: {feed!r}")
    if not (isinstance(source_identity, str)
            and source_identity.startswith(_FEED_SOURCE_PREFIX)
            and len(source_identity) > len(_FEED_SOURCE_PREFIX)):
        raise ValueError(
            f"feed source identity must be Unity-bound "
            f"({_FEED_SOURCE_PREFIX!r} + suffix); got {source_identity!r}. "
            f"Testnet only.")
    _FEED_SOURCES[feed] = source_identity
    return source_identity


def feed_source(feed):
    """The Unity-bound source identity for a feed, or None if unbound."""
    return _FEED_SOURCES.get(feed)


def clear_feed_sources():
    """Release all feed-source bindings (tests / honest shutdown)."""
    _FEED_SOURCES.clear()


def feed_registry():
    """The six feeds. Every feed is PENDING with null reading and null
    hash. A feed flips to LIVE only via ingest_reading() with a real
    reading AND a real hash — from its Unity-bound source."""
    return {
        name: {
            "name": name,
            "display": display,
            "status": "PENDING",
            "last_reading": None,
            "reading_hash": None,
            "provenance": "UNKNOWN",
        }
        for name, display in _FEED_NAMES
    }


def ingest_reading(feed, reading, reading_hash, *, source_identity=None):
    """Record a real reading. Returns the feed entry.

    LIVE requires BOTH a real reading and a real hash. A feed with only
    one of the two stays PENDING. Empty/None values never flip.

    IDENTITY: every feed source is Unity-bound. The reading is accepted
    only from the feed's bound source identity — passed explicitly as
    source_identity, or previously bound via register_feed_source().
    No bound source (and none passed) -> PurificationRefused: no
    anonymous feeds. A passed identity that does not match the bound
    source -> PurificationRefused (SOURCE_MISMATCH): a feed's readings
    come from its source, not from whoever asks.
    """
    # Structural first: unknown feeds are a caller error, not an
    # identity failure.
    entries = feed_registry()
    if feed not in entries:
        raise ValueError(f"unknown feed: {feed!r}")
    # PURIFY ON ENTRY: resolve and bind the source identity first.
    bound = _FEED_SOURCES.get(feed)
    if source_identity is not None:
        if not (isinstance(source_identity, str)
                and source_identity.startswith(_FEED_SOURCE_PREFIX)
                and len(source_identity) > len(_FEED_SOURCE_PREFIX)):
            raise PurificationRefused(
                f"[NOT_TESTNET_IDENTITY] at data.ingest_reading: feed "
                f"source identity {source_identity!r} is not Unity-bound "
                f"testnet. Testnet only.")
        if bound is not None and source_identity != bound:
            raise PurificationRefused(
                f"[SOURCE_MISMATCH] at data.ingest_reading: feed {feed!r} "
                f"is bound to source {bound!r}; reading presented by "
                f"{source_identity!r} refused. A feed's readings come "
                f"from its source.")
        source = source_identity
    else:
        source = bound
    purify_input(
        {"identity": source, "action": "INGEST_READING", "feed": feed,
         "claims": [{"claim": "feed-reading", "provenance": "REPORTED",
                     "feed": feed,
                     "reading_hash": (reading_hash
                                      if isinstance(reading_hash, str)
                                      else None)}]},
        context={"path": "data.ingest_reading"},
    )
    entry = entries[feed]
    has_both = bool(reading) and bool(reading_hash)
    if has_both:
        entry["last_reading"] = reading
        entry["reading_hash"] = reading_hash
        entry["status"] = "LIVE"
        entry["provenance"] = "REPORTED"  # the feed reported it; DCLM did not measure it
        entry["source_identity"] = source  # WHO reported it: Unity-bound
    # PURIFY ON EXIT: the entry leaves labeled — and when LIVE,
    # identity-bound to its source.
    return purify_output(
        entry,
        context={"path": "data.ingest_reading",
                 "require_identity": has_both},
    )


# ---------------------------------------------------------------------------
# factory verdicts — sealed verdicts wired in as the Atlas view's verdict feed
_VERDICT_RE = re.compile(r"\*\*Verdict:\*\*\s*`([^`]+)`\s*[—-]\s*([A-Z\- ]+)")
_CLAIM_RE = re.compile(r"\*\*Claim:\*\*\s*`([0-9a-f]{16,64})")
_SEALED_RE = re.compile(r"\*\*Sealed:\*\*\s*([^\n]+)")


def _parse_seal_file(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    title = text.splitlines()[0].lstrip("# ").strip()
    verdict_m = _VERDICT_RE.search(text)
    claim_m = _CLAIM_RE.search(text)
    sealed_m = _SEALED_RE.search(text)
    seal_line = next(
        (ln for ln in text.splitlines() if ln.startswith("**Seal:**")), ""
    )
    return {
        "seal": title,
        "verdict": verdict_m.group(1) if verdict_m else "UNKNOWN",
        "disposition": (verdict_m.group(2).strip()
                        if verdict_m else "UNKNOWN"),
        "sealed": sealed_m.group(1).strip() if sealed_m else "UNKNOWN",
        "claim_hash": claim_m.group(1) if claim_m else None,
        "seal_note": seal_line.replace("**Seal:**", "").strip(),
        "seal_ref": os.path.basename(path),
        "status": "SEALED",
        "provenance": "VERIFIED",  # SEALED -> VERIFIED, with seal reference
    }


def factory_verdicts(seal_dir=SEAL_DIR):
    """Sealed verdicts found in the workspace.

    Each: SEALED -> VERIFIED with a seal reference (file or packet sha).
    Covers: corporate-helpers seal records, encyclopedia wave adjudications,
    and the Trinity verdict packet (data/trinity-verdict.json).
    """
    verdicts = []

    # Trinity verdict packet — the real packet, vendored with the registries.
    try:
        packet = load_registry("trinity-verdict")
        packet_sha = packet.get("packetSha256")
        for d in packet.get("decisions", []):
            verdicts.append({
                "seal": packet.get("packet"),
                "verdict": d.get("id"),
                "disposition": d.get("disposition"),
                "sealed": packet.get("decidedAt"),
                "claim_hash": None,
                "seal_note": "Trinity verdict packet (DCLM/Iris/Twain2 votes)",
                "seal_ref": f"trinity-verdict.json sha256:{packet_sha}",
                "status": "SEALED",
                "provenance": "VERIFIED",
            })
    except (FileNotFoundError, ValueError):
        pass

    # Seal records on disk: any *.md seal record except superseded attempts,
    # plus encyclopedia wave verdicts and adjudication records (sealed records
    # that carry no "seal" in the name).
    if os.path.isdir(seal_dir):
        for fname in sorted(os.listdir(seal_dir)):
            if not fname.endswith(".md"):
                continue
            is_seal = "seal" in fname.lower() and not fname.startswith("attempt1-")
            is_enc_verdict = (fname.startswith("ed-enc-")
                              and "-verdict-" in fname)
            is_adjudication = fname.startswith("ed-adjudication-")
            if is_seal:
                try:
                    verdicts.append(_parse_seal_file(os.path.join(seal_dir, fname)))
                except Exception:
                    verdicts.append({
                        "seal": fname, "verdict": "UNKNOWN",
                        "disposition": "UNKNOWN", "sealed": "UNKNOWN",
                        "claim_hash": None, "seal_note": "unparseable seal file",
                        "seal_ref": fname, "status": "UNSEALED",
                        "provenance": "UNKNOWN",
                    })
            elif is_enc_verdict:
                try:
                    verdicts.append(_parse_seal_file(os.path.join(seal_dir, fname)))
                except Exception:
                    pass
            elif is_adjudication:
                with open(os.path.join(seal_dir, fname), encoding="utf-8") as fh:
                    text = fh.read()
                verdicts.append({
                    "seal": fname.replace(".md", ""),
                    "verdict": fname,
                    "disposition": "ADJUDICATED",
                    "sealed": "UNKNOWN",
                    "claim_hash": None,
                    "seal_note": text.splitlines()[0].lstrip("# ").strip()[:160],
                    "seal_ref": fname,
                    "status": "SEALED",
                    "provenance": "VERIFIED",
                })
    return verdicts


# ---------------------------------------------------------------------------
# serve_world_data — the full bundle for compute.py's WorldState
# ---------------------------------------------------------------------------
def serve_world_data():
    """One call returning the full data bundle.

    Feeds registry_digest (sha256 of the vendored manifest digest input,
    computed in-process -> VERIFIED by compute) and feed_status
    (PENDING/UNKNOWN until ingest_reading supplies real data).
    Figures outside the WorldState carry their own figure-level labels.
    """
    digest_input = json.dumps(
        registry_summary(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    feeds = [
        {"name": e["name"], "reading": None, "reading_hash": None}
        for e in feed_registry().values()
    ]
    pricing = pricing_index()
    rte = rte_telemetry()
    verdicts = factory_verdicts()
    return {
        "registry_data": digest_input,
        "registry_summary": registry_summary(),
        "feeds": feeds,
        "pricing_rows": pricing["parsed"],
        "pricing_expected": pricing["expected"],
        "rte_metrics": rte["count"],
        "sealed_verdicts": len(verdicts),
        "provenance": "VERIFIED",  # assembled in-process from validated sources
    }


def serve_world_state(waves=None):
    """Build and return the signed-able WorldState dict for the thin client.

    Digests the vendored registries and the six feeds (all PENDING until a
    real reading + hash is ingested).
    """
    bundle = serve_world_data()
    return compute_world_state(
        waves or [],
        feeds=bundle["feeds"],
        registry_data=bundle["registry_data"],
    )
