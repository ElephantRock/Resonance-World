#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w9/replication"
SOURCE_CONFIG="$ROOT/configs/w9/source-development-replication.json"
CRITICALITY_CONFIG="$ROOT/configs/w9/criticality-campaign.json"
ALLOCATION_CONFIG="$ROOT/configs/w9/w9-01-allocation.json"
CALIBRATION_ACCEPTANCE="$ROOT/configs/w9/w9-00b-acceptance.json"
LEASING_CONFIG="$ROOT/configs/w9/w9-02-leasing.json"
PORTFOLIO_CONFIG="$ROOT/configs/w9/w9-03-portfolio-replication.json"
COALITION_CONFIG="$ROOT/configs/w9/w9-04-coalition.json"
MARKET_CONFIG="$ROOT/configs/w9/w9-05-integrated.json"
LONG_CONFIG="$ROOT/configs/w9/w9-06-long-horizon.json"
SOURCE_CAMPAIGN="w9-stateful-source-development-replication-v0.1"
DEVELOPMENT_CAMPAIGN="w9-portfolio-development-replication-v0.1"

SOURCE_STEP="$OUT/source-step"
RAW="$OUT/raw"
SOURCE_RAW="$OUT/source-raw"
SOURCE="$OUT/source"
CONTROL_SOURCE="$OUT/w9-03-control-source"
PORTFOLIO_SOURCE="$OUT/w9-03-portfolio-source"
CAL_PREDICTIONS="$OUT/w9-00b-predictions.json"
CAL_RESULT="$OUT/w9-00b-calibration.json"
ALLOCATION_RESULT="$OUT/w9-01-allocation.json"
LEASING_RESULT="$OUT/w9-02-leasing.json"
PORTFOLIO_PLAN="$OUT/w9-03-portfolio-plan.json"
PORTFOLIO_RUNS="$OUT/w9-03-development-runs.json"
PORTFOLIO_RESULT="$OUT/w9-03-portfolio.json"
COALITION_RESULT="$OUT/w9-04-coalition.json"
W8_STATIC_DB="resonance_w9_07_w8_static"
W8_STATIC_DSN="${DSN%/*}/$W8_STATIC_DB"
W8_STATIC_PLAN="$OUT/w9-05-w8-replacement-plan.json"
W8_STATIC_REPLACEMENT="$OUT/w9-05-w8-native-replacement.json"
INTEGRATED_RESULT="$OUT/w9-05-integrated.json"
W8_LONG_DB="resonance_w9_07_w8_long"
W8_LONG_DSN="${DSN%/*}/$W8_LONG_DB"
W8_LONG_PLAN="$OUT/w9-06-w8-replacement-plan.json"
W8_LONG_REPLACEMENT="$OUT/w9-06-w8-native-replacement.json"
LONG_RESULT="$OUT/w9-06-long-horizon.json"
SYNTHESIS="$OUT/w9-07-replication.json"

mkdir -p "$SOURCE_STEP" "$RAW" "$SOURCE_RAW" "$CONTROL_SOURCE" "$PORTFOLIO_SOURCE"

export_source_rows() {
  local campaign="$1"
  local arm_predicate="$2"
  local raw_dir="$3"
  local destination="$4"
  local normalize_arm="${5:-false}"
  mkdir -p "$raw_dir" "$destination"

  psql "$DSN" --csv -c "
    SELECT r.run_id::text, r.seed, r.arm_label, r.environment::text, r.metrics::text, r.completed_at
    FROM integration_campaign_runs r
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND ($arm_predicate)
    ORDER BY r.seed
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

  if [[ "$normalize_arm" == "true" ]]; then
    python - "$raw_dir/runs.csv" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(newline='', encoding='utf-8') as handle:
    rows = list(csv.DictReader(handle))
if not rows:
    raise SystemExit('replication development source export selected no runs')
for row in rows:
    row['arm_label'] = 'immortal_control'
with path.open('w', newline='', encoding='utf-8') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
PY
  fi

  python -m resonance_world.w4_source_export \
    "$raw_dir/runs.csv" \
    "$raw_dir/outcomes.csv" \
    "$raw_dir/tasks.csv" \
    "$raw_dir/bids.csv" \
    "$destination"
}

init_comparator_db() {
  local db_name="$1"
  local db_dsn="$2"
  psql "$DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE $db_name"
  (
    cd "$FIELD_DIR"
    RESONANCE_W9_07_COMPARATOR_DSN="$db_dsn" python - <<'PY'
import os
import psycopg
from psycopg.rows import dict_row
from resonance.experiments.runner import apply_migrations

with psycopg.connect(
    os.environ['RESONANCE_W9_07_COMPARATOR_DSN'],
    autocommit=True,
    row_factory=dict_row,
) as connection:
    apply_migrations(connection)
PY
  )
}

