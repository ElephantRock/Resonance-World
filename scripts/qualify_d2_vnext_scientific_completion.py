#!/usr/bin/env python3
"""Engineering-only D2-shaped Hermes/Coding Plan completion qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import qualify_d2_coding_plan_hermes as base  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_vnext_scientific_completion"
PLAN = DIR / "D2_VNEXT_SCIENTIFIC_COMPLETION_REQUEST_PLAN.json"
TOPOLOGY = DIR / "D2_VNEXT_SCIENTIFIC_COMPLETION_TOPOLOGY.json"
MARKER = DIR / "RUN_D2_VNEXT_SCIENTIFIC_COMPLETION_QUALIFICATION"

ISSUE = 223
MODEL = "glm-5.3"
TEMPERATURE = 0.8
THINKING = {"type": "disabled"}
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
SHAPES = (
    "fresh_evaluation",
    "developed_development",
    "developed_evaluation",
    "oracle_evaluation",
)
PROFILES = (
    {"name": "iterations2_tokens768", "max_iterations": 2, "max_tokens": 768},
    {"name": "iterations2_tokens1024", "max_iterations": 2, "max_tokens": 1024},
    {"name": "iterations3_tokens1024", "max_iterations": 3, "max_tokens": 1024},
)
TRAJECTORIES = ("schema_like_0", "schema_like_1", "schema_like_2", "schema_like_3")
PROFILE_CALLS = 12
TRAJECTORY_CALLS_EACH = 55
TRAJECTORY_CALLS = 220
MAX_LOGICAL_CALLS = 232
MAX_SENDS_PER_LOGICAL = 54
MAX_SENDS_TOTAL = 400
MAX_TRAJECTORY_CONCURRENCY = 4
AUTH_ENV = "D2_VNEXT_SCIENTIFIC_COMPLETION_AUTHORIZED"
AUTH_STRING = "D2_vNext_scientific_completion_engineering_execution_explicitly_authorized"
ALLOWED_URL = base.BASE_URL.rstrip("/") + "/"


class PhysicalSendBudgetExceeded(RuntimeError):
    pass


class UnexpectedOutboundRequest(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text())


def validate_plan(p: dict[str, Any]) -> None:
    expected = {
        "schema": "d2-vnext-scientific-completion-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "hermes_repository": "hermes-agent-org/hermes",
        "hermes_revision": base.HERMES_REVISION,
        "hermes_package_version": base.HERMES_VERSION,
        "hermes_run_agent_blob_sha": base.HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": base.OPENAI_VERSION,
        "openai_sdk_default_max_retries": base.OPENAI_DEFAULT_MAX_RETRIES,
        "httpx_version": base.HTTPX_VERSION,
        "endpoint_base_url": base.BASE_URL,
        "provider_id": base.PROVIDER,
        "provider_base_url_env_var": "GLM_BASE_URL",
        "credential_env_var": "ZAI_API_KEY",
        "api_mode": base.API_MODE,
        "requested_model": MODEL,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "enabled_toolsets": [],
        "memory_context_files_enabled": False,
        "persistent_session_enabled": False,
        "fallback_provider_configured": False,
        "general_api_fallback_allowed": False,
        "profiles": list(PROFILES),
        "profile_call_shapes": list(SHAPES),
        "profile_logical_calls": PROFILE_CALLS,
        "trajectory_names": list(TRAJECTORIES),
        "trajectory_logical_calls_each": TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_total": TRAJECTORY_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_send_guard_fail_closed": True,
        "unregistered_outbound_http_blocked": True,
        "all_profiles_execute": True,
        "selected_profile_rule": "first_passing_profile_in_registered_order",
        "trajectory_executes_only_if_profile_selected": True,
        "trajectory_qualification_requires_all_four_complete_55_of_55": True,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "source_acquisition_evidence_generated": False,
        "scientific_campaign_authorized": False,
        "provider_execution_authorized": False,
        "workflow_rerun_allowed": False,
        "same_request_stream_rerun_allowed": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_response_body_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "predecessor_issue": 221,
        "predecessor_pr": 222,
        "predecessor_merge_sha": "f2d4e5158a875a4a3ffa0bd69312eecba55e4940",
    }
    for key, value in expected.items():
        if p.get(key) != value:
            raise AssertionError(
                f"request-plan drift for {key}: {p.get(key)!r} != {value!r}"
            )


def cases(seed: int) -> list[dict[str, int]]:
    return [
        {
            "case_id": seed * 100 + i,
            "f0": (seed + 3 * i) % 11 - 5,
            "f1": (2 * seed + 5 * i) % 13 - 6,
            "f2": (3 * seed + 7 * i) % 17 - 8,
            "f3": (5 * seed + 11 * i) % 19 - 9,
        }
        for i in range(8)
    ]


def feedback(seed: int) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": ACTIONS[(seed + i) % 4],
            "correct": bool((seed + i) % 2),
            "bounded_feedback": "engineering sentinel feedback",
        }
        for i, row in enumerate(cases(seed))
    ]


def system_prompt() -> str:
    return (
        "Return one JSON object with an actions array containing exactly 8 entries, "
        "each one of KAPPA, MICA, ORBIT, VELA. You may also include strategy as a "
        "concise private working string. Other keys are ignored. Do not use markdown."
    )


def user_prompt(shape: str, seed: int, strategy: str = "") -> str:
    if shape not in SHAPES:
        raise ValueError(shape)
    sections = [
        "Objective: engineering-only D2-shaped structured completion sentinel; responses are never scientifically scored.",
        f"Call shape: {shape}",
        "Task ecology: synthetic four-feature integer cases with no hidden scientific policy.",
    ]
    if shape == "oracle_evaluation":
        sections.append(
            "Diagnostic instruction: emit any internally consistent valid action; there is no scientific answer key."
        )
    if strategy:
        sections.append("Prior private strategy:\n" + strategy[:1200])
    if shape in {"developed_development", "developed_evaluation"}:
        sections.append(
            "Outcome-bearing local feedback (synthetic engineering sentinel):\n"
            + json.dumps(feedback(seed - 1), sort_keys=True, separators=(",", ":"))
        )
    sections.append(
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":"))
    )
    if shape == "developed_development":
        sections.append(
            "Return choices and, if useful, an updated private strategy. This feedback carries no scientific truth."
        )
    else:
        sections.append(
            "These are held-out-shaped engineering cases. No correctness feedback will be returned."
        )
    return "\n\n".join(sections)


def trajectory_specs(index: int) -> list[dict[str, Any]]:
    if not 0 <= index < 4:
        raise ValueError(index)
    out: list[dict[str, Any]] = []
    b = 5000 + 1000 * index
    for c in range(4):
        out.append(
            {
                "phase": f"fresh/evaluation{c+1}",
                "shape": "fresh_evaluation",
                "seed": b + c,
                "arm": "fresh",
            }
        )
    for budget in (40, 80, 160):
        for batch in range(budget // 8):
            out.append(
                {
                    "phase": f"developed_{budget}/development{batch+1}",
                    "shape": "developed_development",
                    "seed": b + 10 * budget + batch,
                    "arm": f"developed_{budget}",
                }
            )
        for c in range(4):
            out.append(
                {
                    "phase": f"developed_{budget}/evaluation{c+1}",
                    "shape": "developed_evaluation",
                    "seed": b + 10 * budget + 100 + c,
                    "arm": f"developed_{budget}",
                }
            )
    for c in range(4):
        out.append(
            {
                "phase": f"oracle/evaluation{c+1}",
                "shape": "oracle_evaluation",
                "seed": b + 3000 + c,
                "arm": "oracle",
            }
        )
    if len(out) != 55:
        raise AssertionError("trajectory topology drift")
    return out


def materialize_topology() -> dict[str, Any]:
    shapes = []
    for i, shape in enumerate(SHAPES):
        text = user_prompt(shape, 100 + i, "S" * 320)
        shapes.append(
            {
                "shape": shape,
                "prompt_bytes": len(text.encode()),
                "prompt_sha256": sha(text),
            }
        )
    traj = []
    for i, name in enumerate(TRAJECTORIES):
        specs = trajectory_specs(i)
        traj.append(
            {
                "trajectory": name,
                "logical_calls": 55,
                "topology_sha256": hashlib.sha256(canonical(specs)).hexdigest(),
            }
        )
    return {
        "schema": "d2-vnext-scientific-completion-topology-v0.1",
        "issue": ISSUE,
        "profile_call_shapes": shapes,
        "profiles": list(PROFILES),
        "profile_logical_calls": PROFILE_CALLS,
        "trajectories": traj,
        "trajectory_logical_calls_total": TRAJECTORY_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "production_historical_substrate_enabled": False,
    }


def preflight() -> dict[str, Any]:
    validate_plan(load_plan())
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    topology = materialize_topology()
    if json.loads(TOPOLOGY.read_text()) != topology:
        raise AssertionError("committed topology drift")
    return {
        "schema": "d2-vnext-scientific-completion-preflight-v0.1",
        "issue": ISSUE,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha(PLAN),
        "topology_sha256": file_sha(TOPOLOGY),
        "topology": topology,
        "historical_substrate_enabled": False,
    }


class Budget:
    def __init__(self) -> None:
        self.total = 0
        self.blocked_budget = 0
        self.blocked_unexpected = 0
        self.attempts: dict[int, list[dict[str, Any]]] = {}
        self.local = threading.local()
        self.lock = threading.Lock()

    def begin(self, logical: int) -> None:
        if not 0 <= logical < MAX_LOGICAL_CALLS:
            raise AssertionError("logical index outside registered topology")
        with self.lock:
            self.attempts.setdefault(logical, [])
        self.local.logical = logical

    def reserve(self, url: str) -> tuple[int, int]:
        logical = getattr(self.local, "logical", None)
        with self.lock:
            if logical is None or not str(url).startswith(ALLOWED_URL):
                self.blocked_unexpected += 1
                raise UnexpectedOutboundRequest("unregistered outbound HTTP blocked")
            rows = self.attempts[logical]
            if len(rows) >= MAX_SENDS_PER_LOGICAL or self.total >= MAX_SENDS_TOTAL:
                self.blocked_budget += 1
                raise PhysicalSendBudgetExceeded(
                    "physical provider-send budget exhausted"
                )
            self.total += 1
            rows.append(
                {
                    "attempt": len(rows) + 1,
                    "campaign_physical_send_index": self.total,
                    "http_status": None,
                    "transport_error_type": None,
                }
            )
            return logical, len(rows) - 1

    def response(self, logical: int, i: int, status: int) -> None:
        with self.lock:
            self.attempts[logical][i]["http_status"] = int(status)

    def error(self, logical: int, i: int, exc: BaseException) -> None:
        with self.lock:
            self.attempts[logical][i]["transport_error_type"] = type(exc).__name__

    def rows(self, logical: int) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(x) for x in self.attempts.get(logical, [])]


@contextmanager
def guard(budget: Budget) -> Iterator[None]:
    import httpx

    sync = httpx.Client._send_single_request
    async_ = httpx.AsyncClient._send_single_request

    def capped_sync(client: Any, request: Any) -> Any:
        logical, i = budget.reserve(str(request.url))
        try:
            r = sync(client, request)
        except Exception as exc:
            budget.error(logical, i, exc)
            raise
        budget.response(logical, i, r.status_code)
        return r

    async def capped_async(client: Any, request: Any) -> Any:
        logical, i = budget.reserve(str(request.url))
        try:
            r = await async_(client, request)
        except Exception as exc:
            budget.error(logical, i, exc)
            raise
        budget.response(logical, i, r.status_code)
        return r

    httpx.Client._send_single_request = capped_sync
    httpx.AsyncClient._send_single_request = capped_async
    try:
        yield
    finally:
        httpx.Client._send_single_request = sync
        httpx.AsyncClient._send_single_request = async_


def bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status = re.search(
        r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I
    ) or re.search(r"\b(4\d\d|5\d\d)\b", text)
    code = re.search(
        r"""["']code["']\s*:\s*["']?(\d{3,6})""", text, re.I
    ) or re.search(r"provider(?:_code)?[=: ]+(\d{3,6})", text, re.I)
    s = int(status.group(1)) if status else None
    c = int(code.group(1)) if code else None
    return {
        "error_type": type(exc).__name__,
        "http_status": s,
        "provider_code": c,
        "error_text_length": len(text),
        "error_text_sha256": sha(text),
        "terminal_http_429_code_1113": s == 429 and c == 1113,
    }


def parse_response(text: str) -> str:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant prohibited: {value}")

    payload = json.loads(text, parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("response must be JSON object")
    actions = payload.get("actions")
    if (
        not isinstance(actions, list)
        or len(actions) != 8
        or any(x not in ACTIONS for x in actions)
    ):
        raise ValueError("invalid actions contract")
    strategy = payload.get("strategy")
    if strategy is None:
        return ""
    if not isinstance(strategy, str):
        raise ValueError("strategy must be string")
    return strategy[:1200]


def new_agent(iterations: int, tokens: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=base.PROVIDER,
        api_mode=base.API_MODE,
        model=MODEL,
        max_iterations=iterations,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=system_prompt(),
        max_tokens=tokens,
        request_overrides={
            "temperature": TEMPERATURE,
            "extra_body": {"thinking": THINKING},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    if int(getattr(agent.client, "max_retries", -1)) != base.OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI retry drift")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (
        agent.model != MODEL
        or agent.provider != base.PROVIDER
        or agent.api_mode != base.API_MODE
    ):
        raise AssertionError("Hermes route drift")
    if (
        str(agent.client.base_url).rstrip("/") != base.BASE_URL
        or str(agent.base_url).rstrip("/") != base.BASE_URL
    ):
        raise AssertionError("Hermes base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    if (
        float(kwargs.get("temperature", -1)) != TEMPERATURE
        or kwargs.get("extra_body") != {"thinking": THINKING}
    ):
        raise AssertionError("sampling/thinking drift")
    return agent


def run_call(
    budget: Budget,
    logical: int,
    call_id: str,
    profile: dict[str, Any],
    shape: str,
    seed: int,
    strategy: str,
) -> tuple[dict[str, Any], str]:
    budget.begin(logical)
    prompt = user_prompt(shape, seed, strategy)
    row: dict[str, Any] = {
        "logical_index": logical,
        "call_id": call_id,
        "call_shape": shape,
        "max_iterations": profile["max_iterations"],
        "max_tokens": profile["max_tokens"],
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": sha(prompt),
    }
    try:
        agent = new_agent(int(profile["max_iterations"]), int(profile["max_tokens"]))
        result = agent.run_conversation(user_message=prompt)
        api_calls = int(getattr(agent, "_api_call_count", 0))
        final = str(result.get("final_response") or "")
        if (
            result.get("failed") is True
            or result.get("completed") is not True
            or bool(result.get("error"))
            or not final.strip()
        ):
            raise RuntimeError(
                str(
                    result.get("error")
                    or "Hermes returned non-completed engineering logical call"
                )
            )
        if not 1 <= api_calls <= int(profile["max_iterations"]):
            raise RuntimeError(f"Hermes semantic API-call count drift: {api_calls}")
        next_strategy = parse_response(final)
        attempts = budget.rows(logical)
        if not 1 <= len(attempts) <= int(profile["max_iterations"]) * 18:
            raise AssertionError("physical-send count outside profile bound")
        finish = result.get("finish_reason")
        stop = result.get("stop_reason")
        if not isinstance(finish, (str, int, float, bool, type(None))):
            finish = None
        if not isinstance(stop, (str, int, float, bool, type(None))):
            stop = None
        row.update(
            {
                "status": "success",
                "completed": True,
                "agent_api_calls_observed": api_calls,
                "final_response_length": len(final),
                "final_response_sha256": sha(final),
                "strategy_present": bool(next_strategy),
                "strategy_length": len(next_strategy),
                "strategy_sha256": sha(next_strategy) if next_strategy else None,
                "finish_reason": finish,
                "stop_reason": stop,
                "provider_http_attempts_observed": len(attempts),
                "attempts": attempts,
                "terminal_http_429_code_1113": False,
            }
        )
        return row, next_strategy
    except Exception as exc:
        attempts = budget.rows(logical)
        row.update(
            {
                "status": "failure",
                "completed": False,
                "agent_api_calls_observed": int(
                    getattr(locals().get("agent", None), "_api_call_count", 0)
                ),
                "provider_http_attempts_observed": len(attempts),
                "attempts": attempts,
                **bounded_error(exc),
            }
        )
        return row, strategy


def profile_pass(profile: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    return len(rows) == 4 and all(
        x.get("status") == "success"
        and 1
        <= int(x.get("agent_api_calls_observed", 0))
        <= int(profile["max_iterations"])
        and x.get("terminal_http_429_code_1113") is False
        for x in rows
    )


def run_trajectory(
    budget: Budget, index: int, profile: dict[str, Any]
) -> dict[str, Any]:
    start = PROFILE_CALLS + index * TRAJECTORY_CALLS_EACH
    strategies: dict[str, str] = {}
    rows = []
    for offset, spec in enumerate(trajectory_specs(index)):
        arm = str(spec["arm"])
        prior_strategy = strategies.get(arm, "")
        row, strategy = run_call(
            budget,
            start + offset,
            f"{TRAJECTORIES[index]}/{spec['phase']}",
            profile,
            str(spec["shape"]),
            int(spec["seed"]),
            prior_strategy,
        )
        rows.append(row)
        if row["status"] != "success":
            break
        strategies[arm] = strategy or prior_strategy
    complete = len(rows) == 55 and all(x["status"] == "success" for x in rows)
    return {
        "trajectory": TRAJECTORIES[index],
        "registered_logical_calls": 55,
        "attempted_logical_calls": len(rows),
        "completed_logical_calls": sum(x["status"] == "success" for x in rows),
        "complete_55_of_55": complete,
        "calls": rows,
    }


def marker() -> dict[str, str]:
    if not MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(
        line.split("=", 1) for line in MARKER.read_text().splitlines() if line
    )
    if (
        set(fields) != {"candidate_sha", "issue", "authorization"}
        or fields["issue"] != "223"
        or fields["authorization"] != AUTH_STRING
    ):
        raise RuntimeError("authorization marker invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", fields["candidate_sha"]):
        raise RuntimeError("candidate SHA invalid")
    return fields


def execute() -> dict[str, Any]:
    if os.getenv(AUTH_ENV) != "1" or not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("provider execution not authorized/credentialed")
    base._assert_execution_environment()
    validate_plan(load_plan())
    auth = marker()
    hermes_version, sdk_retries, httpx_version = base._validate_runtime_versions()
    budget = Budget()
    profiles = []
    logical = 0
    with guard(budget):
        for profile in PROFILES:
            rows = []
            for i, shape in enumerate(SHAPES):
                row, _ = run_call(
                    budget,
                    logical,
                    f"profile/{profile['name']}/{shape}",
                    profile,
                    shape,
                    100 + i,
                    "S" * 320,
                )
                rows.append(row)
                logical += 1
            profiles.append(
                {"profile": profile, "calls": rows, "pass": profile_pass(profile, rows)}
            )
        selected = next((x["profile"] for x in profiles if x["pass"]), None)
        trajectories: list[dict[str, Any]] = []
        if selected:
            with ThreadPoolExecutor(max_workers=MAX_TRAJECTORY_CONCURRENCY) as pool:
                trajectories = list(
                    pool.map(lambda i: run_trajectory(budget, i, selected), range(4))
                )
    attempted = PROFILE_CALLS + sum(
        int(x["attempted_logical_calls"]) for x in trajectories
    )
    passed = (
        bool(selected)
        and len(trajectories) == 4
        and all(x["complete_55_of_55"] for x in trajectories)
        and budget.total <= MAX_SENDS_TOTAL
        and budget.blocked_budget == 0
        and budget.blocked_unexpected == 0
    )
    return {
        "schema": "d2-vnext-scientific-completion-qualification-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "authorized_candidate_sha": auth["candidate_sha"],
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "hermes_revision": base.HERMES_REVISION,
        "hermes_package_version": hermes_version,
        "hermes_run_agent_blob_sha": base.HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": base.OPENAI_VERSION,
        "openai_sdk_default_max_retries": sdk_retries,
        "httpx_version": httpx_version,
        "endpoint_base_url": base.BASE_URL,
        "provider_id": base.PROVIDER,
        "api_mode": base.API_MODE,
        "requested_model": MODEL,
        "effective_model_identity_observed": False,
        "effective_model_identity_claim": "unobserved_at_supported_product_boundary",
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "profiles": profiles,
        "selected_profile": selected,
        "trajectories": trajectories,
        "profile_logical_calls_registered": PROFILE_CALLS,
        "trajectory_logical_calls_registered_maximum": TRAJECTORY_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "logical_calls_attempted": attempted,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total,
        "provider_sends_blocked_by_budget": budget.blocked_budget,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "qualification_pass": passed,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "scientific_campaign_executed": False,
        "source_acquisition_evidence_generated": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_response_body_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "same_request_stream_rerun_allowed": False,
        "predecessor_issue": 221,
        "predecessor_pr": 222,
        "predecessor_merge_sha": "f2d4e5158a875a4a3ffa0bd69312eecba55e4940",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    result = preflight() if args.preflight else execute()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(result))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()