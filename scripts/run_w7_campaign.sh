#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
FIELD_DIR="${FIELD_DIR:-$ROOT/../field}"
DISCOVERY_DSN="${DSN:-postgresql://resonance:resonance@localhost:5432/resonance}"
REPLICATION_DSN="${DISCOVERY_DSN%/*}/resonance_replication"
FIELD_SHA="${FIELD_SHA:-0914a21249261fe61e02c5191f4a36df416c672f}"
OUT="$ROOT/output/w7"

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
  "configs/w7/source-development-discovery.json" \
  "$OUT/discovery-source-step" \
  "$DISCOVERY_DSN"
export_campaign \
  "w7-stateful-source-development-discovery-v0.1" \
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
summary = json.loads(Path('output/w7/discovery-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 3, summary
assert summary['agent_count'] == 36, summary
assert summary['seeds'] == [1663, 1789, 1913], summary
PY

python -m resonance_world.w7_campaign discover \
  "$DISCOVERY_SOURCE/candidates.jsonl" \
  "$DISCOVERY_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w7/competition-campaign.json" \
  "$DISCOVERY_RESULTS"

# W7-07 populations are generated only after discovery and in a fresh evidence
# store. No replication Field can inherit source rows or constraints from discovery.
psql "$DISCOVERY_DSN" -v ON_ERROR_STOP=1 -c "CREATE DATABASE resonance_replication"

REPLICATION_RAW="$OUT/replication-raw"
REPLICATION_SOURCE="$OUT/replication-source"
REPLICATION_RESULTS="$OUT/replication"

run_source_campaign \
  "configs/w7/source-development-replication.json" \
  "$OUT/replication-source-step" \
  "$REPLICATION_DSN"
export_campaign \
  "w7-stateful-source-development-replication-v0.1" \
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
summary = json.loads(Path('output/w7/replication-source/w4-source-summary.json').read_text())
assert summary['field_count'] == 3, summary
assert summary['agent_count'] == 36, summary
assert summary['seeds'] == [2039, 2161, 2287], summary
PY

python -m resonance_world.w7_campaign replicate \
  "$REPLICATION_SOURCE/candidates.jsonl" \
  "$REPLICATION_SOURCE/capsules.private.jsonl" \
  "$ROOT/configs/w7/competition-campaign.json" \
  "$REPLICATION_RESULTS"

python -m resonance_world.w7_campaign synthesize \
  "$DISCOVERY_RESULTS/w7-discovery.json" \
  "$REPLICATION_RESULTS/w7-07-replication.json" \
  "$ROOT/configs/w7/competition-campaign.json" \
  "$OUT"

python - <<'PY'
import inspect
import json
from pathlib import Path

from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w7_competition import TalentOffer

out = Path('output/w7')
discovery = json.loads((out / 'discovery/w7-discovery.json').read_text())
replication = json.loads((out / 'replication/w7-07-replication.json').read_text())
synthesis = json.loads((out / 'w7-synthesis.json').read_text())

for phase in (discovery, replication):
    assert phase['field_count'] == 3
    assert phase['population_count'] == 36
    assert len(phase['w7_01']['organization_results']) == 3
    assert len(phase['w7_04']['field_results']) == 3
    assert len(phase['w7_05']['coalition_results']) == 3
    assert len(phase['w7_06']['mission_results']) == 3
    assert phase['w7_01']['classification'] in {'positive', 'null', 'negative'}
    assert phase['w7_04']['classification'] in {'positive', 'null', 'negative'}
    assert phase['w7_05']['classification'] in {'positive', 'null', 'negative'}

assert synthesis['status'] in {
    'w7_primary_classifications_replicated',
    'w7_discovery_not_replicated',
}

forbidden = {
    'bid', 'budget', 'coalition', 'competition', 'contract',
    'market', 'organization_count', 'price', 'rival'
}
assert not set(inspect.signature(JointEnvironment.evaluate).parameters) & forbidden
assert 'practice_by_skill' not in inspect.signature(TalentOffer).parameters
PY
