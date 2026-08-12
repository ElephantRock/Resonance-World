#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-discovery.json"
PORTFOLIO_CONFIG="$ROOT/configs/w9/w9-03-portfolio.json"
SOURCE_CAMPAIGN="w9-stateful-source-development-discovery-v0.1"
DEVELOPMENT_CAMPAIGN="w9-portfolio-development-discovery-v0.1"

mkdir -p "$OUT"
SOURCE_STEP="$OUT/discovery-source-step"
RAW="$OUT/discovery-raw"
SOURCE="$OUT/discovery-source"
PLAN="$OUT/w9-03-portfolio-plan.json"
RUNS="$OUT/w9-03-development-runs.json"
CONTROL_SOURCE="$OUT/w9-03-control-source"
PORTFOLIO_SOURCE="$OUT/w9-03-portfolio-source"
RESULT="$OUT/w9-03-portfolio.json"
mkdir -p "$SOURCE_STEP" "$RAW" "$SOURCE" "$CONTROL_SOURCE" "$PORTFOLIO_SOURCE"

(
  cd "$FIELD_DIR"
  python -m resonance.experiments.lifecycle_step_cli \
    --config "$SOURCE_CONFIG" \
    --experiment 63 \
    --code-sha "$FIELD_SHA" \
    --dsn "$DSN" \
    --output-dir "$SOURCE_STEP"
)

export_source_rows() {
  local campaign="$1"
  local arm_predicate="$2"
  local raw_dir="$3"
  local destination="$4"
  mkdir -p "$raw_dir" "$destination"

  psql "$DSN" --csv -c "
    SELECT run_id::text, seed, arm_label, environment::text, metrics::text, completed_at
    FROM integration_campaign_runs
    WHERE campaign_name = '$campaign'
      AND experiment_number = 63
      AND ($arm_predicate)
    ORDER BY seed
  " > "$raw_dir/runs.csv"

  psql "$DSN" --csv -c "
    SELECT o.run_id::text, o.cycle, o.task_id::text, o.task_domain,
           o.required_skill, o.winner_agent_id::text, o.winner_slot,
           o.success, o.winning_price, o.task_budget, o.created_at
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND ($arm_predicate)
    ORDER BY r.seed, o.cycle
  " > "$raw_dir/outcomes.csv"

  psql "$DSN" --csv -c "
    SELECT o.run_id::text, t.task_id::text, t.requester_agent_id::text
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    JOIN market_tasks t ON t.task_id = o.task_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND ($arm_predicate)
    ORDER BY r.seed, t.task_id
  " > "$raw_dir/tasks.csv"

  psql "$DSN" --csv -c "
    SELECT o.run_id::text, b.task_id::text, b.bidder_agent_id::text,
           b.price, b.confidence, b.status
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    JOIN market_bids b ON b.task_id = o.task_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND ($arm_predicate)
    ORDER BY r.seed, b.task_id, b.bidder_agent_id
  " > "$raw_dir/bids.csv"

  python -m resonance_world.w4_source_export \
    "$raw_dir/runs.csv" \
    "$raw_dir/outcomes.csv" \
    "$raw_dir/tasks.csv" \
    "$raw_dir/bids.csv" \
    "$destination"
}

export_source_rows \
  "$SOURCE_CAMPAIGN" \
  "r.arm_label = 'immortal_control'" \
  "$RAW/base" \
  "$SOURCE"

python -m resonance_world.w9_portfolio_development plan \
  --phase discovery \
  --source-dir "$SOURCE" \
  --config "$PORTFOLIO_CONFIG" \
  --output "$PLAN"

python -m resonance_world.w9_portfolio_development run \
  --dsn "$DSN" \
  --source-config "$SOURCE_CONFIG" \
  --config "$PORTFOLIO_CONFIG" \
  --plan "$PLAN" \
  --output "$RUNS"

export_source_rows \
  "$DEVELOPMENT_CAMPAIGN" \
  "r.arm_label LIKE 'w9-compute-control-seed%'" \
  "$RAW/control" \
  "$CONTROL_SOURCE"

export_source_rows \
  "$DEVELOPMENT_CAMPAIGN" \
  "r.arm_label LIKE 'w9-portfolio-seed%'" \
  "$RAW/portfolio" \
  "$PORTFOLIO_SOURCE"

python -m resonance_world.w9_portfolio \
  --phase discovery \
  --no-preparation-dir "$SOURCE" \
  --matched-control-dir "$CONTROL_SOURCE" \
  --portfolio-dir "$PORTFOLIO_SOURCE" \
  --config "$PORTFOLIO_CONFIG" \
  --output "$RESULT"

python - <<'PY'
import json
from pathlib import Path

plan = json.loads(Path('output/w9/w9-03-portfolio-plan.json').read_text())
runs = json.loads(Path('output/w9/w9-03-development-runs.json').read_text())
value = json.loads(Path('output/w9/w9-03-portfolio.json').read_text())
assert plan['field_count'] == 5, plan
assert plan['agent_count'] == 60, plan
assert all(len(row['selected_strata']) == 3 for row in plan['fields']), plan
assert len(runs['runs']) == 10, runs
assert runs['development_tasks_per_field'] == 12, runs
assert runs['development_compute_units_per_field'] == 144, runs
assert value['phase'] == 'discovery', value
assert value['classification'] in {
    'portfolio_redundancy_effective',
    'generic_development_sufficient',
    'redundancy_already_sufficient',
    'redundancy_not_efficient',
}, value
assert 'practice_by_skill' not in json.dumps(plan, sort_keys=True)
assert 'practice_by_skill' not in json.dumps(value, sort_keys=True)
print(json.dumps({
    'classification': value['classification'],
    'eligible_for_w9_05_P': value['eligible_for_w9_05_P'],
    'no_preparation': {
        'viable': value['arms']['no-preparation']['viable'],
        'contracts': value['arms']['no-preparation']['contract_count'],
        'org_success_pct': value['arms']['no-preparation']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['no-preparation']['mean_source_loss_pp'],
        'unrestricted_org_success_pct': value['arms']['no-preparation']['unrestricted']['mean_organization_success_pct'],
    },
    'matched_control': {
        'viable': value['arms']['matched-compute-control']['viable'],
        'contracts': value['arms']['matched-compute-control']['contract_count'],
        'org_success_pct': value['arms']['matched-compute-control']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['matched-compute-control']['mean_source_loss_pp'],
        'unrestricted_org_success_pct': value['arms']['matched-compute-control']['unrestricted']['mean_organization_success_pct'],
    },
    'portfolio': {
        'viable': value['arms']['portfolio']['viable'],
        'contracts': value['arms']['portfolio']['contract_count'],
        'org_success_pct': value['arms']['portfolio']['mean_organization_success_pct'],
        'source_loss_pp': value['arms']['portfolio']['mean_source_loss_pp'],
        'unrestricted_org_success_pct': value['arms']['portfolio']['unrestricted']['mean_organization_success_pct'],
    },
}, indent=2, sort_keys=True))
PY
