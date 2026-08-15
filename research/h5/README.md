# H5 research harness

This directory preserves the branch-scoped H5 institutional-mediation experiment preregistered in #152. It is not a production-enablement package.

The apparatus is implemented by:

- `scripts/materialize_h5_fixtures.py` — deterministic Plane E / Plane K fixture generation;
- `scripts/verify_h5_lock.py` — prospective fixture/model/safety lock verification;
- `scripts/h5_institutional_core.py` — deterministic prompt, partition, protocol, and routine-digest construction.
- `scripts/run_h5_institutional.py` — equal-compute request planning and live Z.AI execution;
- `scripts/h5_evaluator_core.py` — deterministic acceptance, statistics, and causal-audit evaluation.
- `scripts/accept_h5_institutional.py` — deterministic frozen-output evaluator and registered statistical gates;
- `.github/workflows/h5-institutional-mediation.yml` — hosted lock, live campaign, and frozen evaluation.

Local pre-key apparatus check:

```bash
python scripts/materialize_h5_fixtures.py --output-dir output/h5-fixtures
python scripts/verify_h5_lock.py --fixture-dir output/h5-fixtures
python scripts/run_h5_institutional.py \
  --plane-e output/h5-fixtures/plane_e/evidence.json \
  --output-dir output/h5-prekey \
  --prepare-only
```

The live job is gated by a branch push commit whose message contains `[H5-RUN]` and requires repository secret `ZAI_API_KEY`. Live stochastic output is frozen once and evaluated deterministically; a failed confirmatory result is retained.

Production/default Historical Substrate remains OFF.
