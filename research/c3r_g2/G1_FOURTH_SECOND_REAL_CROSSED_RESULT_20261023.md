# G1 fourth crossed: second REAL GLM-5.3 run — empirical results (2026-10-23)

**Observed provider experiment** (not a synthetic fixture):
- GitHub Action: https://github.com/ElephantRock/Resonance-World/actions/runs/39912520068 — `success`.
- Run ID: `g1-crossed-real-20261023-02`; execution commit `421f0e00957733af6382dc7e28ea432e2828540e`.
- Artifact ID **12484321406** (`g1-fourth-real-crossed-20261023-b`); ZIP SHA256 `aa634a4ef7a394cebf132e5c0fc9868a9491961a9df238b1761640762cda0238`; JSON SHA256 `e1e80c0cea029fd78456d0b64caefd728178f00dba7aa4f8a19bd1f03000fae7`.
- Public plan digest: `00661fe7dd37086f08f8458b13a57cc1e8b2123fd00e31918dedf8d26a3cdf6e`.
- Endpoint: Z.AI Coding, model `glm-5.3`, reasoning effort low, token cap 16384, up to 3 independent concurrent calls. User authorized actual paid experiments; no outside auditor or approval service was used.

## Prespecified 40-slot denominator

| Source or holdout | Accepted | Provider errors | Invalid format | Not sent | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 12 | 4 | 0 | 0 | 16 |
| Qualification | 13 | 4 | 1 | 6 | 24 |
| **All attempts** | **25** | **8** | **1** | **6** | **40** |

**34 physical attempts were durably reserved**. This is the reservation count, not independently verified network delivery or billing. Six holdout requests were properly skipped because two text contexts each lacked two accepted development grades. The 16-row source checkpoint was written and verified internally, allowing the six eligible contexts to continue.

## Within-family heldout comparison

| Family | Learned | Fresh | Neutral | Fully observed triplets |
| --- | ---: | ---: | ---: | ---: |
| Arithmetic (4 contexts) | **4/4** | 1/4 | 1/4 | **4/4** |
| Text (4 contexts) | 1/4 (one accepted) | 0/4 (zero accepted) | 0/4 (zero accepted) | **0/4** |
| All 8 planned contexts, treating unresolved as not correct | 5/8 | 1/8 | 1/8 | **4/8** |

The arithmetic observed learned-minus-fresh and learned-minus-neutral differences are **+3/4 = +75 percentage points** each (three favorable discordant pairs and one tie for each comparison). A simple conditional two-sided exact sign test over the three discordant pairs would give p=0.25, *not* a powered or confirmatory result. In arithmetic, the model's learned arm was correct in both A-target and B-target contexts, whereas Fresh/Neutral were correct only in one of four each. The arm result is descriptive; task operands and prompts are reused from a frozen small pilot.

The text arm did **not** produce a full qualification triplet. Two text contexts had complete source; their six qualification requests yielded 1 accepted Learned, 1 invalid-length Learned (completion_tokens_reported=16384, finish_reason=length), and four provider errors. The other two text contexts' holdouts were not sent. Thus any text learned-over-control accuracy claim would be unsupported.

## Reported provider token consumption, not verified invoice

- **Prompt tokens:** 4,512 (source 1,987; qualification 2,525).
- **Completion tokens:** 28,571 (source 11,330; qualification 17,241).
- **Reasoning tokens reported within completion:** 12,386 (source 11,291; qualification 1,095). One failed text qualification has an unusually large 16,384-token completion with `length` finish, illustrating output-budget exhaustion/malformed output risk.
- Missing/provider-error rows have no usage figures, so the sums are **lower bounds of observable provider-reported usage** and not total invoice amounts.

## Interpretation and next empirical step

This is meaningful *real-model* evidence that **explicit graded prompt feedback can improve new-item choices within the small arithmetic task family** relative to a no-history and grade-free-history control. It does **not** prove stable acquired memory or emergent autonomous agent learning: all graded feedback was supplied again inside prompts, the sample comprises four complete context-level triplets, token parity is not established (arithmetic neutral prompts used 2 more provider-reported input tokens than learned on each of four pairs), model/grade/billing attestation is internal-only, and G1 `scientific_acceptance=false`.

**Operational diagnosis:** provider errors and long reasoning/output exhaustion concentrate in text tasks; the next run should be a fresh-ID text-specific **technical reliability experiment** with bounded concurrency, explicit safe HTTP/failure classification (never provider response bodies), and incomplete-context continuation. Do not blindly rerun either previous real run or count their missing outcomes as successes. Avoid external gatekeepers or new approval chains.
