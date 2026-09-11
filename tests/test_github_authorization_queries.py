from __future__ import annotations

import json
import subprocess

import pytest

from resonance_world.github_authorization_queries import (
    AuthorizationQueryError,
    count_exact_candidate_reviews,
    count_prior_workflow_runs,
    count_unresolved_review_threads,
    fetch_review_threads,
    fetch_reviews,
    fetch_workflow_runs,
)

CANDIDATE = "a" * 40


def _capture_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[str]]:
    captured: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return captured


def test_count_prior_workflow_runs_across_pages() -> None:
    payload = json.dumps(
        [
            {"workflow_runs": [{"id": 10}, {"id": 11}]},
            {"workflow_runs": [{"id": "12"}, {"id": 13}]},
        ]
    )
    assert count_prior_workflow_runs(payload, exclude_run_id="12") == 3


def test_workflow_runs_fail_closed_on_malformed_shape() -> None:
    with pytest.raises(AuthorizationQueryError, match="workflow_runs"):
        count_prior_workflow_runs(json.dumps([{"workflow_runs": {}}]), exclude_run_id="1")


def test_count_exact_candidate_reviews_accepts_codex_and_operator() -> None:
    payload = json.dumps(
        [
            [
                {
                    "commit_id": CANDIDATE,
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                    "body": "blocking text is interpreted separately by thread cleanliness",
                },
                {
                    "commit_id": CANDIDATE,
                    "user": {"login": "Alajmah"},
                    "body": (
                        "Autonomous-Operator-Exact-Head-Review: PASS\n"
                        f"candidate_sha={CANDIDATE}"
                    ),
                },
                {
                    "commit_id": "b" * 40,
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                    "body": "older head",
                },
            ],
            [],
        ]
    )
    assert (
        count_exact_candidate_reviews(
            payload,
            candidate_sha=CANDIDATE,
            codex_login="chatgpt-codex-connector[bot]",
            operator_login="Alajmah",
            operator_pass_marker="Autonomous-Operator-Exact-Head-Review: PASS",
        )
        == 2
    )


def test_operator_review_requires_candidate_binding_and_pass_marker() -> None:
    payload = json.dumps(
        [
            [
                {
                    "commit_id": CANDIDATE,
                    "user": {"login": "Alajmah"},
                    "body": "Autonomous-Operator-Exact-Head-Review: PASS",
                },
                {
                    "commit_id": CANDIDATE,
                    "user": {"login": "Alajmah"},
                    "body": f"candidate_sha={CANDIDATE}",
                },
            ]
        ]
    )
    assert (
        count_exact_candidate_reviews(
            payload,
            candidate_sha=CANDIDATE,
            codex_login="chatgpt-codex-connector[bot]",
            operator_login="Alajmah",
            operator_pass_marker="Autonomous-Operator-Exact-Head-Review: PASS",
        )
        == 0
    )


def test_count_unresolved_review_threads_across_graphql_pages() -> None:
    def page(nodes: list[dict[str, bool]], has_next_page: bool) -> dict[str, object]:
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": nodes,
                            "pageInfo": {
                                "hasNextPage": has_next_page,
                                "endCursor": "cursor" if has_next_page else None,
                            },
                        }
                    }
                }
            }
        }

    payload = json.dumps(
        [
            page([{"isResolved": True}, {"isResolved": False}], True),
            page([{"isResolved": False}], False),
        ]
    )
    assert count_unresolved_review_threads(payload) == 2


def test_review_threads_fail_closed_on_non_boolean_resolution() -> None:
    payload = json.dumps(
        [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [{"isResolved": "false"}],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            }
                        }
                    }
                }
            }
        ]
    )
    with pytest.raises(AuthorizationQueryError, match="must be boolean"):
        count_unresolved_review_threads(payload)


def test_fetch_workflow_runs_uses_slurp_without_formatting_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_subprocess(monkeypatch)

    assert fetch_workflow_runs(repository="ElephantRock/Resonance-World", workflow="ci.yml") == "[]"
    command = captured[0]
    assert command == [
        "gh",
        "api",
        "--paginate",
        "--slurp",
        "/repos/ElephantRock/Resonance-World/actions/workflows/ci.yml/runs?per_page=100",
    ]
    assert "--jq" not in command
    assert "--template" not in command


def test_fetch_reviews_uses_slurp_without_formatting_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_subprocess(monkeypatch)

    assert fetch_reviews(repository="ElephantRock/Resonance-World", pull_request=248) == "[]"
    command = captured[0]
    assert command[-1] == "/repos/ElephantRock/Resonance-World/pulls/248/reviews?per_page=100"
    assert "--slurp" in command
    assert "--jq" not in command


def test_fetch_review_threads_uses_graphql_slurp_without_formatting_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_subprocess(monkeypatch)

    assert fetch_review_threads(repository="ElephantRock/Resonance-World", pull_request=248) == "[]"
    command = captured[0]
    assert command[:5] == ["gh", "api", "graphql", "--paginate", "--slurp"]
    assert "--jq" not in command
    assert "--template" not in command
