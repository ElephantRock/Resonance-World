#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
LEASING_CONFIG="$ROOT/configs/w9/w9-02-leasing.json"
CAMPAIGN_NAME="w9-stateful-source-development-discovery-v0.1"

mkdir -p "$OUT"
SOURCE_STEP="$OUT/discovery-source-step"
RAW="$OUT/discovery-raw"
SOURCE="$OUT/discovery-source"
RESULT="$OUT/w9-02-leasing.json"
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

python -m resonance_world.w9_leasing \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$LEASING_CONFIG" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

value = json.loads(Path('output/w9/w9-02-leasing.json').read_text())
assert value['phase'] == 'discovery', value
assert value['classification'] in {
    'robust_sustainable_leasing',
    'leasing_switching_fragile',
    'leasing_not_sustainable',
}, value
assert value['arms']['lease-zero-recovery']['lease_conflict_rate'] == 0.0, value
assert value['arms']['lease-one-window-recovery']['lease_conflict_rate'] == 0.0, value
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
print(json.dumps({
    'classification': value['classification'],
    'zero_recovery_gate': value['zero_recovery_gate'],
    'recovery_gate': value['recovery_gate'],
    'robust_gate': value['robust_gate'],
    'permanent': {
        'org_success_pct': value['arms']['permanent']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['permanent']['mean_source_loss_pp'],
    },
    'four_two': {
        'org_success_pct': value['arms']['4:2']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['4:2']['mean_source_loss_pp'],
    },
    'lease_zero': {
        'org_success_pct': value['arms']['lease-zero-recovery']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['lease-zero-recovery']['mean_source_loss_pp'],
        'service_per_unavailable': value['arms']['lease-zero-recovery']['useful_external_service_per_source_unavailable_window'],
    },
    'lease_recovery': {
        'org_success_pct': value['arms']['lease-one-window-recovery']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['lease-one-window-recovery']['mean_source_loss_pp'],
        'recovery_idle_slots': value['arms']['lease-one-window-recovery']['recovery_idle_source_agent_slots'],
    },
}, indent=2, sort_keys=True))
PY
