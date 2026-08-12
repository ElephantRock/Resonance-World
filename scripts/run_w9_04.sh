#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
COALITION_CONFIG="$ROOT/configs/w9/w9-04-coalition.json"
CAMPAIGN_NAME="w9-stateful-source-development-discovery-v0.1"
SOURCE_STEP="$OUT/discovery-source-step"
RAW="$OUT/discovery-raw"
SOURCE="$OUT/discovery-source"
RESULT="$OUT/w9-04-coalition.json"
mkdir -p "$SOURCE_STEP" "$RAW" "$SOURCE"

(
  cd "$FIELD_DIR"
  python -m resonance.experiments.lifecycle_step_cli \
    --config "$SOURCE_CONFIG" \
    --experiment 63 \
    --code-sha "$FIELD_SHA" \
    --dsn "$DSN" \
    --output-dir "$SOURCE_STEP"
)

psql "$DSN" --csv -c "
  SELECT run_id::text, seed, arm_label, environment::text, metrics::text, completed_at
  FROM integration_campaign_runs
  WHERE campaign_name = '$CAMPAIGN_NAME'
    AND experiment_number = 63
    AND arm_label = 'immortal_control'
  ORDER BY seed
" > "$RAW/runs.csv"

psql "$DSN" --csv -c "
  SELECT o.run_id::text, o.cycle, o.task_id::text, o.task_domain,
         o.required_skill, o.winner_agent_id::text, o.winner_slot,
         o.success, o.winning_price, o.task_budget, o.created_at
  FROM integration_campaign_outcomes o
  JOIN integration_campaign_runs r ON r.run_id = o.run_id
  WHERE r.campaign_name = '$CAMPAIGN_NAME'
    AND r.experiment_number = 63
    AND r.arm_label = 'immortal_control'
  ORDER BY r.seed, o.cycle
" > "$RAW/outcomes.csv"

psql "$DSN" --csv -c "
  SELECT o.run_id::text, t.task_id::text, t.requester_agent_id::text
  FROM integration_campaign_outcomes o
  JOIN integration_campaign_runs r ON r.run_id = o.run_id
  JOIN market_tasks t ON t.task_id = o.task_id
  WHERE r.campaign_name = '$CAMPAIGN_NAME'
    AND r.experiment_number = 63
    AND r.arm_label = 'immortal_control'
  ORDER BY r.seed, t.task_id
" > "$RAW/tasks.csv"

psql "$DSN" --csv -c "
  SELECT o.run_id::text, b.task_id::text, b.bidder_agent_id::text,
         b.price, b.confidence, b.status
  FROM integration_campaign_outcomes o
  JOIN integration_campaign_runs r ON r.run_id = o.run_id
  JOIN market_bids b ON b.task_id = o.task_id
  WHERE r.campaign_name = '$CAMPAIGN_NAME'
    AND r.experiment_number = 63
    AND r.arm_label = 'immortal_control'
  ORDER BY r.seed, b.task_id, b.bidder_agent_id
" > "$RAW/bids.csv"

python -m resonance_world.w4_source_export \
  "$RAW/runs.csv" \
  "$RAW/outcomes.csv" \
  "$RAW/tasks.csv" \
  "$RAW/bids.csv" \
  "$SOURCE"

python -m resonance_world.w9_coalition \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$COALITION_CONFIG" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

value = json.loads(Path('output/w9/w9-04-coalition.json').read_text())
assert value['phase'] == 'discovery', value
assert len(value['pooled_factorial']['condition_results']) == 16, value
assert len(value['diagnostic_field_pair_results']) == 5, value
assert set(value['factor_results']) == {'D', 'R', 'C', 'V'}, value
assert len(value['interaction_results']) == 6, value
assert value['K'], value
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
print(json.dumps({
    'K': value['K'],
    'factor_results': {
        factor: {
            'main_effect_pp': row['main_effect_pp'],
            'positive_missions': row['positive_missions'],
            'positive_fields': row['positive_fields'],
            'selected_for_K': row['selected_for_K'],
        }
        for factor, row in value['factor_results'].items()
    },
    'material_interactions': {
        key: row['interaction_pp']
        for key, row in value['interaction_results'].items()
        if row['material_positive']
    },
}, indent=2, sort_keys=True))
PY
