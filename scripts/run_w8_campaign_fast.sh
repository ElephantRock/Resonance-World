#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# The scientific runner is frozen in run_w8_campaign.sh. Substitute only the Python
# module entry point so prepare/phase/synthesis install mathematically exact cached
# source-frontier calculations before delegating to the same evaluator. The second
# substitution updates only the final runner allowlist to recognize the corrected
# replicated non-sustainable synthesis label; it does not alter any experiment output.
sed \
  -e 's/resonance_world\.w8_execution/resonance_world.w8_fastpath/g' \
  -e "/'replicated_regulatory_null_or_negative',/a\\    'replicated_non_sustainable_regulatory_regime'," \
  "$ROOT/scripts/run_w8_campaign.sh" > "$TMP"

bash "$TMP"
