#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
OUT="$ROOT/output/w9"
MARKET_CONFIG="$ROOT/configs/w9/w9-05-integrated.json"
LONG_CONFIG="$ROOT/configs/w9/w9-06-long-horizon.json"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
W8_DB="resonance_w9_06_w8"
W8_DSN="${DSN%/*}/$W8_DB"
W8_PLAN="$OUT/w9-06-w8-replacement-plan.json"
W8_REPLACEMENT="$OUT/w9-06-w8-native-replacement.json"
RESULT="$OUT/w9-06-long-horizon.json"

mkdir -p "$OUT"

# Regenerate the frozen W9 discovery population. W9-06 selected W9, W7, and
# no-portfolio controls are structural aliases and consume this same source draw.
bash "$ROOT/scripts/run_w9_03.sh"
BASE_SOURCE="$OUT/discovery-source"
test -f "$BASE_SOURCE/candidates.jsonl"

# Regenerate the W8 neutral-charter native-successor comparator on the same W9
# discovery source in a fresh evidence store. The exact fast path is the same
# validated preparation used by W9-05.
psql "$DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE $W8_DB"
(
  cd "$FIELD_DIR"
  RESONANCE_W9_06_W8_DSN="$W8_DSN" python - <<'PY'
import os
import psycopg
from psycopg.rows import dict_row
from resonance.experiments.runner import apply_migrations

with psycopg.connect(
    os.environ["RESONANCE_W9_06_W8_DSN"],
    autocommit=True,
    row_factory=dict_row,
) as connection:
    apply_migrations(connection)
PY
)

python -m resonance_world.w8_fastpath prepare \
  --phase discovery \
  --source-dir "$BASE_SOURCE" \
  --config "$MARKET_CONFIG" \
  --output "$W8_PLAN"

python -m resonance_world.w8_native_replacement_execution \
  --dsn "$W8_DSN" \
  --source-config "$SOURCE_CONFIG" \
  --plan "$W8_PLAN" \
  --campaign-config "$MARKET_CONFIG" \
  --output "$W8_REPLACEMENT"

python -m resonance_world.w9_long_horizon_execution \
  --phase discovery \
  --source-dir "$BASE_SOURCE" \
  --market-config "$MARKET_CONFIG" \
  --long-horizon-config "$LONG_CONFIG" \
  --w8-replacement "$W8_REPLACEMENT" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path('output/w9/w9-06-long-horizon.json').read_text())
assert result['version'] == 'w9-06-long-horizon-result-v0.4', result
assert result['phase'] == 'discovery', result
assert result['selected_mechanisms'] == [], result
assert result['structural_status'] == 'selected_W9_equals_W7_and_noP_control', result
assert result['alias_map'] == {
    'W7_unrestricted': 'selected_W9',
    'W9_without_portfolio_development': 'selected_W9',
}, result
selected = result['arms']['selected_W9']
w8 = result['arms']['W8_neutral_full_regulatory_charter']
assert selected == result['arms']['W7_unrestricted'], result
assert selected == result['arms']['W9_without_portfolio_development'], result
assert selected['compute']['incremental_source_development_compute'] == 0.0, selected
assert selected['developmental_efficiency'] is None, selected
assert selected['compute']['source_diagnostic_mission_execution_compute'] == 122880.0, selected
assert selected['compute']['mission_execution_compute'] == 221184.0, selected
assert selected['compute']['final_total_measured_compute_including_cycle0_embodied'] == 222192.0, selected
assert result['gates']['developmental_efficiency_at_least_20pct_better_than_W8'] is False, result
assert result['accounting']['source_development_unit'] == 'resident_agent_cycle', result
assert w8['compute']['coalition_mission_execution_compute'] == 36864.0, w8
assert w8['compute']['source_diagnostic_mission_execution_compute'] == 64000.0, w8
assert w8['compute']['standalone_comparator_pair_selection_compute'] == 48.0, w8
assert w8['compute']['neutral_budget_update_regulatory_compute'] == 72.0, w8
assert w8['compute']['mission_execution_compute'] == 199168.0, w8
assert w8['compute']['organization_coordination_compute'] == 144.0, w8
assert w8['compute']['world_regulatory_estimation_compute'] == 2271.0, w8
assert w8['compute']['final_total_measured_compute_including_cycle0_embodied'] == 202219.0, w8
assert result['accounting_corrections']['selected_source_frontier_diagnostics']['mission_execution_compute_added'] == 122880.0, result
assert result['accounting_corrections']['w8_source_frontier_diagnostics']['mission_execution_compute_added'] == 64000.0, result
assert result['accounting_corrections']['w8_neutral_budget_updates']['world_regulatory_estimation_compute_added'] == 72.0, result
assert 'practice_by_skill' not in json.dumps(result, sort_keys=True), result

summary = {
    'classification': result['classification'],
    'long_horizon_gate': result['long_horizon_gate'],
    'gates': result['gates'],
    'selected': {
        'organization_success_pct': selected['mean_organization_success_pct'],
        'source_loss_pp': selected['mean_source_loss_pp'],
        'normalized_world_stock_growth': selected['compute_normalized_world_stock_growth'],
        'source_accessible_capability_growth': selected['source_accessible_capability_growth'],
        'developmental_efficiency': selected['developmental_efficiency'],
        'service_efficiency': selected['service_efficiency'],
        'total_efficiency_final': selected['total_efficiency_final'],
    },
    'w8_neutral': {
        key: w8[key]
        for key in (
            'mean_organization_success_pct',
            'mean_source_loss_pp',
            'compute_normalized_world_stock_growth',
            'source_accessible_capability_growth',
            'developmental_efficiency',
            'service_efficiency',
            'total_efficiency_final',
        )
    },
}
print(json.dumps(summary, indent=2, sort_keys=True))
PY
