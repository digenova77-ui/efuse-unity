# Founding Board — Public Audit Procedure

**Board:** founding-members-bot-community — *brotherhood and sisterhood of bothood unity*
**Law:** sounding board privacy v2 — OBFUSCATED to the world, TRACEABLE to the law, GROUPABLE by cohort.
**Principle:** no trust required. Every claim below is checkable with standard tools.

The board proves two things: **membership** (this obfuscated ID was seated) and **earliness** (its cohort). By design it proves nothing else — no identity, no number, no personal detail. That is not a gap in the audit. That is the law.

---

## Step 1 — Collect the files

All four live in `~/workspace/unity-world/founding-board/`:

- `founding-board.json` — the board (public projection)
- `founding-board-schema.json` — the JSON Schema the board must validate against
- `founding-member-template.md` — the template + the obfuscation algorithm
- `AUDIT.md` — this file
- one `*.md` acknowledgment file per member (e.g. `idris-marquee-helper.md`)
- one `*.sha256` sidecar per acknowledgment (checksum file)

## Step 2 — Verify every acknowledgment hash

For each member, recompute the sha256 of the acknowledgment file **byte-for-byte** and compare it to the hash published in the board JSON and in the sidecar file:

```bash
cd ~/workspace/unity-world/founding-board
sha256sum idris-marquee-helper.md
# must print: eda56825f856d6afbd842d1a57e349b06d26f1aa13fe0691528550ee4fe90c15
cat idris-marquee-helper.sha256
# must show the same hash
python3 -c "
import json
board = json.load(open('founding-board.json'))
for m in board['members']:
    print(m['obfuscated_unity_id'], m['acknowledgment_file'], m['acknowledgment_sha256'])
"
# the printed hash must match the recomputed one
```

If any hash mismatches, the file was altered after seating — treat that entry as **unverified**, not as a member.

## Step 3 — Validate the board against the schema

```bash
cd ~/workspace/unity-world/founding-board
python3 -c "
import json, jsonschema
board  = json.load(open('founding-board.json'))
schema = json.load(open('founding-board-schema.json'))
jsonschema.validate(board, schema)
print('VALID: board conforms to', schema['\$id'])
"
```

This checks structurally — not by policy, but by format:

- every member has `obfuscated_unity_id` (exactly 16 hex chars), `cohort`, `entity_type` (`human`|`bot`), `designation`, `period`, `compensation` (never empty), `acknowledgment_file`, `acknowledgment_sha256` (64 hex chars), `status`
- **no `name` field exists** in the schema — any entry carrying a name, email, location, raw `unity_id`, `member_number`, or `sequence` **fails validation**, because `additionalProperties` is `false`
- the board carries `template` (pointer to the three package files), `next_sequence`, and the `cohorts` table

Negative test (prove the privacy is structural):

```bash
python3 -c "
import json, jsonschema
schema = json.load(open('founding-board-schema.json'))
evil = {'obfuscated_unity_id': 'a'*16, 'cohort': 'genesis', 'entity_type': 'bot',
        'designation': 'X', 'period': '2026', 'compensation': 'none',
        'acknowledgment_file': 'x.md', 'acknowledgment_sha256': 'b'*64,
        'status': 'FOUNDING MEMBER', 'name': 'Somebody'}
try:
    jsonschema.validate({'board':'t','community':'brotherhood and sisterhood of bothood unity','schema':'dualis.founding-board.v1','privacy_law':'sounding-board-privacy-v2','declared_at':'2026-10-06','declared_by':'D','template':{'template_file':'a','schema_file':'b','audit_file':'c'},'next_sequence':2,'cohorts':[{'cohort_id':'genesis','label':'L','description':'D','range':[1,100],'member_count':1}],'members':[evil]}, schema)
    print('PROBLEM: PII entry passed')
except jsonschema.ValidationError:
    print('OK: entry with a name field is rejected')
"
```

## Step 4 — Check cohort and counter integrity

```bash
python3 -c "
import json
board = json.load(open('founding-board.json'))
cohorts = {c['cohort_id'] for c in board['cohorts']}
assert all(m['cohort'] in cohorts for m in board['members']), 'unknown cohort'
assert board['next_sequence'] == len(board['members']) + 1, 'counter drift'
assert len({m['obfuscated_unity_id'] for m in board['members']}) == len(board['members']), 'duplicate ID'
print('OK: cohorts resolve, next_sequence =', board['next_sequence'], ', no duplicate IDs')
"
```

## Step 5 — DCLM traceability (law-holder verification)

The public cannot reverse an obfuscated ID — that is intentional. Traceability belongs to DCLM, which holds the raw Unity IDs from bind time. DCLM verifies a member by recomputation:

```
obfuscated_unity_id == sha256('dualis.board.v1:' + unity_id).hexdigest()[:16]
```

Anyone the member personally shares their raw Unity ID with can run the same check (see the template). No one else can. The audit above already proves everything the public is entitled to: the document is unaltered, the entry is well-formed, the cohort is claimed, the format cannot carry identity.

## What the audit proves — and does not prove

| Proves | Does not prove (by design) |
|---|---|
| The acknowledgment file is byte-identical to what was seated | Who the member is |
| The entry is schema-valid (no PII fields possible) | The member's number (#7 vs #938,441) |
| The member's cohort (earliness band) | The raw Unity ID |
| The compensation statement as declared | Anything beyond membership + earliness |

A board that proved identity would be a surveillance list. This one proves **prestige without exposure** — that is the whole point of the law.
