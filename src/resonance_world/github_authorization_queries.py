"""Fail-closed GitHub authorization queries for one-shot workflow gates.

The hosted GitHub CLI currently rejects combining ``gh api --slurp`` with
``--jq``/``--template``.  This module deliberately keeps pagination/retrieval
and JSON interpretation separate: ``gh`` returns the complete slurped payload,
then Python validates and interprets it locally.

No external model-provider credentials are used by this module.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from typing import Any


class AuthorizationQueryError(RuntimeError):
    """Raised when an authorization query cannot be interpreted safely."""


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

THREAD_QUERY = """query(
  $owner: String!,
  $name: String!,
  $number: Int!,
  $endCursor: String
) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        nodes {
          isResolved
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}"""


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuthorizationQueryError("GitHub API output is not valid JSON") from exc


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuthorizationQueryError(f"{label} must be a JSON array")
    return value


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorizationQueryError(f"{label} must be a JSON object")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise AuthorizationQueryError(f"{label} must be boolean")
    return value


def _slurped_pages(text: str) -> list[Any]:
    return _require_list(_load_json(text), "slurped GitHub API payload")


def count_prior_workflow_runs(text: str, *, exclude_run_id: str) -> int:
    """Count workflow runs across all slurped REST pages except one run id."""

    count = 0
    for page_index, page_value in enumerate(_slurped_pages(text)):
        page = _require_dict(page_value, f"workflow-runs page {page_index}")
        runs = _require_list(
            page.get("workflow_runs"),
            f"workflow-runs page {page_index}.workflow_runs",
        )
        for run_index, run_value in enumerate(runs):
            run = _require_dict(
                run_value,
                f"workflow-runs page {page_index} row {run_index}",
            )
            run_id = run.get("id")
            if not isinstance(run_id, (int, str)) or isinstance(run_id, bool):
                raise AuthorizationQueryError("workflow run id must be int or string")
            if str(run_id) != str(exclude_run_id):
                count += 1
    return count


def count_exact_candidate_reviews(
    text: str,
    *,
    candidate_sha: str,
    codex_login: str,
    operator_login: str,
    operator_pass_marker: str,
) -> int:
    """Count accepted exact-candidate reviews across all slurped REST pages."""

    count = 0
    expected_sha_marker = f"candidate_sha={candidate_sha}"
    for page_index, page_value in enumerate(_slurped_pages(text)):
        reviews = _require_list(page_value, f"reviews page {page_index}")
        for review_index, review_value in enumerate(reviews):
            review = _require_dict(
                review_value,
                f"reviews page {page_index} row {review_index}",
            )
            commit_id = review.get("commit_id")
            if commit_id is not None and not isinstance(commit_id, str):
                raise AuthorizationQueryError("review commit_id must be string or null")
            user = _require_dict(review.get("user"), "review user")
            login = user.get("login")
            if not isinstance(login, str):
                raise AuthorizationQueryError("review user.login must be string")
            body = review.get("body")
            if body is None:
                body = ""
            if not isinstance(body, str):
                raise AuthorizationQueryError("review body must be string or null")
            if commit_id != candidate_sha:
                continue
            if login == codex_login:
                count += 1
                continue
            if (
                login == operator_login
                and operator_pass_marker in body
                and expected_sha_marker in body
            ):
                count += 1
    return count


def count_unresolved_review_threads(text: str) -> int:
    """Count unresolved PR review threads across slurped GraphQL pages."""

    count = 0
    for page_index, page_value in enumerate(_slurped_pages(text)):
        page = _require_dict(page_value, f"GraphQL page {page_index}")
        data = _require_dict(page.get("data"), f"GraphQL page {page_index}.data")
        repository = _require_dict(data.get("repository"), "GraphQL repository")
        pull_request = _require_dict(
            repository.get("pullRequest"),
            "GraphQL pullRequest",
        )
        threads = _require_dict(
            pull_request.get("reviewThreads"),
            "GraphQL reviewThreads",
        )
        nodes = _require_list(threads.get("nodes"), "GraphQL reviewThreads.nodes")
        page_info = _require_dict(
            threads.get("pageInfo"),
            "GraphQL reviewThreads.pageInfo",
        )
        _require_bool(page_info.get("hasNextPage"), "GraphQL pageInfo.hasNextPage")
        end_cursor = page_info.get("endCursor")
        if end_cursor is not None and not isinstance(end_cursor, str):
            raise AuthorizationQueryError("GraphQL pageInfo.endCursor must be string or null")
        for node_index, node_value in enumerate(nodes):
            node = _require_dict(node_value, f"review thread {node_index}")
            is_resolved = _require_bool(
                node.get("isResolved"),
                f"review thread {node_index}.isResolved",
            )
            if not is_resolved:
                count += 1
    return count


def _run_gh(arguments: Sequence[str]) -> str:
    command = ["gh", "api", *arguments]
    if "--jq" in command or "-q" in command or "--template" in command or "-t" in command:
        raise AuthorizationQueryError("formatting flags are forbidden in paginated gh retrieval")
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AuthorizationQueryError(f"GitHub API command failed: {command!r}") from exc
    return completed.stdout


def fetch_workflow_runs(*, repository: str, workflow: str) -> str:
    _validate_repository(repository)
    if not _WORKFLOW_RE.fullmatch(workflow):
        raise AuthorizationQueryError("workflow filename contains unsupported characters")
    endpoint = f"/repos/{repository}/actions/workflows/{workflow}/runs?per_page=100"
    return _run_gh(["--paginate", "--slurp", endpoint])


def fetch_reviews(*, repository: str, pull_request: int) -> str:
    _validate_repository(repository)
    _validate_pull_request(pull_request)
    endpoint = f"/repos/{repository}/pulls/{pull_request}/reviews?per_page=100"
    return _run_gh(["--paginate", "--slurp", endpoint])


def fetch_review_threads(*, repository: str, pull_request: int) -> str:
    _validate_repository(repository)
    _validate_pull_request(pull_request)
    owner, name = repository.split("/", 1)
    return _run_gh(
        [
            "graphql",
            "--paginate",
            "--slurp",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pull_request}",
            "-f",
            f"query={THREAD_QUERY}",
        ]
    )


def _validate_repository(repository: str) -> None:
    if not _REPOSITORY_RE.fullmatch(repository):
        raise AuthorizationQueryError("repository must have owner/name form")


def _validate_pull_request(pull_request: int) -> None:
    if pull_request <= 0:
        raise AuthorizationQueryError("pull-request number must be positive")


def _validate_sha(candidate_sha: str) -> None:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise AuthorizationQueryError("candidate SHA must be 40 lowercase hex characters")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    workflow = subparsers.add_parser("workflow-runs")
    workflow.add_argument("--repository", required=True)
    workflow.add_argument("--workflow", required=True)
    workflow.add_argument("--exclude-run-id", required=True)

    reviews = subparsers.add_parser("reviews")
    reviews.add_argument("--repository", required=True)
    reviews.add_argument("--pull-request", type=int, required=True)
    reviews.add_argument("--candidate-sha", required=True)
    reviews.add_argument(
        "--codex-login",
        default="chatgpt-codex-connector[bot]",
    )
    reviews.add_argument("--operator-login", default="Alajmah")
    reviews.add_argument(
        "--operator-pass-marker",
        default="Autonomous-Operator-Exact-Head-Review: PASS",
    )

    threads = subparsers.add_parser("threads")
    threads.add_argument("--repository", required=True)
    threads.add_argument("--pull-request", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "workflow-runs":
            raw = fetch_workflow_runs(repository=args.repository, workflow=args.workflow)
            result = count_prior_workflow_runs(raw, exclude_run_id=args.exclude_run_id)
        elif args.command == "reviews":
            _validate_sha(args.candidate_sha)
            raw = fetch_reviews(
                repository=args.repository,
                pull_request=args.pull_request,
            )
            result = count_exact_candidate_reviews(
                raw,
                candidate_sha=args.candidate_sha,
                codex_login=args.codex_login,
                operator_login=args.operator_login,
                operator_pass_marker=args.operator_pass_marker,
            )
        elif args.command == "threads":
            raw = fetch_review_threads(
                repository=args.repository,
                pull_request=args.pull_request,
            )
            result = count_unresolved_review_threads(raw)
        else:  # pragma: no cover - argparse enforces the command set.
            raise AuthorizationQueryError("unknown command")
    except AuthorizationQueryError as exc:
        print(f"authorization-query error: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
