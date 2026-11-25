#!/usr/bin/env bash
# Apply merge settings, the main ruleset and security features to the new public repo (punchlist block 1).
# Owner-run (J or HP) once the repo exists. Idempotent: re-running updates the ruleset in place.
# Usage: scripts/apply-repo-settings.sh ojfbot/<repo>
set -euo pipefail
REPO="${1:?usage: $0 owner/repo}"
RULESET="$(cd "$(dirname "$0")/.." && pwd)/.github/rulesets/main.json"

# Merge settings: rebase only, delete branch on merge, update-branch button on.
gh api -X PATCH "repos/$REPO" \
  -F allow_rebase_merge=true -F allow_squash_merge=false -F allow_merge_commit=false \
  -F delete_branch_on_merge=true -F allow_update_branch=true -F allow_auto_merge=false >/dev/null

# Ruleset (create or replace by name).
id=$(gh api "repos/$REPO/rulesets" -q '.[] | select(.name=="main") | .id' || true)
if [ -n "${id:-}" ]; then
  gh api -X PUT "repos/$REPO/rulesets/$id" --input "$RULESET" >/dev/null
else
  gh api -X POST "repos/$REPO/rulesets" --input "$RULESET" >/dev/null
fi

# Security: secret scanning + push protection, Dependabot alerts and updates, private vulnerability reporting.
gh api -X PATCH "repos/$REPO" --input - >/dev/null <<'JSON'
{"security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}
JSON
gh api -X PUT "repos/$REPO/vulnerability-alerts" >/dev/null
gh api -X PUT "repos/$REPO/automated-security-fixes" >/dev/null
gh api -X PUT "repos/$REPO/private-vulnerability-reporting" >/dev/null
gh api -X PATCH "repos/$REPO/code-scanning/default-setup" -f state=configured -f query_suite=default >/dev/null || \
  echo "CodeQL default setup: enable in Settings > Code security if the API refuses"

# Labels the queue and digest read.
for l in contract adr irreversible cross-repo eval-failure gate-red impl:claude-code impl:codex ready-for-agent \
         HP IQ PD ED MF EN DX EL; do
  gh label create "$l" --repo "$REPO" --force >/dev/null
done
for f in a b c d e f g h i j; do gh label create "fork-$f" --repo "$REPO" --force >/dev/null; done

# Verify: the applied ruleset must require exactly the checks main.json requires (R-22). A renamed or missing
# check silently weakens the gate; an extra one nothing emits (cross-review, R-07) blocks every merge.
id=$(gh api "repos/$REPO/rulesets" -q '.[] | select(.name=="main") | .id')
[ -n "$id" ] || { echo "no ruleset named main on $REPO" >&2; exit 1; }
gh api "repos/$REPO/rulesets/$id" | python3 -I -c '
import json, sys

def checks(ruleset):
    return sorted(
        c["context"]
        for r in ruleset.get("rules", [])
        if r.get("type") == "required_status_checks"
        for c in r["parameters"]["required_status_checks"]
    )

with open(sys.argv[1]) as f:
    want = checks(json.load(f))
got = checks(json.load(sys.stdin))
print("required checks, main.json:", " ".join(want) or "(none)")
print("required checks, applied:  ", " ".join(got) or "(none)")
if got != want or not want:
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    if missing:
        print("missing:", " ".join(missing), file=sys.stderr)
    if extra:
        print("extra:", " ".join(extra), file=sys.stderr)
    if not want:
        print("main.json requires no checks", file=sys.stderr)
    print("the applied ruleset does not match .github/rulesets/main.json", file=sys.stderr)
    sys.exit(1)
' "$RULESET"
