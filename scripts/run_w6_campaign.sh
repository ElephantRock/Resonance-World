#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DISCOVERY_DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
REPLICATION_DSN="${DISCOVERY_DSN%/*}/resonance_replication"
FIELD_SHA="${FIELD_SHA:-0914a21249261fe61e02c5191f4a36df416c672f}"
OUT="$ROOT/output/w6"

mkdir -p "$OUT"

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

DISCOVERY_RAW="$OUT/discovery-raw"
DISCOVERY_SOURCE="$OUT/discovery-source"
DISCOVERY_RESULTS="$OUT/discovery"

run_source_campaign \
  "configs/w6/source-development-discovery.json" \
  "$OUT/discovery-source-step" \
  "$DISCOVERY_DSN"
export_campaign \
  "w6-stateful-source-development-discovery-v0.1" \
  "$DISCOVERY_RAW" \
  "$DISCOVERY_DSN"

python -m resonance_world.w4_source_export \
  "$DISCOVERY_RAW/runs.csv" \
  "$DISCOVERY_RAW/outcomes.csv" \
  "$DISCOVERY_RAW/tasks.csv" \
  "$DISCOVERY_RAW/bids.csv" \
  "$DISCOVERY_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('output/w6/discovery-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 6, summary
assert summary['agent_count'] == 72, summary
assert summary['seeds'] == [191, 313, 437, 559, 683, 809], summary
PY

python -m resonance_world.w6_mobility_campaign discover \
  "$DISCOVERY_SOURCE/candidates.jsonl" \
  "$DISCOVERY_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w6/mobility-campaign.json" \
  "$DISCOVERY_RESULTS"

# The replication population is generated only after discovery and in a fresh
# PostgreSQL evidence store, so it cannot inherit rows or constraints from discovery.
psql "$DISCOVERY_DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE resonance_replication"

REPLICATION_RAW="$OUT/replication-raw"
REPLICATION_SOURCE="$OUT/replication-source"
REPLICATION_RESULTS="$OUT/replication"

run_source_campaign \
  "configs/w6/source-development-replication.json" \
  "$OUT/replication-source-step" \
  "$REPLICATION_DSN"
export_campaign \
  "w6-stateful-source-development-replication-v0.1" \
  "$REPLICATION_RAW" \
  "$REPLICATION_DSN"

python -m resonance_world.w4_source_export \
  "$REPLICATION_RAW/runs.csv" \
  "$REPLICATION_RAW/outcomes.csv" \
  "$REPLICATION_RAW/tasks.csv" \
  "$REPLICATION_RAW/bids.csv" \
  "$REPLICATION_SOURCE"

python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('output/w6/replication-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 6, summary
assert summary['agent_count'] == 72, summary
assert summary['seeds'] == [929, 1051, 1177, 1301, 1423, 1549], summary
PY

python -m resonance_world.w6_mobility_campaign replicate \
  "$REPLICATION_SOURCE/candidates.jsonl" \
  "$REPLICATION_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w6/mobility-campaign.json" \
  "$DISCOVERY_RESULTS/w6-discovery.json" \
  "$REPLICATION_RESULTS"

python -m resonance_world.w6_mobility_campaign synthesize \
  "$DISCOVERY_RESULTS/w6-discovery.json" \
  "$REPLICATION_RESULTS/w6-07-replication.json" \
  "$OUT"

python - <<'PY'
import inspect
import json
from pathlib import Path
from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w6_mobility_campaign import _expected_probability

out = Path('output/w6')
discovery = json.loads((out / 'discovery/w6-discovery.json').read_text())
replication = json.loads((out / 'replication/w6-07-replication.json').read_text())
synthesis = json.loads((out / 'w6-synthesis.json').read_text())
assert len(discovery['routes']) == 3
assert len(replication['routes']) == 3
assert discovery['summary']['w6_02']['exact_mode_parity'] is True
assert replication['summary']['w6_02']['exact_mode_parity'] is True
assert synthesis['status']
for route in discovery['routes'] + replication['routes']:
    assert route['w6_01']['mobility_event']['state_before_sha256'] == route['w6_01']['mobility_event']['state_after_sha256']
    assert route['w6_04']['discard_state_before_sha256'] == route['w6_04']['discard_state_after_sha256']
    assert route['w6_04']['learned_state_before_sha256'] != route['w6_04']['learned_state_after_sha256']

forbidden = {
    'mobility_mode', 'current_field_id', 'home_affiliation',
    'migration_history', 'time_away', 'module_id', 'organization_memory'
}
assert not set(inspect.signature(_expected_probability).parameters) & forbidden
assert not set(inspect.signature(JointEnvironment.evaluate).parameters) & forbidden
PY
