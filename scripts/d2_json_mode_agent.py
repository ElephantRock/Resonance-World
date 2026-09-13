"""Pinned Hermes request construction and zero-provider preflight for #258."""

from __future__ import annotations

from typing import Any

import d2_json_mode_contract as contract


def request_overrides(logical_index: int) -> dict[str, Any]:
    return {
        "temperature": contract.TEMPERATURE,
        "response_format": dict(contract.RESPONSE_FORMAT),
        "extra_body": {"thinking": dict(contract.THINKING)},
        "extra_headers": {contract.PROBE_ORIGIN_HEADER: str(logical_index)},
    }


def preflight() -> dict[str, Any]:
    probes = contract.validate_frozen_contract()
    if contract.MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    for logical in (0, 17, 18, 35, 36, 53, 54, 71):
        overrides = request_overrides(logical)
        if overrides["response_format"] != {"type": "json_object"}:
            raise AssertionError("JSON-mode intervention drift")
        if overrides["extra_body"] != {"thinking": {"type": "disabled"}}:
            raise AssertionError("thinking override drift")
        if overrides["extra_headers"][contract.PROBE_ORIGIN_HEADER] != str(logical):
            raise AssertionError("logical origin header drift")
    lengths = [len(contract.user_prompt(probe).encode()) for probe in probes]
    return {
        "schema": "d2-json-mode-conformance-preflight-v0.1",
        "issue": contract.ISSUE,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "fresh_namespace": contract.NAMESPACE,
        "probe_count": len(probes),
        "minimum_prompt_bytes": min(lengths),
        "maximum_prompt_bytes": max(lengths),
        "request_intervention": {"response_format": {"type": "json_object"}},
        "request_plan_git_blob_sha": contract.git_blob_sha(contract.PLAN),
        "probes_git_blob_sha": contract.git_blob_sha(contract.PROBES),
        "provider_send_guard_git_blob_sha": contract.git_blob_sha(contract.GUARD_PATH),
        "terminal_adapter_git_blob_sha": contract.git_blob_sha(contract.ADAPTER_PATH),
        "scientific_scoring_performed": False,
        "acceptance_action_authorized": False,
        "historical_substrate_enabled": False,
    }


def new_agent(logical_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=contract.PROVIDER,
        api_mode=contract.API_MODE,
        model=contract.MODEL,
        max_iterations=contract.MAX_ITERATIONS,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=contract.system_prompt(),
        max_tokens=contract.MAX_TOKENS,
        request_overrides=request_overrides(logical_index),
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    if int(getattr(agent.client, "max_retries", -1)) != contract.OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI client retry drift")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (agent.model, agent.provider, agent.api_mode) != (
        contract.MODEL,
        contract.PROVIDER,
        contract.API_MODE,
    ):
        raise AssertionError("Hermes route drift")
    if (int(agent.max_iterations), int(agent.max_tokens)) != (
        contract.MAX_ITERATIONS,
        contract.MAX_TOKENS,
    ):
        raise AssertionError("Hermes profile drift")
    if str(agent.client.base_url).rstrip("/") != contract.BASE_URL:
        raise AssertionError("Hermes client base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    expected = request_overrides(logical_index)
    for key in ("temperature", "response_format", "extra_body", "extra_headers"):
        if kwargs.get(key) != expected[key]:
            raise AssertionError(f"Hermes request override drift: {key}")
    return agent
