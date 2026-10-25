from __future__ import annotations

import sqlite3

import pytest

from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.replay import replay_branch
from resonance_world.experimental_runtime.scenario import (
    ScriptedPolicy,
    build_machine,
    drive,
    start_kernel,
)
from resonance_world.experimental_runtime.store import KernelStore

# Fixed commitment key so file-backed stores can be reopened for tamper tests.
TEST_KEY = bytes(range(16, 48))


def captured_world(
    store_path: str | None = None,
) -> tuple[KernelStore, WorldKernel, ScriptedPolicy]:
    store = KernelStore(store_path, commitment_key=TEST_KEY)
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=40, policy=policy)
    kernel.checkpoint("cp-40")
    return store, kernel, policy


def test_replay_reproduces_the_captured_world_exactly() -> None:
    store, kernel, policy = captured_world()
    capture_hash = kernel.state_hash()

    result = replay_branch(store, "main", build_machine())
    assert result.final_state_sha256 == capture_hash
    assert result.final_public_state_sha256 == kernel.public_state_hash()
    assert result.recorded_agent_decisions == policy.calls
    assert result.all_checkpoints_matched
    assert [item.matched for item in result.checkpoint_verifications] == [True]


def test_replay_never_invokes_the_decision_policy() -> None:
    store, kernel, policy = captured_world()
    calls_before = policy.calls

    replay_branch(store, "main", build_machine())

    assert policy.calls == calls_before


def test_replay_detects_event_payload_tampering(tmp_path) -> None:
    store_path = tmp_path / "world.sqlite3"
    store, _kernel, _policy = captured_world(str(store_path))
    store.close()

    connection = sqlite3.connect(str(store_path))
    connection.execute(
        "UPDATE events SET payload = ? WHERE kind = 'world_effect' AND seq = "
        "(SELECT MIN(seq) FROM events WHERE kind = 'world_effect')",
        ('{"tick": 999999}',),
    )
    connection.commit()
    connection.close()

    reopened = KernelStore(store_path, commitment_key=TEST_KEY)
    with pytest.raises(ValueError, match="digest mismatch"):
        replay_branch(reopened, "main", build_machine())


def test_replay_detects_sealed_payload_tampering(tmp_path) -> None:
    store_path = tmp_path / "world.sqlite3"
    store = KernelStore(store_path, commitment_key=TEST_KEY)
    kernel = start_kernel(store)
    drive(kernel, ticks=100, policy=ScriptedPolicy())
    store.close()

    connection = sqlite3.connect(str(store_path))
    row = connection.execute(
        "SELECT seq FROM sealed_payloads ORDER BY seq LIMIT 1"
    ).fetchone()
    assert row is not None
    connection.execute(
        "UPDATE sealed_payloads SET payload = ? WHERE seq = ?",
        ('{"epoch": 1, "stress": 0}', row[0]),
    )
    connection.commit()
    connection.close()

    reopened = KernelStore(store_path, commitment_key=TEST_KEY)
    with pytest.raises(ValueError, match="digest mismatch"):
        replay_branch(reopened, "main", build_machine())


def test_replay_detects_event_record_field_tampering(tmp_path) -> None:
    store_path = tmp_path / "world.sqlite3"
    store, _kernel, _policy = captured_world(str(store_path))
    store.close()

    connection = sqlite3.connect(str(store_path))
    connection.execute("UPDATE events SET tick = tick + 1 WHERE seq = 1")
    connection.commit()
    connection.close()

    reopened = KernelStore(store_path, commitment_key=TEST_KEY)
    with pytest.raises(ValueError, match="content digest"):
        replay_branch(reopened, "main", build_machine())


def test_replay_covers_every_checkpoint_watermark() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=40, policy=policy, checkpoint_ticks=(20, 40))

    result = replay_branch(store, "main", build_machine())
    assert len(result.checkpoint_verifications) == 2
    assert [item.event_count for item in result.checkpoint_verifications] == sorted(
        item.event_count for item in result.checkpoint_verifications
    )
    assert result.all_checkpoints_matched


def test_replay_requires_the_same_reducer_registry() -> None:
    from resonance_world.experimental_runtime.machine import StateMachine

    store, _kernel, _policy = captured_world()
    empty = StateMachine()
    empty.register("tick", lambda state, event, sealed: state)
    with pytest.raises(ValueError, match="fingerprint"):
        replay_branch(store, "main", empty)
