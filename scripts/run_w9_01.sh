#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
ALLOCATION_CONFIG="$ROOT/configs/w9/w9-01-allocation.json"
CALIBRATION_ACCEPTANCE="$ROOT/configs/w9/w9-00b-acceptance.json"
CAMPAIGN_NAME="w9-stateful-source-development-discovery-v0.1"

mkdir -p "$OUT"
SOURCE_STEP="$OUT/discovery-source-step"
RAW="$OUT/discovery-raw"
SOURCE="$OUT/discovery-source"
RESULT="$OUT/w9-01-allocation.json"
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
assert 'practice_by_skill' not in Path('output/w9/discovery-source/candidates.jsonl').read_text()
acceptance = json.loads(Path('configs/w9/w9-00b-acceptance.json').read_text())
assert acceptance['classification'] == 'calibrated_source_cost_estimator', acceptance
assert acceptance['authorizes_w9_01_principal_claim'] is True, acceptance
PY

python -m resonance_world.w9_allocation \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$ALLOCATION_CONFIG" \
  --calibration-acceptance "$CALIBRATION_ACCEPTANCE" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

value = json.loads(Path('output/w9/w9-01-allocation.json').read_text())
assert value['phase'] == 'discovery', value
assert value['calibration_classification'] == 'calibrated_source_cost_estimator', value
assert value['classification'] in {
    'criticality_allocation_effective',
    'criticality_allocation_ineffective',
}, value
assert value['criticality_aware']['mean_conservative_budget_used_pp'] <= 2.0 + 1e-12, value
assert all(
    budget <= 2.0 + 1e-12
    for budget in value['criticality_aware']['conservative_budget_pp_by_field'].values()
), value
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
print(json.dumps({
    'classification': value['classification'],
    'gate': value['gate'],
    'gates': value['gates'],
    'unrestricted_org_success_pct': value['unrestricted']['mean_organization_success_pct'],
    'unrestricted_source_loss_pp': value['unrestricted']['mean_source_loss_pp'],
    'criticality_org_success_pct': value['criticality_aware']['mean_organization_success_pct'],
    'criticality_source_loss_pp': value['criticality_aware']['mean_source_loss_pp'],
    'source_loss_reduction_fraction': value['criticality_aware']['source_loss_reduction_fraction_vs_unrestricted'],
    'criticality_contract_count': value['criticality_aware']['contract_count'],
    'cap2_org_success_pct': value['cap_2']['mean_organization_success_pct'],
    'cap2_source_loss_pp': value['cap_2']['mean_source_loss_pp'],
}, indent=2, sort_keys=True))
PY
