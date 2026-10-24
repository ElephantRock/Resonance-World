# G1 third real GLM-5.3 exploratory pilot: two schemas and neutral metadata control

**Run date:** 2026-10-22. **Evidence class:** observed live-model responses, small exploratory apparatus; **scientific_acceptance=false**. Not powered or independently graded, not evidence of autonomous persistent agent memory.

## Authenticated references within this research branch

- **GitHub Actions completed run:** https://github.com/ElephantRock/Resonance-World/actions/runs/39800889211
- **Successful job:** 119900902278, action `third-once-marked-commit`.
- **Execution commit:** `2510e2624bd0b30058db4e9f5fa9e737c8c66cc0`.
- **Sanitized GitHub Actions artifact:** `c3r-g1-third-real-multischema-neutral-20261022`, ID **12435438427**, 14-day GitHub retention; downloadable ZIP **SHA256 d59b4b7ef22ccd168efb8d812a40b9dd49f62e9bdf4f3b6b3be8c42334df0820**.
- **JSON within ZIP:** `real-two-schema-neutral.json`. Public experiment lock SHA256 `c8cdee68a0ea157bfe24fcef3336aa0b59422c484d422e3f7a1c79955c7d9cbe`.
- **Execution configuration:** `glm-5.3`, configured Z.AI Coding endpoint, 16,384 output-token ceiling including mandatory reasoning, `reasoning_effort=low`, timeout 180 s, no retries, eight physical reservations maximum. Actual backend billed send count/invoice not independently attested.
- The initial re-run workflow encountered GitHub `startup_failure` with **zero second-attempt jobs**. A fresh marker-based `push` workflow was successfully executed once. **That workflow was deleted immediately after completion**, and no additional live call has been authorized by this run.

## Design — 8 calls, two contexts, 3 arms

Exactly **one real graded development attempt per family**, followed by one new qualification task for each of learned/fresh/neutral metadata control. The families use different contexts and deliberately different target labels:

| Family | True rule | Source | Qualification |
| --- | --- | ---: | ---: |
| Arithmetic operation order | **B** = multiply then add | 1 | 3 arms × 1 item |
| Text transform order | **A** = replace then uppercase | 1 | 3 arms × 1 item |
| **Total** | | **2** | **6** |

- **Learned** sees its own actual development choice and correct/incorrect grade; no holdout grades are passed.
- **Fresh** sees no development records.
- **Neutral metadata control** sees the public source task identifier but only `choice=?; success=?????`, not actual choice or grade. This neutral history uses the same *character count* as learned history and masks both value and true/false length, but **token-count parity is not independently tested**.
- Arm order was fixed/interleaved, not randomized. Family and target identity are still **confounded**. These are two contexts, **not independently replicated learner units**. The small preselected targets are visible to the local test author; grader/operator independence is not established.

## Exact observed responses

The original ZIP was downloaded and checked against its GitHub digest. The model's choice was reconstructed by mapping the retained SHA256(choice) to SHA256(A) and SHA256(B), not by interpreting aggregate grades.

| Stage | Family | Arm | Choice | Correct | Completion tokens | Reasoning tokens |
| --- | --- | --- | --- | --- | ---: | ---: |
| Development | Arithmetic | Learned source | A | No | 6,307 | 6,304 |
| Development | Text | Learned source | A | Yes | 940 | 937 |
| Qualification | Text | Neutral control | A | Yes | 80 | 77 |
| Qualification | Arithmetic | Fresh | A | No | 1,590 | 1,587 |
| Qualification | Text | Learned | A | Yes | 8 | 5 |
| Qualification | Arithmetic | Learned | **B** | **Yes** | 10 | 7 |
| Qualification | Text | Fresh | A | Yes | 520 | 517 |
| Qualification | Arithmetic | Neutral control | A | No | 43 | 40 |
| **Total** | | | | | **9,498** | **9,474** |

All eight local ledger entries show HTTP **200**, no recorded transport failures; all eight observations have `finish_reason=stop` and valid exact A/B outputs. **2/2 three-arm qualification triplets complete**. The 9,498/9,474 values are **provider API-reported usage**, not independently verified billing.

## Correctness by arm and family

| Family | Learned | Fresh | Neutral metadata |
| --- | --- | --- | --- |
| Arithmetic, B correct | **1/1** | 0/1 | 0/1 |
| Text, A correct | **1/1** | 1/1 | 1/1 |
| **Total** | **2/2** | **1/2** | **1/2** |

**Arithmetic behavioral contrast:** the one development call chose A and received an explicit *incorrect* grade. At qualification the learned prompt with that grade chose B, while both grade-free controls continued to choose A. This is consistent with the model using its **in-context graded feedback**.

**Text behavioral contrast:** the one development call chose A and was graded correct; all three heldout variants chose A. This family provides **no observed learned-over-control accuracy lift**.

## Three real G1 exploratory runs viewed descriptively

| Run | Family / true law | Learned | Fresh | Sham / neutral |
| --- | --- | --- | --- | --- |
| 1: GitHub 39780461001 | Arithmetic / B | 2/2 | 0/2 | not tested |
| 2: GitHub 39790290483 | Arithmetic / A | 2/2 | 2/2 | misleading sham 0/2 |
| 3: GitHub 39800889211 | Arithmetic B + text A | 2/2 | 1/2 | grade-free neutral 1/2 |

Across these runs the **fresh arm selected A on all six qualification calls**; the learned arm selected the correct local target on all six. This is *descriptive* across different, unrandomized protocols and tasks, not evidence of a six-unit experimental sample. A strong **default A response tendency** remains a credible explanation of the fresh comparisons, whereas true graded feedback appears to update the model's choice in B-target contexts.

## Scientific limits and next empirical decision

- This tests history **reinserted into prompts**, not enduring state or skills acquired by an agent independently of the prompt.
- One qualification item per family and one graded development item per family; no powered effect estimate.
- Correct target is confounded with task family in run 3. True counterbalancing must occur **within each family** over multiple opaque contexts and independent learner units.
- Token matching is only approximate by **character count**. A neutral metadata placeholder is not equivalent to a full plausibly graded sham history.
- No blinded independent grader, independently witnessed timestamps, model-identity hardware attestation or provider invoice reconciliation.
- Consequently **no G1 acceptance, Pattern Register promotion, G2/G3/G4 inference or main merge**.

**Next evidence-producing experiment:** preregister four contexts (arithmetic A/B and text A/B), randomize order and arm exposure, add multiple true graded development items per context, and keep neutral feedback matched at the *provider-token* level. Use a separately approved bounded physical-send envelope, not more preparatory architecture.

The action's one-shot live workflow was retired after its successful run; this report only records completed evidence, not future permission for additional sends.
