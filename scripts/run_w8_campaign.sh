#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DISCOVERY_DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
REPLICATION_DSN="${DISCOVERY_DSN%/*}/resonance_w8_replication"
DISCOVERY_REPLACEMENT_DSN="${DISCOVERY_DSN%/*}/resonance_w8_replacement"
REPLICATION_REPLACEMENT_DSN="${DISCOVERY_DSN%/*}/resonance_w8_replication_replacement"
FIELD_SHA="${FIELD_SHA:-2a85739603ebac86f451b90733229782c0d45ce0}"
OUT="$ROOT/output/w8"
CONFIG="$ROOT/configs/w8/regulatory-campaign.json"

mkdir -p "$OUT"

db_name_from_dsn() {
  local dsn="$1"
  printf '%s\n' "${dsn##*/}"
}

create_database() {
  local dsn="$1"
  local name
  name="$(db_name_from_dsn "$dsn")"
  psql "$DISCOVERY_DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE $name"
}

initialize_field_database() {
  local dsn="$1"
  (
    cd "$FIELD_DIR"
    RESONANCE_W8_DSN="$dsn" python - <<'PY'
import os
import psycopg
from psycopg.rows import dict_row
from resonance.experiments.runner import apply_migrations

with psycopg.connect(
    os.environ["RESONANCE_W8_DSN"],
    autocommit=True,
    row_factory=dict_row,
) as connection:
    apply_migrations(connection)
PY
  )
}

run_source_campaign() {
  local config="$1"
  local step_dir="$2"
  local campaign_dsn="$3"
  mkdir -p "$step_dir"
  (
    cd "$FIELD_DIR"
    python -m resonance.experiments.lifecycle_step_cli \
      --config "$ROOT/$config" \
      --experiment 63 \
      --code-sha "$FIELD_SHA" \
      --dsn "$campaign_dsn" \
      --output-dir "$step_dir"
  )
}

export_campaign() {
  local campaign="$1"
  local raw_dir="$2"
  local campaign_dsn="$3"
  mkdir -p "$raw_dir"

  psql "$campaign_dsn" --csv -c "
    SELECT run_id::text, seed, arm_label, environment::text, metrics::text, completed_at
    FROM integration_campaign_runs
    WHERE campaign_name = '$campaign'
      AND experiment_number = 63
      AND arm_label = 'immortal_control'
    ORDER BY seed
  " > "$raw_dir/runs.csv"

  psql "$campaign_dsn" --csv -c "
    SELECT o.run_id::text, o.cycle, o.task_id::text, o.task_domain,
           o.required_skill, o.winner_agent_id::text, o.winner_slot,
           o.success, o.winning_price, o.task_budget, o.created_at
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND r.arm_label = 'immortal_control'
    ORDER BY r.seed, o.cycle
  " > "$raw_dir/outcomes.csv"

  psql "$campaign_dsn" --csv -c "
    SELECT o.run_id::text, t.task_id::text, t.requester_agent_id::text
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    JOIN market_tasks t ON t.task_id = o.task_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND r.arm_label = 'immortal_control'
    ORDER BY r.seed, t.task_id
  " > "$raw_dir/tasks.csv"

  psql "$campaign_dsn" --csv -c "
    SELECT o.run_id::text, b.task_id::text, b.bidder_agent_id::text,
           b.price, b.confidence, b.status
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    JOIN market_bids b ON b.task_id = o.task_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND r.arm_label = 'immortal_control'
    ORDER BY r.seed, b.task_id, b.bidder_agent_id
  " > "$raw_dir/bids.csv"
}

export_world_source() {
  local raw_dir="$1"
  local source_dir="$2"
  python -m resonance_world.w4_source_export \
    "$raw_dir/runs.csv" \
    "$raw_dir/outcomes.csv" \
    "$raw_dir/tasks.csv" \
    "$raw_dir/bids.csv" \
    "$source_dir"
}

run_replacement_assay() {
  local dsn="$1"
  local source_config="$2"
  local plan="$3"
  local output="$4"
  initialize_field_database "$dsn"
  python -m resonance_world.w8_native_replacement_execution \
    --dsn "$dsn" \
    --source-config "$ROOT/$source_config" \
    --plan "$plan" \
    --campaign-config "$CONFIG" \
    --output "$output"
}

# ---------------------------------------------------------------------------
# Discovery: all source evidence and native replacement assays exist before any
# replication database is created.
# ---------------------------------------------------------------------------
DISCOVERY_RAW="$OUT/discovery-raw"
DISCOVERY_SOURCE="$OUT/discovery-source"
DISCOVERY_PLAN="$OUT/discovery-replacement-plan.json"
DISCOVERY_REPLACEMENT="$OUT/discovery-native-replacement.json"
DISCOVERY_RESULT="$OUT/w8-discovery.json"

run_source_campaign \
  "configs/w8/source-development-discovery.json" \
  "$OUT/discovery-source-step" \
  "$DISCOVERY_DSN"
