"""Fail-closed role and peer-validation tests for offline three-UID fixture."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

import pytest

from resonance_world.c3r_g1_crossed_uid_client import _connect, _send, run_fixture
from resonance_world.c3r_g1_crossed_uid_service import serve_fixture


def test_invalid_worker_role_or_unpinned_uid_fails_before_socket(tmp_path) -> None:
    target = tmp_path / "service.sock"
    for role, peer_uid in (("anything", 10001), ("evaluator", 0),
                           ("custodian", -1), ("custodian", True)):
        with pytest.raises(ValueError):
            serve_fixture(path=target, peer_uid=peer_uid, role=role, arguments=[])
    assert not target.exists()


def test_relative_socket_and_root_server_do_not_bind(tmp_path) -> None:
    with pytest.raises(ValueError):
        serve_fixture(path=Path("relative.sock"), peer_uid=10001,
                      role="evaluator", arguments=[])
    # The production socket requires an owner-matching nonroot caller.
    # Fixture itself does not weaken production's nonroot requirement.
    path = tmp_path / "service.sock"
    if os.geteuid() == 0:
        with pytest.raises(ValueError, match="nonroot owner"):
            serve_fixture(path=path, peer_uid=10001,
                          role="evaluator", arguments=[])


def test_fake_path_or_wrong_uid_is_rejected_without_connect(tmp_path) -> None:
    path = tmp_path / "fake.socket"
    path.write_text("not a socket")
    with pytest.raises(ValueError, match="not owned"):
        _connect(path, expected_server_uid=10001)
    link = tmp_path / "linked.socket"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        _connect(link, expected_server_uid=10001)
    with pytest.raises(ValueError):
        _connect(path, expected_server_uid=0)


def test_aliasing_agent_and_evaluator_uid_blocks_run_before_network(tmp_path) -> None:
    with pytest.raises(ValueError, match="three different"):
        run_fixture(
            evaluator_socket=tmp_path / "none", custodian_socket=tmp_path / "none2",
            evaluator_uid=os.geteuid(), custodian_uid=65000,
            evaluator_public_key_hex="", custodian_public_key_hex="",
            run_id="local-dummy-20261022",
        )


def test_socket_protocol_rejects_non_object_reply() -> None:
    for payload in ("[]\n", '"string"\n', "\n"):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _send(StringIO(payload), StringIO(), {"op": "untrusted"})
