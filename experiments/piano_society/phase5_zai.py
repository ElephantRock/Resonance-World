"""Phase-5 Z.AI transport adapter for the institutional strategy vocabulary."""

from __future__ import annotations

from resonance.experiments.piano_phase2_zai import ZAIChatCompletionsBackend


class Phase5ZAIChatCompletionsBackend(ZAIChatCompletionsBackend):
    """Use the first registered institutional strategy in JSON shape examples."""

    def _format_template(self, stage: str) -> str:
        action = self.allowed_actions[0]
        if stage == "intention":
            return (
                '{"intention":"<non-empty string>",'
                f'"intended_action":"{action}"}}'
            )
        if stage == "speech":
            return '{"speech":"<non-empty string>",' f'"speech_action":"{action}"}}'
        if stage == "action":
            return f'{{"action":"{action}","payload":{{}},"confidence":0.5}}'
        if stage == "post_action_report":
            return '{"report":"<non-empty string>","claims_success":true}'
        raise ValueError(f"unsupported Phase-5 model stage {stage!r}")
