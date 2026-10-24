from __future__ import annotations

import time

import pytest

from resonance_world.experimental_runtime.scenario import run_acceptance


@pytest.fixture(scope="module")
def report() -> object:
    return run_acceptance(ticks=1000)


def test_acceptance_runs_1000_virtual_ticks(report) -> None:
    assert report.ticks == 1000
    assert report.event_count > 1000


def test_acceptance_creates_four_isolated_branches(report) -> None:
    assert report.branch_ids == ("branch-1", "branch-2", "branch-3", "branch-4")
    assert len(report.branch_summaries) == 4
    for summary in report.branch_summaries:
        assert summary.matches_capture, summary
        assert summary.all_checkpoints_matched, summary


def test_acceptance_replay_reproduces_identical_state_hashes(report) -> None:
    assert report.capture_state_sha256 == report.replay_state_sha256
    assert report.capture_public_state_sha256 == report.replay_public_state_sha256


def test_acceptance_checkpoints_survive_replay(report) -> None:
    assert report.replay_checkpoint_matches == 2


def test_acceptance_records_decisions_without_model_calls(report) -> None:
    assert report.capture_agent_decisions == report.replay_recorded_agent_decisions
    assert report.capture_agent_decisions > 0
    assert report.policy_invocations == report.capture_agent_decisions


def test_acceptance_checkpoint_transparency(report) -> None:
    assert report.checkpoint_transparency_verified is True
    assert report.checkpoint_restore_tick == 400


def test_acceptance_completes_promptly() -> None:
    started = time.perf_counter()
    run_acceptance(ticks=1000)
    elapsed = time.perf_counter() - started
    assert elapsed < 60.0


def test_acceptance_rejects_too_few_ticks() -> None:
    with pytest.raises(ValueError, match="at least 200"):
        run_acceptance(ticks=10)
