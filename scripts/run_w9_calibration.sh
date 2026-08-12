#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
CAMPAIGN_CONFIG="$ROOT/configs/w9/criticality-campaign.json"
CAMPAIGN_NAME="w9-stateful-source-development-discovery-v0.1"

mkdir -p "$OUT"

SOURCE_STEP="$OUT/discovery-source-step"
RAW="$OUT/discovery-raw"
SOURCE="$OUT/discovery-source"
PREDICTIONS="$OUT/w9-00b-predictions.json"
RESULT="$OUT/w9-00b-calibration.json"

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

python - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path('output/w9/discovery-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 5, summary
assert summary['agent_count'] == 60, summary
assert summary['seeds'] == [3611, 3731, 3851, 3971, 4091], summary
public = Path('output/w9/discovery-source/candidates.jsonl').read_text()
assert 'practice_by_skill' not in public
PY

# Materialize every public-only prediction first. This command does not require or read
# capsules.private.jsonl; the private source state is consulted only by the evaluate step.
python -m resonance_world.w9_calibration_execution prepare \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$CAMPAIGN_CONFIG" \
  --output "$PREDICTIONS"

python - <<'PY'
import json
from pathlib import Path

value = json.loads(Path('output/w9/w9-00b-predictions.json').read_text())
assert value['field_count'] == 5, value
assert value['agent_count'] == 60, value
assert value['principal_observation_count'] == 120, value
assert value['interaction_observation_count'] == 660, value
assert value['seeds'] == [3611, 3731, 3851, 3971, 4091], value
assert value['field_sha'] == '2a85739603ebac86f451b90733229782c0d45ce0', value
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
PY

python -m resonance_world.w9_calibration_execution evaluate \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$CAMPAIGN_CONFIG" \
  --predictions "$PREDICTIONS" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

value = json.loads(Path('output/w9/w9-00b-calibration.json').read_text())
assert value['field_count'] == 5, value
assert value['agent_count'] == 60, value
assert value['seeds'] == [3611, 3731, 3851, 3971, 4091], value
assert value['field_sha'] == '2a85739603ebac86f451b90733229782c0d45ce0', value
assert value['calibration']['observation_count'] == 120, value
assert value['interaction_diagnostic']['observation_count'] == 660, value
assert value['calibration']['label'] in {
    'calibrated_source_cost_estimator',
    'biased_but_rank_informative',
    'uncalibrated_source_cost_estimator',
}, value
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
print(json.dumps({
    'label': value['calibration']['label'],
    'mae_pp': value['calibration']['mae_pp'],
    'signed_bias_pp': value['calibration']['signed_bias_pp'],
    'spearman_rho': value['calibration']['spearman_rho'],
    'high_cost_safe_rate': value['calibration']['high_cost_safe_rate'],
    'result_sha256': value['result_sha256'],
}, indent=2, sort_keys=True))
PY
