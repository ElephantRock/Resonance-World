from resonance.experiments.piano_phase2 import ModelReply

from experiments.piano_society.phase5_controller import (
    InstitutionalControllerConfig,
    InstitutionalPianoController,
)


class _FakeBackend:
    model_snapshot = "glm-5.2"

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        payloads = {
            "intention": {
                "intention": "Use inherited procedure evidence to route the mission.",
                "intended_action": "specialist",
            },
            "speech": {
                "speech": "The organization will use specialist routing.",
                "speech_action": "specialist",
            },
            "action": {
                "action": "specialist",
                "payload": {},
                "confidence": 0.8,
            },
            "post_action_report": {
                "report": "The audited routing evaluation completed.",
                "claims_success": True,
            },
        }
        return ModelReply(
            payload=payloads[request.stage],
            model_snapshot=self.model_snapshot,
            input_tokens=10,
            output_tokens=5,
            latency_ms=2.0,
        )


def test_phase5_controller_uses_exact_four_call_piano_contract() -> None:
    backend = _FakeBackend()
    controller = InstitutionalPianoController(
        backend=backend,
        config=InstitutionalControllerConfig(
            trial_seed=9301,
            required_model_snapshot="glm-5.2",
            strategy_order=("balanced", "specialist"),
        ),
    )

    plan = controller.plan(
        mission_text="context=route-a; lead_skill=energy_storage; support_skill=public_health",
        roster_text="member competence table",
        memory_text="specialist attempts=48 successes=34; balanced attempts=48 successes=21",
    )
    report = controller.report_after_execution(
        plan,
        acknowledgement_text="128 registered environment trials; success_rate=0.625",
    )

    assert [request.stage for request in backend.requests] == [
        "intention",
        "speech",
        "action",
        "post_action_report",
    ]
    assert all(request.seed == 9301 for request in backend.requests)
    assert all(request.max_output_tokens == 128 for request in backend.requests)
    assert plan.strategy == "specialist"
    assert report.usage.calls == 4
    assert report.usage.input_tokens == 40
    assert report.usage.output_tokens == 20
    assert report.usage.latency_ms == 8.0


def test_phase5_binary_strategy_order_is_explicit_in_every_planning_prompt() -> None:
    backend = _FakeBackend()
    controller = InstitutionalPianoController(
        backend=backend,
        config=InstitutionalControllerConfig(
            trial_seed=9302,
            required_model_snapshot="glm-5.2",
            strategy_order=("balanced", "specialist"),
        ),
    )

    controller.plan(
        mission_text="context=route-a; lead_skill=energy_storage; support_skill=public_health",
        roster_text="same replacement roster",
        memory_text="no inherited observations",
    )

    for request in backend.requests:
        assert "Available strategies in registered presentation order: balanced, specialist" in (
            request.prompt
        )
    assert all("hidden mission regime" not in request.prompt.lower() for request in backend.requests)


def test_phase5_controller_rejects_duplicate_or_unknown_strategy_vocabularies() -> None:
    for strategy_order in (
        ("specialist", "specialist"),
        ("specialist", "unknown"),
        (),
    ):
        try:
            InstitutionalControllerConfig(
                trial_seed=9303,
                required_model_snapshot="glm-5.2",
                strategy_order=strategy_order,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid strategy vocabulary must fail closed")
