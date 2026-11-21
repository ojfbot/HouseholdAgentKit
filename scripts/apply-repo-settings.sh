#!/usr/bin/env bash
# Apply merge settings, the main ruleset and security features to the new public repo (punchlist block 1).
# Owner-run (J or HP) once the repo exists. Idempotent: re-running updates the ruleset in place.
# Usage: scripts/apply-repo-settings.sh ojfbot/<repo>
set -euo pipefail
REPO="${1:?usage: $0 owner/repo}"

# Merge settings: rebase only, delete branch on merge, update-branch button on.
gh api -X PATCH "repos/$REPO" \
  -F allow_rebase_merge=true -F allow_squash_merge=false -F allow_merge_commit=false \
  -F delete_branch_on_merge=true -F allow_update_branch=true -F allow_auto_merge=false >/dev/null

# Ruleset (create or replace by name).
id=$(gh api "repos/$REPO/rulesets" -q '.[] | select(.name=="main") | .id' || true)
if [ -n "${id:-}" ]; then
  gh api -X PUT "repos/$REPO/rulesets/$id" --input .github/rulesets/main.json >/dev/null
else
  gh api -X POST "repos/$REPO/rulesets" --input .github/rulesets/main.json >/dev/null
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

# Verify: required check names must match job names exactly (a renamed check silently blocks merges).
gh api "repos/$REPO/rulesets/$(gh api "repos/$REPO/rulesets" -q '.[] | select(.name=="main") | .id')" \
  -q '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'
echo "expected: ci security privacy-guard cross-review"
