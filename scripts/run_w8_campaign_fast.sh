#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# The scientific runner is frozen in run_w8_campaign.sh. Substitute only the Python
# module entry point so prepare/phase/synthesis install mathematically exact cached
# source-frontier calculations before delegating to the same evaluator.
sed 's/resonance_world\.w8_execution/resonance_world.w8_fastpath/g' \
  "$ROOT/scripts/run_w8_campaign.sh" > "$TMP"

bash "$TMP"
