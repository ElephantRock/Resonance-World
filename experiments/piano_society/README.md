# PIANO Society Runtime Experiment

Status: **Phase 0 — instrumentation validation**

Branch: `experiment/piano-society-runtime`

This experiment tests one narrow architectural claim inspired by Project Sid/PIANO:

> Does a shared high-level intention plus action acknowledgement reduce behavioral
> contradictions and unsupported success claims relative to independently generated
> speech/action channels?

It does **not** attempt to reproduce Project Sid's civilization claims, Minecraft
environment, seeded governance, or cultural-diffusion experiments.

## Repository boundary

Resonance World's production boundary remains unchanged:

- Resonance Field owns agents, local cognition, local substrate, and within-field
  emergence.
- Resonance World owns cross-field protocols, institutions, orchestration, and
  world-level experiments.
- This directory is disposable experimental scaffolding. A successful result does not
  authorize moving agent cognition into `src/resonance_world`.
- A live treatment must connect to Resonance Field through an explicit adapter/contract,
  not by importing Field-private state.

## Arms

### Baseline

Raw cognitive, speech, and action proposals are generated independently. Speech and
action channels execute without a shared arbitration result, and speech can claim
success before environmental acknowledgement.

### Treatment

The same raw proposal stream and the same exogenous environment draws are reused. A
single controller intention conditions both speech and action. Success language is
allowed only after the environment acknowledges the action.

The paired design is intentional: model, seed, scenario, environment draw, and workload
must be held constant between arms when the live adapter is added.

## Phase 0

Phase 0 is a synthetic fault-injection harness. It exists only to validate that the
metrics detect the failure modes they claim to measure.

**No scientific claim is allowed from Phase 0.** The result payload carries
`"scientific_claim_allowed": false`, and a test freezes that invariant.

Run it with:

```bash
python -m experiments.piano_society.harness \
  --config experiments/piano_society/config.json \
  --output output/piano_society/phase0.json
```

Run the focused tests with:

```bash
pytest -q tests/test_piano_society_experiment.py
```

## Preregistered live metrics

Primary:

1. **Cross-channel contradiction rate** — speech intent conflicts with executed action.
2. **Intent/action divergence rate** — executed action conflicts with the arbitrated
   high-level intention.
3. **Unsupported success-claim rate** — speech asserts task success when the action
   failed or a different action was executed.

Secondary:

- task completion rate,
- wall-clock latency per agent-step,
- model calls and tokens per agent-step,
- relationship-state consistency after interaction,
- recovery time after an action failure,
- degradation of the above as population scales.

## Live progression

The branch should advance only through explicit gates:

1. **Phase 0 — instrumentation validation**
   - synthetic paired streams;
   - prove metrics respond to injected disagreement/failure;
   - no scientific interpretation.
2. **Phase 1 — single-agent live adapter**
   - one Resonance Field agent;
   - same model/tool budget in both arms;
   - inject action failures and delayed acknowledgements.
3. **Phase 2 — small social cohort**
   - 10 agents;
   - repeated interaction and relationship-state checks.
4. **Phase 3 — scaling**
   - 50 then 100 agents;
   - advance only if measurement and cost remain stable.
5. **Extraction decision**
   - if the treatment wins under live paired runs, extract only the validated contracts
     into the appropriate production repository;
   - leave synthetic scaffolding in this experiment branch.

## Initial live decision rule

Before Phase 1 runs, freeze exact seeds, model snapshot, prompts, tool permissions,
scenario corpus, failure-injection schedule, and compute budget.

The treatment is considered promising only if it reduces each primary failure metric
without a material task-completion regression. Latency/token costs must be reported,
not hidden by the coherence improvement.

No scale claim should be made from a single run. Report paired results by seed and
population size, not only pooled averages.

## Files

- `config.json` — Phase 0 paired-run configuration.
- `harness.py` — synthetic proposal generator, arms, metrics, and CLI.
- `../../tests/test_piano_society_experiment.py` — invariants for paired inputs and
  measurement sensitivity.
- `../../.github/workflows/piano-society-runtime.yml` — focused CI for this branch/PR.