# Generate the entirely unseen source cohort once in this job's fresh evidence store.
(
  cd "$FIELD_DIR"
  python -m resonance.experiments.lifecycle_step_cli \
    --config "$SOURCE_CONFIG" \
    --experiment 63 \
    --code-sha "$FIELD_SHA" \
    --dsn "$DSN" \
    --output-dir "$SOURCE_STEP"
)

# Preserve the raw source export byte-for-byte as provenance evidence. The stage
# input below normalizes only run-specific public provenance hashes; scientific
# public features and all private source state remain unchanged.
export_source_rows \
  "$SOURCE_CAMPAIGN" \
  "r.arm_label = 'immortal_control'" \
  "$RAW/base" \
  "$SOURCE_RAW"
python -m resonance_world.w9_replication_source \
  --input-dir "$SOURCE_RAW" \
  --output-dir "$SOURCE"

python - <<'PY'
import json
from pathlib import Path

raw = Path('output/w9/replication/source-raw')
source = Path('output/w9/replication/source')
summary = json.loads((raw / 'w4-source-summary.json').read_text())
normalization = json.loads((source / 'w9-07-source-normalization.json').read_text())
assert summary['field_count'] == 5, summary
assert summary['agent_count'] == 60, summary
assert summary['seeds'] == [4211, 4331, 4451, 4571, 4691], summary
assert normalization['version'] == 'w9-07-semantic-public-provenance-v0.1', normalization
assert normalization['candidate_count'] == 60, normalization
assert (raw / 'capsules.private.jsonl').read_bytes() == (source / 'capsules.private.jsonl').read_bytes()
assert 'practice_by_skill' not in (source / 'candidates.jsonl').read_text()
PY

# W9-00B: independent confirmation of the discovery-frozen public estimator.
python -m resonance_world.w9_calibration_execution prepare \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$CRITICALITY_CONFIG" \
  --output "$CAL_PREDICTIONS"
python -m resonance_world.w9_calibration_execution evaluate \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$CRITICALITY_CONFIG" \
  --predictions "$CAL_PREDICTIONS" \
  --output "$CAL_RESULT"

# W9-01: frozen criticality allocation, still authorized by discovery calibration acceptance.
python -m resonance_world.w9_allocation \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$ALLOCATION_CONFIG" \
  --calibration-acceptance "$CALIBRATION_ACCEPTANCE" \
  --output "$ALLOCATION_RESULT"

# W9-02: frozen leasing schedule and one-window recovery sensitivity.
python -m resonance_world.w9_leasing \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$LEASING_CONFIG" \
  --output "$LEASING_RESULT"

# W9-03: rerun the frozen portfolio-development law and matched compute control.
python -m resonance_world.w9_portfolio_development plan \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$PORTFOLIO_CONFIG" \
  --output "$PORTFOLIO_PLAN"
python -m resonance_world.w9_portfolio_development run \
  --dsn "$DSN" \
  --source-config "$SOURCE_CONFIG" \
  --config "$PORTFOLIO_CONFIG" \
  --plan "$PORTFOLIO_PLAN" \
  --output "$PORTFOLIO_RUNS"

export_source_rows \
  "$DEVELOPMENT_CAMPAIGN" \
  "r.arm_label LIKE 'w9-compute-control-seed%'" \
  "$RAW/control" \
  "$CONTROL_SOURCE" \
  true
export_source_rows \
  "$DEVELOPMENT_CAMPAIGN" \
  "r.arm_label LIKE 'w9-portfolio-seed%'" \
  "$RAW/portfolio" \
  "$PORTFOLIO_SOURCE" \
  true

python -m resonance_world.w9_portfolio \
  --phase replication \
  --no-preparation-dir "$SOURCE" \
  --matched-control-dir "$CONTROL_SOURCE" \
  --portfolio-dir "$PORTFOLIO_SOURCE" \
  --config "$PORTFOLIO_CONFIG" \
  --output "$PORTFOLIO_RESULT"

# W9-04: frozen 2^4 factor assay. Replication K is diagnostic only; W9-05 selection is frozen.
python -m resonance_world.w9_coalition \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$COALITION_CONFIG" \
  --output "$COALITION_RESULT"

# W9-05: frozen empty selected regime plus diagnostics and a fresh W8 comparator.
init_comparator_db "$W8_STATIC_DB" "$W8_STATIC_DSN"
python -m resonance_world.w8_fastpath prepare \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$MARKET_CONFIG" \
  --output "$W8_STATIC_PLAN"
python -m resonance_world.w8_native_replacement_execution \
  --dsn "$W8_STATIC_DSN" \
  --source-config "$SOURCE_CONFIG" \
  --plan "$W8_STATIC_PLAN" \
  --campaign-config "$MARKET_CONFIG" \
  --output "$W8_STATIC_REPLACEMENT"
