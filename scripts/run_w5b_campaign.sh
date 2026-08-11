#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
FIELD_SHA="${FIELD_SHA:-0914a21249261fe61e02c5191f4a36df416c672f}"
OUT="$ROOT/output/w5b"

mkdir -p "$OUT"

run_source_campaign() {
  local config="$1"
  local step_dir="$2"
  mkdir -p "$step_dir"
  (
    cd "$FIELD_DIR"
    python -m resonance.experiments.lifecycle_step_cli \
      --config "$ROOT/$config" \
      --experiment 63 \
      --code-sha "$FIELD_SHA" \
      --dsn "$DSN" \
      --output-dir "$step_dir"
  )
}

export_campaign() {
  local campaign="$1"
  local raw_dir="$2"
  mkdir -p "$raw_dir"

  psql "$DSN" --csv -c "
    SELECT run_id::text, seed, arm_label, environment::text, metrics::text, completed_at
    FROM integration_campaign_runs
    WHERE campaign_name = '$campaign'
      AND experiment_number = 63
      AND arm_label = 'immortal_control'
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
      AND r.arm_label = 'immortal_control'
    ORDER BY r.seed, o.cycle
  " > "$raw_dir/outcomes.csv"

  psql "$DSN" --csv -c "
    SELECT o.run_id::text, t.task_id::text, t.requester_agent_id::text
    FROM integration_campaign_outcomes o
    JOIN integration_campaign_runs r ON r.run_id = o.run_id
    JOIN market_tasks t ON t.task_id = o.task_id
    WHERE r.campaign_name = '$campaign'
      AND r.experiment_number = 63
      AND r.arm_label = 'immortal_control'
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
      AND r.arm_label = 'immortal_control'
    ORDER BY r.seed, b.task_id, b.bidder_agent_id
  " > "$raw_dir/bids.csv"
}

DISCOVERY_RAW="$OUT/discovery-raw"
DISCOVERY_SOURCE="$OUT/discovery-source"
DISCOVERY_RESULTS="$OUT/discovery"

run_source_campaign \
  "configs/w5b/source-development-discovery.json" \
  "$OUT/discovery-source-step"
export_campaign \
  "w5b-stateful-source-development-discovery-v0.1" \
  "$DISCOVERY_RAW"

python -m resonance_world.w4_source_export \
  "$DISCOVERY_RAW/runs.csv" \
  "$DISCOVERY_RAW/outcomes.csv" \
  "$DISCOVERY_RAW/tasks.csv" \
  "$DISCOVERY_RAW/bids.csv" \
  "$DISCOVERY_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(
    Path('output/w5b/discovery-source/w4-source-summary.json').read_text()
)
assert summary['field_count'] == 5, summary
assert summary['agent_count'] == 60, summary
assert summary['seeds'] == [157, 278, 399, 520, 641], summary
PY

python -m resonance_world.w5b_modules discover \
  "$DISCOVERY_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w5b/module-missions.json" \
  "$ROOT/configs/w5b/module-campaign.json" \
  "$DISCOVERY_RESULTS"

REPLICATION_RAW="$OUT/replication-raw"
REPLICATION_SOURCE="$OUT/replication-source"
REPLICATION_RESULTS="$OUT/replication"

run_source_campaign \
  "configs/w5b/source-development-replication.json" \
  "$OUT/replication-source-step"
export_campaign \
  "w5b-stateful-source-development-replication-v0.1" \
  "$REPLICATION_RAW"

python -m resonance_world.w4_source_export \
  "$REPLICATION_RAW/runs.csv" \
  "$REPLICATION_RAW/outcomes.csv" \
  "$REPLICATION_RAW/tasks.csv" \
  "$REPLICATION_RAW/bids.csv" \
  "$REPLICATION_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(
    Path('output/w5b/replication-source/w4-source-summary.json').read_text()
)
assert summary['field_count'] == 3, summary
assert summary['agent_count'] == 36, summary
assert summary['seeds'] == [762, 883, 994], summary
PY

python -m resonance_world.w5b_modules replicate \
  "$REPLICATION_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w5b/module-missions.json" \
  "$ROOT/configs/w5b/module-campaign.json" \
  "$DISCOVERY_RESULTS/w5b-discovery.json" \
  "$REPLICATION_RESULTS"

python -m resonance_world.w5b_modules synthesize \
  "$DISCOVERY_RESULTS/w5b-discovery.json" \
  "$REPLICATION_RESULTS/w5b-05-replication.json" \
  "$OUT"

python - <<'PY'
import inspect
import json
from pathlib import Path
from resonance_world.w4a_joint_learning import JointEnvironment

out = Path('output/w5b')
discovery = json.loads((out / 'discovery/w5b-discovery.json').read_text())
replication = json.loads((out / 'replication/w5b-05-replication.json').read_text())
synthesis = json.loads((out / 'w5b-synthesis.json').read_text())

assert len(discovery['field_results']) == 2
assert len(replication['field_results']) == 3
assert set(discovery['summary']) == {'w5b_01', 'w5b_02', 'w5b_03', 'w5b_04'}
assert set(replication['experiment_gates']) == {
    'w5b_01', 'w5b_02', 'w5b_03', 'w5b_04'
}
assert synthesis['status']
for row in discovery['field_results'] + replication['field_results']:
    assert row['w5b_03']['inter_module_state'] == 'absent_by_design'
    assert row['w5b_04']['fixed_agent_count'] == 6

forbidden = {
    'module', 'module_id', 'module_library', 'module_history',
    'organization', 'institutional_memory'
}
parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
assert not parameters & forbidden
PY
