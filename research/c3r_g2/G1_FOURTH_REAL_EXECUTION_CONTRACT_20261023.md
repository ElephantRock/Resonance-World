# G1 fourth crossed REAL GLM-5.3 experiment — internal run contract (2026-10-23)

**User authorization:** the project owner explicitly authorized genuine paid experimentation and removed any spending ceiling. No independent or external auditor, human signoff chain, outside witness or remote archive is required. All remaining gates are algorithmic dependencies needed to protect experimental interpretation and avoid duplicate sends.

**Execution code:** scripts/run_c3r_g1_fourth_crossed_live.py
**One-shot runner:** .github/workflows/c3r-g1-fourth-crossed-once.yml
**Deployment:** normal trusted push event on the isolated research branch, triggered exactly by first creation of G1_FOURTH_REAL_DISPATCH_20261023.md. The executable workflow should be retired after observation; GitHub Actions rerun is NOT an acceptable recovery mechanism for ambiguous sends.

## Frozen attempted experiment

- Model: GLM-5.3 (Z.AI Coding endpoint previously used in the third real pilot), temperature 0, reasoning_effort low.
- Maximum: **40 separate physical model attempts** for **8 context-level units**, 4 arithmetic and 4 text, with within-family privately seeded balanced assignment of true A/B targets (2 + 2 per family).
- First **16 graded source attempts** (2 per context), with a strict internal source lock before any qualification network request. All 16 must produce accepted A/B grades to unlock qualification; otherwise all 24 holdout slots become not_sent_after_source_failure and no holdout calls are made.
- Then **24 new qualification attempts**, 3 arms per context: learned receives its own two actual development choice/grade records; fresh receives no history; neutral receives source task IDs and equally long masked action/grade placeholders. Qualification grades are withheld until the full 40-slot evaluator ledger closes. Source and holdout tasks have disjoint IDs/operands.
- Maximum 4 concurrent independent provider requests. Source attempts in each unit are sequential to permit authentic feedback; independent units run concurrently. The holdout arm requests can run concurrently *only after source lock*.
- Provider budget per physical request: 16,384 generated tokens maximum, including mandatory reasoning; timeout 180 seconds. Separate one-send transport ledger plus exclusive fsynced per-slot durable pre-send journal; no retries, no automatic reset, no silent duplicate attempts.
- Report grade for each attempted or missing slot plus provider-reported prompt, reasoning and completion token counts; preserve the fixed 40-slot denominator. No raw provider messages, prompts, secret API keys, private target seed or target mapping in public artifact.

## Descriptive planned analysis

Compare learned vs fresh and learned vs neutral within each family. Truth labels are balanced A/B within family. Each context and its 3-arm triplet form one descriptive unit; 8 units do NOT support a powered causal estimate or independent-agent persistent-memory proof. Token parity is **not** guaranteed by matching characters; report actual provider token usage as a diagnostic. Evaluate both learned/controls choice distributions and ITT correctness including missingness.

**Important reporting boundary:** Results show empirical behavior of the public provider endpoint and the internally graded feedback context, not independently audited provider billing, external timestamps, or latent acquired autonomous memory. scientific_acceptance stays false pending a larger scientifically justified replication.

## Operational priority

Do not add external auditors, checkpoints, signatures or blocking services. On failure, classify and preserve every attempted/missing logical slot; do not rerun ambiguous already-sent requests. Proceed directly to analysis of the real responses after the action completes.
