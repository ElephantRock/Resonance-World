# Phase 2 preregistration — one-agent model-backed PIANO experiment

Status: **locked; no scientific model output observed yet**

The Phase-2 design remains the same one-agent paired experiment. The provider selection was revised before any successful model call because the repository already exposes `ZAI_API_KEY` rather than `OPENAI_API_KEY`.

## Locked provider revision

- provider: Z.AI
- API surface: OpenAI-compatible Chat Completions
- general API base: `https://api.z.ai/api/paas/v4`
- credential: GitHub Actions secret `ZAI_API_KEY`
- model: `glm-4-32b-0414-128k`
- structured output: provider JSON mode plus Field-side stage validation
- all seeds, scenarios, prompts, call budgets, metrics, and advancement thresholds are unchanged

This provider revision is permitted because all prior live attempts stopped at the missing-credential gate before any model inference occurred. No campaign outcome was available when this revision was made.
