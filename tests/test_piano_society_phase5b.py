from resonance.experiments.piano_phase2 import ModelReply

from resonance_world.w4a_joint_learning import IndividualState
from resonance_world.w5_institution import InstitutionMission
from resonance_world.w5a_organization import OrganizationEpisode, OrganizationState
from resonance_world.w4a_joint_learning import JointMission

from experiments.piano_society.phase5b_controller import (
    TransferableInstitutionalController,
    TransferControllerConfig,
)
from experiments.piano_society.phase5b_transfer_memory import (
    fit_transfer_posterior,
    forecast_strategies,
    neutral_posterior,
    select_forecast_strategy,
)


class _FakeBackend:
    model_snapshot = "glm-5.2"

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        payloads = {
            "intention": {
                "intention": "Use the institution's current-roster forecast.",
                "intended_action": "specialist",
            },
            "speech": {
                "speech": "The organization will use specialist routing.",
                "speech_action": "specialist",
            },
            "action": {"action": "specialist", "payload": {}, "confidence": 0.9},
            "post_action_report": {
                "report": "The registered routing evaluation completed.",
                "claims_success": False,
            },
        }
        return ModelReply(
            payload=payloads[request.stage],
            model_snapshot=self.model_snapshot,
            input_tokens=11,
            output_tokens=7,
            latency_ms=3.0,
        )


def _mission() -> InstitutionMission:
    return InstitutionMission(
        public=JointMission(
            mission_id="synthetic",
            context="synthetic-context",
            lead_skill="skill-a",
            support_skill="skill-b",
        ),
        regime="specialist",
    )


def _organization_with_role_specific_successes() -> OrganizationState:
    members = [
        IndividualState("lead", {"skill-a": 4, "skill-b": 0}),
        IndividualState("support", {"skill-a": 0, "skill-b": 4}),
        IndividualState("general-1", {"skill-a": 1, "skill-b": 1}),
        IndividualState("general-2", {"skill-a": 1, "skill-b": 1}),
    ]
    organization = OrganizationState("synthetic-org", {item.agent_id: item for item in members})
    for index in range(20):
        organization.memory.observe(
            OrganizationEpisode(
                mission_id=f"formation-{index}",
                context="synthetic-context",
                strategy="specialist",
                lead_agent_id="lead",
                support_agent_id="support",
                success=True,
            )
        )
    return organization


def test_transfer_posterior_learns_structure_from_episodes_not_regime_label() -> None:
    organization = _organization_with_role_specific_successes()
    posterior = fit_transfer_posterior(organization, _mission())
    assert posterior.evidence_episodes == 20
    assert posterior.role_specific > 0.99
    assert posterior.cross_coverage < 0.01


def test_neutral_reset_and_forecast_contract_are_binary() -> None:
    organization = _organization_with_role_specific_successes()
    mission = _mission()
    posterior = neutral_posterior()
    assert posterior.as_dict() == {
        "role_specific": 0.5,
        "cross_coverage": 0.5,
        "evidence_episodes": 0,
    }
    forecasts = forecast_strategies(organization, mission, posterior)
    assert set(forecasts) == {"specialist", "balanced"}
    assert select_forecast_strategy(forecasts) in forecasts


def test_phase5b_controller_uses_exact_four_call_contract() -> None:
    backend = _FakeBackend()
    controller = TransferableInstitutionalController(
        backend=backend,
        config=TransferControllerConfig(
            trial_seed=9601,
            required_model_snapshot="glm-5.2",
            strategy_order=("specialist", "balanced"),
        ),
    )
    plan = controller.plan(
        mission_text="context=route-x; lead_skill=skill-a; support_skill=skill-b",
        roster_text="replacement roster",
        memory_text=(
            '{"structural_posterior":{"role_specific":0.8,"cross_coverage":0.2},'
            '"current_roster_strategy_forecast":{"specialist":0.42,"balanced":0.31}}'
        ),
    )
    report = controller.report_after_execution(
        plan,
        acknowledgement_text="trials=128; successes=40; success_rate=0.3125; grounded_success=false",
    )
    assert [request.stage for request in backend.requests] == [
        "intention",
        "speech",
        "action",
        "post_action_report",
    ]
    assert all(request.seed == 9601 for request in backend.requests)
    assert all(request.max_output_tokens == 128 for request in backend.requests)
    assert plan.strategy == "specialist"
    assert report.usage.calls == 4
    assert report.usage.input_tokens == 44
    assert report.usage.output_tokens == 28
    assert report.usage.latency_ms == 12.0


def test_phase5b_planning_prompts_do_not_contain_hidden_regime_language() -> None:
    backend = _FakeBackend()
    controller = TransferableInstitutionalController(
        backend=backend,
        config=TransferControllerConfig(
            trial_seed=9602,
            required_model_snapshot="glm-5.2",
            strategy_order=("balanced", "specialist"),
        ),
    )
    controller.plan(
        mission_text="context=route-y; lead_skill=skill-c; support_skill=skill-d",
        roster_text="replacement roster",
        memory_text="neutral structural posterior",
    )
    for request in backend.requests:
        lowered = request.prompt.lower()
        assert "hidden regime" not in lowered
        assert "specialist=select" in lowered
        assert "balanced=select" in lowered
