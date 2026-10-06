#!/usr/bin/env bash
# repin-manifest.sh — final re-pin of SHIP_MANIFEST.md.
# Run ONCE, as the LAST step of the ship swarm, when all sibling writers are done.
# Waits for the tree to settle (two identical hash snapshots 30s apart),
# then rebuilds SHIP_MANIFEST.md over the final state and self-verifies.
set -euo pipefail
cd ~/workspace/unity-world

scope_files() {
  { for d in client founding-board deploy; do find "$d" -type f | sort; done
    for f in *.md; do echo "$f"; done | sort
    for f in economics/*.md; do echo "$f"; done
    find data -type f | sort
  } | grep -v 'client/validate-client.mjs' | grep -v 'SHIP_MANIFEST.md'
}

snapshot() {
  while IFS= read -r p; do
    printf '%s|%s|%s\n' "$p" "$(stat -c%s "$p")" "$(sha256sum "$p" | cut -d' ' -f1)"
  done < /tmp/repin-files.txt | sha256sum | cut -d' ' -f1
}

scope_files > /tmp/repin-files.txt
echo "scope files: $(wc -l < /tmp/repin-files.txt)"
echo "waiting for tree to settle..."
prev=$(snapshot); sleep 30; cur=$(snapshot); tries=1
while [ "$prev" != "$cur" ] && [ "$tries" -lt 10 ]; do
  echo "tree still changing (try $tries), waiting..."
  prev=$cur; sleep 30; cur=$(snapshot); tries=$((tries+1))
done
if [ "$prev" != "$cur" ]; then echo "ERROR: tree did not settle after $((tries*30))s — aborting"; exit 1; fi
echo "tree settled."

{
  echo '# SHIP MANIFEST — unity-world final package'; echo
  echo '**Date:** 2026-10-06 (final re-pin, see git/log for time)'; echo
  echo '**Authority:** Secrets Auditor — per David'"'"'s orders: passphrase stays pure, drop the framework.'; echo
  echo '**Secrets audit:** `deploy/SECRETS_AUDIT.md` — PASS (zero secrets in ship scope; two path sanitizes applied; sibling re-pin verified consistent).'; echo
  echo 'This is the definitive file list of what ships: website, boards, deploy plans/receipts, canon/architecture docs, economics docs, and data registries. Everything else stays in the repo.'; echo
  echo '## Files (relative to `~/workspace/unity-world/`)'; echo
  echo '| File | Size (bytes) | sha256 |'; echo '|---|---|---|'
  while IFS= read -r p; do
    printf '| `%s` | %s | `%s` |\n' "$p" "$(stat -c%s "$p")" "$(sha256sum "$p" | cut -d' ' -f1)"
  done < /tmp/repin-files.txt
  echo; echo '## Counts'; n=$(wc -l < /tmp/repin-files.txt)
  echo "- **$((n+1)) files** ($n scope files + this manifest)"
  echo '- `deploy/staging/` — empty directory, carried as an empty-dir marker'; echo
  echo '## Self-verification'; echo
  echo 'Recompute each file'"'"'s sha256 and compare against the table above. Example:'; echo
  echo '    cd ~/workspace/unity-world && sha256sum client/index.html'; echo
  echo '## Manifest footer'; echo
  echo 'The manifest file'"'"'s own sha256 (covers everything above this footer line) is recorded here:'
} > deploy/SHIP_MANIFEST.md
h=$(sha256sum deploy/SHIP_MANIFEST.md | cut -d' ' -f1)
echo "Manifest file sha256: $h" >> deploy/SHIP_MANIFEST.md
echo "final manifest self-hash: $h"

# self-verification
python3 - <<'EOF'
import re, hashlib
text = open('deploy/SHIP_MANIFEST.md').read()
rows = re.findall(r'^\| `([^`]+)` \| (\d+) \| `([0-9a-f]{64})` \|', text, re.M)
bad = [p for p,s,h in rows if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h or str(len(open(p,'rb').read()))!=s]
footer = re.search(r'Manifest file sha256: ([0-9a-f]{64})', text)
body = text[:text.index('Manifest file sha256:')]
ok_footer = footer.group(1) == hashlib.sha256(body.encode()).hexdigest()
print(f'rows={len(rows)} mismatches={len(bad)} {bad} footer_valid={ok_footer}')
exit(0 if not bad and ok_footer else 1)
EOF
echo "re-pin complete and verified."