python -m resonance_world.w9_integrated_execution \
  --phase replication \
  --base-source-dir "$SOURCE" \
  --portfolio-source-dir "$PORTFOLIO_SOURCE" \
  --config "$MARKET_CONFIG" \
  --w8-replacement "$W8_STATIC_REPLACEMENT" \
  --output "$INTEGRATED_RESULT"

# W9-06: accepted v0.6 accounting with an independently regenerated W8 comparator.
init_comparator_db "$W8_LONG_DB" "$W8_LONG_DSN"
python -m resonance_world.w8_fastpath prepare \
  --phase replication \
  --source-dir "$SOURCE" \
  --config "$MARKET_CONFIG" \
  --output "$W8_LONG_PLAN"
python -m resonance_world.w8_native_replacement_execution \
  --dsn "$W8_LONG_DSN" \
  --source-config "$SOURCE_CONFIG" \
  --plan "$W8_LONG_PLAN" \
  --campaign-config "$MARKET_CONFIG" \
  --output "$W8_LONG_REPLACEMENT"
python -m resonance_world.w9_long_horizon_execution \
  --phase replication \
  --source-dir "$SOURCE" \
  --market-config "$MARKET_CONFIG" \
  --long-horizon-config "$LONG_CONFIG" \
  --w8-replacement "$W8_LONG_REPLACEMENT" \
  --output "$LONG_RESULT"

# Deterministic nested replication synthesis. Discovery failures remain frozen prerequisites.
python -m resonance_world.w9_replication \
  --calibration "$CAL_RESULT" \
  --allocation "$ALLOCATION_RESULT" \
  --leasing "$LEASING_RESULT" \
  --portfolio "$PORTFOLIO_RESULT" \
  --coalition "$COALITION_RESULT" \
  --integrated "$INTEGRATED_RESULT" \
  --long-horizon "$LONG_RESULT" \
  --output "$SYNTHESIS"

python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path('output/w9/replication')
paths = {
    'W9-00B': root / 'w9-00b-calibration.json',
    'W9-01': root / 'w9-01-allocation.json',
    'W9-02': root / 'w9-02-leasing.json',
    'W9-03': root / 'w9-03-portfolio.json',
    'W9-04': root / 'w9-04-coalition.json',
    'W9-05': root / 'w9-05-integrated.json',
    'W9-06': root / 'w9-06-long-horizon.json',
    'W9-07': root / 'w9-07-replication.json',
}
values = {name: json.loads(path.read_text()) for name, path in paths.items()}
assert values['W9-00B']['phase'] == 'replication'
assert values['W9-00B']['seeds'] == [4211, 4331, 4451, 4571, 4691]
for name in ('W9-01', 'W9-02', 'W9-03', 'W9-04', 'W9-05', 'W9-06'):
    assert values[name]['phase'] == 'replication', (name, values[name])
assert values['W9-05']['upstream_eligibility'] == {'C': False, 'L': False, 'P': False, 'K': []}
assert values['W9-05']['selected_mechanisms'] == []
assert values['W9-05']['structural_status'] == 'no_upstream_eligible_w9_mechanisms'
assert values['W9-06']['version'] == 'w9-06-long-horizon-result-v0.6'
assert values['W9-06']['selected_mechanisms'] == []
assert values['W9-07']['version'] == 'w9-07-replication-synthesis-v0.1'
assert values['W9-07']['selected_mechanisms'] == []
assert values['W9-07']['discovery_frozen_regime_preserved'] is True
assert values['W9-07']['nested_outcomes']['replicated_tradeoff_reduction'] is False
assert values['W9-07']['nested_outcomes']['replicated_sustainable_capability_leasing'] is False
assert values['W9-07']['nested_outcomes']['replicated_regenerative_allocation'] is False
assert 'practice_by_skill' not in json.dumps(values, sort_keys=True)

manifest = {
    'version': 'w9-07-replication-manifest-v0.1',
    'files': {
        name: {
            'path': str(path.relative_to(root)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for name, path in paths.items()
    },
}
(root / 'w9-07-manifest.json').write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + '\n',
    encoding='utf-8',
)

summary = {
    'nested_outcomes': values['W9-07']['nested_outcomes'],
    'stage_classifications': {
        'W9-00B': values['W9-00B']['calibration']['label'],
        'W9-01': values['W9-01']['classification'],
        'W9-02': values['W9-02']['classification'],
        'W9-03': values['W9-03']['classification'],
        'W9-04_K_diagnostic': values['W9-04']['K'],
        'W9-05': values['W9-05']['classification'],
        'W9-06': values['W9-06']['classification'],
    },
    'manifest': manifest,
}
print(json.dumps(summary, indent=2, sort_keys=True))
PY