export_campaign \
  "w8-stateful-source-development-discovery-v0.1" \
  "$DISCOVERY_RAW" \
  "$DISCOVERY_DSN"
export_world_source "$DISCOVERY_RAW" "$DISCOVERY_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('output/w8/discovery-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 5, summary
assert summary['agent_count'] == 60, summary
assert summary['seeds'] == [2411, 2531, 2657, 2777, 2897], summary
PY

python -m resonance_world.w8_execution prepare \
  --phase discovery \
  --source-dir "$DISCOVERY_SOURCE" \
  --config "$CONFIG" \
  --output "$DISCOVERY_PLAN"

create_database "$DISCOVERY_REPLACEMENT_DSN"
run_replacement_assay \
  "$DISCOVERY_REPLACEMENT_DSN" \
  "configs/w8/source-development-discovery.json" \
  "$DISCOVERY_PLAN" \
  "$DISCOVERY_REPLACEMENT"

python -m resonance_world.w8_execution phase \
  --phase discovery \
  --source-dir "$DISCOVERY_SOURCE" \
  --config "$CONFIG" \
  --replacement "$DISCOVERY_REPLACEMENT" \
  --output "$DISCOVERY_RESULT"

# ---------------------------------------------------------------------------
# W8-07: source and replacement evidence are generated only after discovery.
# Separate PostgreSQL stores prevent source/replication contamination.
# ---------------------------------------------------------------------------
create_database "$REPLICATION_DSN"
REPLICATION_RAW="$OUT/replication-raw"
REPLICATION_SOURCE="$OUT/replication-source"
REPLICATION_PLAN="$OUT/replication-replacement-plan.json"
REPLICATION_REPLACEMENT="$OUT/replication-native-replacement.json"
REPLICATION_RESULT="$OUT/w8-07-replication.json"

run_source_campaign \
  "configs/w8/source-development-replication.json" \
  "$OUT/replication-source-step" \
  "$REPLICATION_DSN"
export_campaign \
  "w8-stateful-source-development-replication-v0.1" \
  "$REPLICATION_RAW" \
  "$REPLICATION_DSN"
export_world_source "$REPLICATION_RAW" "$REPLICATION_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('output/w8/replication-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 5, summary
assert summary['agent_count'] == 60, summary
assert summary['seeds'] == [3011, 3137, 3253, 3373, 3491], summary
PY

python -m resonance_world.w8_execution prepare \
  --phase replication \
  --source-dir "$REPLICATION_SOURCE" \
  --config "$CONFIG" \
  --output "$REPLICATION_PLAN"

create_database "$REPLICATION_REPLACEMENT_DSN"
run_replacement_assay \
  "$REPLICATION_REPLACEMENT_DSN" \
  "configs/w8/source-development-replication.json" \
  "$REPLICATION_PLAN" \
  "$REPLICATION_REPLACEMENT"

python -m resonance_world.w8_execution phase \
  --phase replication \
  --source-dir "$REPLICATION_SOURCE" \
  --config "$CONFIG" \
  --replacement "$REPLICATION_REPLACEMENT" \
  --output "$REPLICATION_RESULT"

python -m resonance_world.w8_execution synthesize \
  --discovery "$DISCOVERY_RESULT" \
  --replication "$REPLICATION_RESULT" \
  --output "$OUT/w8-synthesis.json"

python - <<'PY'
import inspect
import json
from pathlib import Path

from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w8_regulation import RegulatoryCharter

out = Path('output/w8')
discovery = json.loads((out / 'w8-discovery.json').read_text())
replication = json.loads((out / 'w8-07-replication.json').read_text())
synthesis = json.loads((out / 'w8-synthesis.json').read_text())

for phase in (discovery, replication):
    assert phase['field_count'] == 5
    assert phase['agent_count'] == 60
    assert phase['field_sha'] == '2a85739603ebac86f451b90733229782c0d45ce0'
    assert set(phase) >= {
        'w8_01_source_reserve',
        'w8_02_circulation',
        'w8_03_replacement',
        'w8_04_coalitions',
        'w8_05_integrated_charter',
        'w8_06_long_horizon',
    }
    assert len(phase['w8_04_coalitions']['mission_results']) == 6
    assert phase['w8_06_long_horizon']['neutral']['budget_mode'] == 'neutral'
    assert phase['w8_06_long_horizon']['compounding']['budget_mode'] == 'compounding'
    assert len(phase['w8_06_long_horizon']['neutral']['capability_stock_series']) == 24

assert synthesis['status'] in {
    'replicated_generative_circulation',
    'replicated_sustainable_circulation',
    'replicated_regulatory_null_or_negative',
    'w8_discovery_not_replicated',
}

forbidden = {
    'budget', 'charter', 'coalition', 'contract', 'dividend',
    'price', 'regulation', 'reserve'
}
assert not set(inspect.signature(JointEnvironment.evaluate).parameters) & forbidden
assert 'practice_by_skill' not in inspect.signature(RegulatoryCharter).parameters
PY
