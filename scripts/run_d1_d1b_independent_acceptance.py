#!/usr/bin/env python3
"""Run one neutral external-model acceptance review of frozen D1/D1b evidence."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "ElephantRock/Resonance-World"
MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MAX_ATTEMPTS = 3

LOCAL_EVIDENCE = [
    "docs/mechanism-governance-v0.1.md",
    "research/mechanisms/registry.json",
    "research/d1/CONFIRMATORY_PLAN.md",
    "research/d1/EXECUTION.md",
    "research/d1/RESULT.md",
    "research/d1/result.json",
    "research/d1/audit.json",
    "research/d1/manifest.json",
    "research/d1b/PLAN.md",
    "research/d1b/EXECUTION.md",
    "research/d1b/RESULT.md",
    "research/d1b/result.json",
    "research/d1b/audit.json",
    "research/d1b/manifest.json",
    "research/d1b/classification.json",
]

GITHUB_EVIDENCE = {
    "github:issue-160": f"https://api.github.com/repos/{REPO}/issues/160",
    "github:issue-160-comments": f"https://api.github.com/repos/{REPO}/issues/160/comments?per_page=100",
    "github:issue-163": f"https://api.github.com/repos/{REPO}/issues/163",
    "github:issue-163-comments": f"https://api.github.com/repos/{REPO}/issues/163/comments?per_page=100",
    "github:issue-165-rubric": f"https://api.github.com/repos/{REPO}/issues/165",
    "github:d1-workflow-31861296898": f"https://api.github.com/repos/{REPO}/actions/runs/31861296898",
    "github:d1b-workflow-31861974865": f"https://api.github.com/repos/{REPO}/actions/runs/31861974865",
}

DECISIONS = {
    "ACCEPT both transitions",
    "ACCEPT discovery_supported only; replication transition rejected/deferred",
    "REJECT promotion; retain proposed and document reason",
    "DEFER pending specified evidence/integration condition",
}

CRITERIA = [
    "preregistration_before_outcomes",
    "d1b_unchanged_mechanism",
    "confirmatory_cohort_disjointness",
    "p0_p1_p2_pass_both",
    "p2_margin_conventional",
    "capability_artifact_private_state_excluded",
    "oracle_and_subgroups_nonpromotional",
    "claim_ceiling_deterministic_individual_specialist",
    "historical_substrate_off",
    "preservation_dependency_chain_respected",
    "acceptor_distinct_from_proposer",
]


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def github_get(url: str, token: str) -> Any:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "resonance-world-independent-acceptor/0.1",
        },
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def build_evidence(github_token: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {"local": {}, "github": {}}

    for path_text in LOCAL_EVIDENCE:
        path = Path(path_text)
        raw = path.read_bytes()
        manifest["local"][path_text] = {
            "sha256": digest_bytes(raw),
            "bytes": len(raw),
        }
        sections.append({"id": f"repo:{path_text}", "content": raw.decode("utf-8")})

    for evidence_id, url in GITHUB_EVIDENCE.items():
        value = github_get(url, github_token)
        if evidence_id == "github:issue-165-rubric" and isinstance(value, dict):
            value = {
                "number": value.get("number"),
                "title": value.get("title"),
                "body": value.get("body"),
                "state": value.get("state"),
                "created_at": value.get("created_at"),
                "updated_at": value.get("updated_at"),
            }
        raw = canonical(value)
        manifest["github"][evidence_id] = {
            "url": url,
            "sha256": digest_bytes(raw),
            "bytes": len(raw),
        }
        sections.append({"id": evidence_id, "content": raw.decode("utf-8")})

    manifest["combined_sha256"] = digest_bytes(canonical(manifest))
    return sections, manifest


def reviewer_messages(sections: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are the sole independent Acceptance-plane reviewer for D1/D1b in Resonance World. "
        "You are not the experiment proposer, designer, executor, evaluator, or prior project judge. "
        "Review only the supplied frozen evidence. Do not assume missing facts. Do not reward the proposer. "
        "If required evidence is insufficient, choose DEFER. Apply the issue #165 rubric literally. "
        "The allowed claim ceiling is the deterministic individual-specialist Field substrate only. "
        "Return exactly one JSON object and no surrounding prose."
    )
    evidence_text = "\n\n".join(
        f"===== EVIDENCE {section['id']} =====\n{section['content']}" for section in sections
    )
    schema = {
        "decision": "one exact allowed decision string",
        "summary": "neutral concise rationale",
        "checks": [
            {
                "criterion": "one exact criterion id",
                "status": "PASS|FAIL|INSUFFICIENT",
                "evidence_refs": ["one or more supplied evidence ids"],
                "reason": "concise evidence-based reason",
            }
        ],
        "accepted_claim": "bounded claim or null if not accepted",
        "reservations": ["material reservations only"],
        "acceptor": {
            "provider": "Z.AI",
            "model": MODEL,
            "role": "independent_acceptance_plane_reviewer",
        },
    }
    user = (
        "Adjudicate the two requested registry transitions using exactly one substantive review.\n\n"
        "Allowed decisions:\n- " + "\n- ".join(sorted(DECISIONS)) + "\n\n"
        "Required checklist criterion ids, each exactly once:\n- " + "\n- ".join(CRITERIA) + "\n\n"
        "For ACCEPT both transitions, every criterion should be PASS. "
        "For any non-acceptance, identify the exact failed or insufficient criterion(s). "
        "Do not infer model-generalized, naturalistic, team, institutional, market, or environment-spawning claims. "
        "Do not treat the conventional 90% fidelity margin as natural materiality.\n\n"
        f"Evidence-manifest combined SHA-256: {manifest['combined_sha256']}\n\n"
        "Required output shape:\n" + json.dumps(schema, indent=2) + "\n\n" + evidence_text
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def structural_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return ["checks_not_list"]
    seen: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            warnings.append("invalid_check_shape")
            continue
        criterion = check.get("criterion")
        if criterion not in CRITERIA:
            warnings.append(f"unknown_criterion:{criterion}")
        elif criterion in seen:
            warnings.append(f"duplicate_criterion:{criterion}")
        else:
            seen.append(criterion)
        if check.get("status") not in {"PASS", "FAIL", "INSUFFICIENT"}:
            warnings.append(f"invalid_status:{criterion}")
    for criterion in CRITERIA:
        if criterion not in seen:
            warnings.append(f"missing_criterion:{criterion}")
    if payload.get("decision") == "ACCEPT both transitions":
        for check in checks:
            if isinstance(check, dict) and check.get("status") != "PASS":
                warnings.append("accept_both_contains_nonpass_check")
                break
    return sorted(set(warnings))


def call_reviewer(
    key: str, messages: list[dict[str, str]]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[str]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        body = {
            "model": MODEL,
            "messages": messages,
            "thinking": {"type": "disabled"},
            "do_sample": False,
            "temperature": 0.0,
            "max_tokens": 5000,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        started = time.perf_counter()
        request = Request(
            ENDPOINT,
            data=json.dumps(body, separators=(",", ":")).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept-Language": "en-US,en",
                "User-Agent": "resonance-world-independent-acceptor/0.1",
            },
        )
        try:
            with urlopen(request, timeout=180) as response:
                outer = json.loads(response.read().decode())
            if outer.get("model") != MODEL:
                raise ValueError(f"model_drift:{outer.get('model')}")
            choices = outer.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("choice_shape")
            text = choices[0].get("message", {}).get("content")
            payload = json.loads(text)
            if not isinstance(payload, dict) or payload.get("decision") not in DECISIONS:
                raise ValueError("no_allowed_decision")
            warnings = structural_warnings(payload)
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "valid_substantive_decision",
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
            return payload, attempts, outer.get("usage", {}), warnings
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            attempts.append(
                {
                    "attempt": attempt,
                    "status": type(exc).__name__,
                    "detail": str(exc)[:1000],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
            if isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                raise
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"reviewer failed without a valid decision: {attempts}") from exc
            time.sleep(min(30.0, 2.0**attempt))
    raise AssertionError("unreachable")


def main() -> int:
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    zai_key = os.environ.get("ZAI_API_KEY", "").strip()
    if not github_token:
        raise SystemExit("GITHUB_TOKEN required")
    if not zai_key:
        raise SystemExit("ZAI_API_KEY required")

    out = Path("output/d1-d1b-acceptance")
    out.mkdir(parents=True, exist_ok=True)

    sections, manifest = build_evidence(github_token)
    messages = reviewer_messages(sections, manifest)
    request_record = {
        "schema": "d1-d1b-independent-review-request-v0.1",
        "model": MODEL,
        "evidence_manifest_sha256": manifest["combined_sha256"],
        "messages_sha256": digest_bytes(canonical(messages)),
        "evidence_ids": [section["id"] for section in sections],
        "proposer_model": "GPT-5.6 Sol",
        "acceptor_model": MODEL,
    }
    (out / "evidence-manifest.json").write_bytes(canonical(manifest))
    (out / "review-request.json").write_bytes(canonical(request_record))

    payload, attempts, usage, warnings = call_reviewer(zai_key, messages)
    response_record = {
        "schema": "d1-d1b-independent-review-response-v0.1",
        "evidence_manifest_sha256": manifest["combined_sha256"],
        "review": payload,
    }
    response_bytes = canonical(response_record)
    (out / "review-response.json").write_bytes(response_bytes)
    audit = {
        "schema": "d1-d1b-independent-review-audit-v0.1",
        "provider": "Z.AI",
        "model": MODEL,
        "proposer_model": "GPT-5.6 Sol",
        "model_separation": MODEL != "GPT-5.6 Sol",
        "attempts": attempts,
        "usage": usage,
        "structural_warnings": warnings,
        "evidence_manifest_sha256": manifest["combined_sha256"],
        "review_response_sha256": digest_bytes(response_bytes),
        "substantive_valid_decision_count": sum(
            x["status"] == "valid_substantive_decision" for x in attempts
        ),
        "production_historical_substrate_enabled": False,
    }
    (out / "review-audit.json").write_bytes(canonical(audit))
    print(json.dumps(response_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
