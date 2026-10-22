"""Credential-free G1 crossed-view builder; never a provider dispatch gate.

Only a trusted, external evaluator can authenticate grades or target custody.
Only an actual provider transport can attest session and token usage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Literal

from resonance_world.c3r_g1_crossed_plan import ARMS, CrossedPlan, make_plan

Phase = Literal["development", "learned", "fresh", "neutral"]
PHASES: tuple[Phase, ...] = ("development", "learned", "fresh", "neutral")


@dataclass(frozen=True, slots=True)
class SourceObservation:
    """Unattested source event; never includes the target rule or holdout grade."""

    unit_id: str
    task_id: str
    action: str
    feedback: str


@dataclass(frozen=True, slots=True)
class SessionBinding:
    unit_id: str
    phase: Phase
    session_ref: str


@dataclass(frozen=True, slots=True)
class QualificationView:
    unit_id: str
    task_id: str
    arm: str
    session_ref: str
    payload: str


@dataclass(frozen=True, slots=True)
class PreflightBundle:
    views: tuple[QualificationView, ...]
    audit: dict[str, object]


def build_preflight(
    plan: CrossedPlan,
    *,
    sources: tuple[SourceObservation, ...],
    sessions: tuple[SessionBinding, ...],
    token_count: Callable[[str], int] | None = None,
) -> PreflightBundle:
    """Shape-check source and session declarations; expose no target map.

    A caller-supplied tokenizer produces *local diagnostics only*. Provider
    prompt-token accounting, model-session separation, evaluator receipts and
    paid-send authorization are all explicitly outside this function.
    """
    plan.audit()
    if plan.public_digest != make_plan().public_digest:
        raise ValueError("unfrozen crossed plan digest")
    expected_sources = {
        (cell.unit_id, task.task_id)
        for cell in plan.cells for task in cell.development
    }
    actual_sources = [(s.unit_id, s.task_id) for s in sources]
    if len(actual_sources) != len(expected_sources) or set(actual_sources) != expected_sources:
        raise ValueError("incomplete, repeated or alien development evidence")
    if any(s.action not in ("A", "B") or s.feedback not in ("correct", "incorrect")
           for s in sources):
        raise ValueError("source events require exact A/B and binary feedback")
    source_by_key = {(s.unit_id, s.task_id): s for s in sources}

    expected_sessions = {(cell.unit_id, phase) for cell in plan.cells for phase in PHASES}
    session_keys = [(s.unit_id, s.phase) for s in sessions]
    refs = [s.session_ref for s in sessions]
    if (len(session_keys) != len(expected_sessions)
            or set(session_keys) != expected_sessions
            or len(set(refs)) != len(refs)
            or any(not isinstance(ref, str) or not ref.strip() for ref in refs)):
        raise ValueError("session declarations must be complete and globally disjoint")
    session_by_key = {(s.unit_id, s.phase): s.session_ref for s in sessions}
    rendered: dict[tuple[str, str, str], QualificationView] = {}
    paired_local_counts: list[bool] = []
    for cell in plan.cells:
        qualification = cell.qualification[0]
        source_tasks = [(t, source_by_key[(cell.unit_id, t.task_id)])
                        for t in cell.development]
        for arm in ARMS:
            if arm == "fresh":
                history: list[dict[str, object]] = []
            elif arm == "neutral":
                history = [{"public_task": t.record(), "attempt_recorded": True}
                           for t, _ in source_tasks]
            else:
                history = [{"public_task": t.record(), "action": obs.action,
                            "feedback": obs.feedback} for t, obs in source_tasks]
            payload = json.dumps({
                "schema": "c3r-g1-crossed-view-v0.1",
                "qualification_task": qualification.record(),
                "source_history": history,
            }, sort_keys=True, separators=(",", ":"))
            rendered[(cell.unit_id, qualification.task_id, arm)] = QualificationView(
                cell.unit_id, qualification.task_id, arm,
                session_by_key[(cell.unit_id, arm)], payload,
            )
        if token_count is not None:
            def count(arm: str) -> int:
                n = token_count(rendered[(cell.unit_id, qualification.task_id, arm)].payload)
                if type(n) is not int or n < 0:
                    raise ValueError("local tokenizer must return a nonnegative integer")
                return n
            paired_local_counts.append(count("learned") == count("neutral"))

    views = tuple(rendered[(slot.unit_id, slot.task_id, slot.arm)]
                  for slot in plan.schedule if slot.stage == "qualification")
    if len(views) != 24:
        raise ValueError("qualification view count mismatch")
    return PreflightBundle(views, {
        "schema": "c3r-g1-crossed-preflight-v0.1",
        "public_plan_digest": plan.public_digest,
        "source_events_shape_checked": 16,
        "source_evaluator_receipts_attested": False,
        "distinct_local_session_references": len(set(refs)),
        "provider_session_isolation_attested": False,
        "rendered_qualification_views": len(views),
        "local_tokenizer_comparisons": len(paired_local_counts),
        "local_tokenizer_equal_pairs": sum(paired_local_counts),
        "provider_prompt_token_parity_attested": False,
        "private_target_mapping_imported": False,
        "physical_sends": 0,
        "physical_send_authorized": False,
        "live_ready": False,
        "scientific_acceptance": False,
        "verdict": "offline_view_construction_only",
    })
