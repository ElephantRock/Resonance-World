#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
CONFIG="$ROOT/configs/w9/w9-05-integrated.json"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
W8_DB="resonance_w9_05_w8"
W8_DSN="${DSN%/*}/$W8_DB"
W8_PLAN="$OUT/w9-05-w8-replacement-plan.json"
W8_REPLACEMENT="$OUT/w9-05-w8-native-replacement.json"
RESULT="$OUT/w9-05-integrated.json"

mkdir -p "$OUT"

# Regenerate the exact W9-03 discovery source, matched development control, and
# portfolio-development source in this fresh CI evidence store. W9-05 consumes
# only the base and preregistered portfolio source; running the existing script
# preserves W9-03's frozen development law rather than duplicating it here.
bash "$ROOT/scripts/run_w9_03.sh"

BASE_SOURCE="$OUT/discovery-source"
PORTFOLIO_SOURCE="$OUT/w9-03-portfolio-source"

test -f "$BASE_SOURCE/candidates.jsonl"
test -f "$PORTFOLIO_SOURCE/candidates.jsonl"

# Build the W8 integrated-charter comparator on the same W9 discovery source in
# a separate PostgreSQL store so its native-successor lifecycle cannot contaminate
# the W9-03/W9-05 source evidence.
psql "$DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE $W8_DB"
(
  cd "$FIELD_DIR"
  RESONANCE_W9_05_W8_DSN="$W8_DSN" python - <<'PY'
import os
import psycopg
from psycopg.rows import dict_row
from resonance.experiments.runner import apply_migrations

with psycopg.connect(
    os.environ["RESONANCE_W9_05_W8_DSN"],
    autocommit=True,
    row_factory=dict_row,
) as connection:
    apply_migrations(connection)
PY
)

python -m resonance_world.w8_execution prepare \
  --phase discovery \
  --source-dir "$BASE_SOURCE" \
  --config "$CONFIG" \
  --output "$W8_PLAN"

python -m resonance_world.w8_native_replacement_execution \
  --dsn "$W8_DSN" \
  --source-config "$SOURCE_CONFIG" \
  --plan "$W8_PLAN" \
  --campaign-config "$CONFIG" \
  --output "$W8_REPLACEMENT"

python -m resonance_world.w9_integrated_execution \
  --phase discovery \
  --base-source-dir "$BASE_SOURCE" \
  --portfolio-source-dir "$PORTFOLIO_SOURCE" \
  --config "$CONFIG" \
  --w8-replacement "$W8_REPLACEMENT" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path('output/w9/w9-05-integrated.json').read_text())
assert result['version'] == 'w9-05-integrated-market-result-v0.1', result
assert result['phase'] == 'discovery', result
assert result['upstream_eligibility'] == {'C': False, 'L': False, 'P': False, 'K': []}, result
assert result['selected_mechanisms'] == [], result
assert result['structural_status'] == 'no_upstream_eligible_w9_mechanisms', result
assert result['selected_regime'] == result['W7_unrestricted'], result

aliases = result['registered_diagnostic_labels']
required = {
    'full_C+L+P+K',
    'leave_one_out_C', 'leave_one_out_L', 'leave_one_out_P', 'leave_one_out_K',
    'leave_two_out_C_L', 'leave_two_out_C_P', 'leave_two_out_C_K',
    'leave_two_out_L_P', 'leave_two_out_L_K', 'leave_two_out_P_K',
    'W7_unrestricted', 'criticality_only', 'leasing_only', 'substitution_only',
    'leasing_plus_substitution',
}
assert required <= set(aliases), aliases
assert aliases['full_C+L+P+K'] == aliases['leave_one_out_K'] == 'C1L1P1'
assert aliases['leave_one_out_C'] == aliases['leave_two_out_C_K'] == 'C0L1P1'
assert set(result['canonical_diagnostic_arms']) == {
    'C0L0P0', 'C0L0P1', 'C0L1P0', 'C0L1P1',
    'C1L0P0', 'C1L0P1', 'C1L1P0', 'C1L1P1',
}
assert 'practice_by_skill' not in json.dumps(result, sort_keys=True)

summary = {
    'classification': result['classification'],
    'integrated_static_gate': result['integrated_static_gate'],
    'gates': result['gates'],
    'selected_mechanisms': result['selected_mechanisms'],
    'selected_regime': {
        'organization_success_pct': result['selected_regime']['mean_organization_success_pct'],
        'source_loss_pp': result['selected_regime']['mean_source_loss_pp'],
        'organization_inequality_sd_pp': result['selected_regime']['organization_outcome_inequality_sd_pp'],
    },
    'diagnostics': {
        label: {
            'organization_success_pct': arm['mean_organization_success_pct'],
            'source_loss_pp': arm['mean_source_loss_pp'],
            'contracts': arm['contract_count'],
        }
        for label, arm in result['direct_L_vs_P_vs_LP'].items()
    },
    'nominal_full': {
        'organization_success_pct': result['canonical_diagnostic_arms']['C1L1P1']['mean_organization_success_pct'],
        'source_loss_pp': result['canonical_diagnostic_arms']['C1L1P1']['mean_source_loss_pp'],
        'contracts': result['canonical_diagnostic_arms']['C1L1P1']['contract_count'],
    },
    'w8_comparator': {
        'organization_success_pct': result['W8_integrated_charter_comparator']['mean_organization_success_pct'],
        'source_loss_pp': result['W8_integrated_charter_comparator']['mean_source_loss_pp'],
    },
}
print(json.dumps(summary, indent=2, sort_keys=True))
PY
