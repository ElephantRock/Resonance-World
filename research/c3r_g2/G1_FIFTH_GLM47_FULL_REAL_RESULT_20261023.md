# G1 — First complete 40/40 REAL model crossed trial (2026-10-23)

**Observed experiment:** GitHub Actions [run 39961127844](https://github.com/ElephantRock/Resonance-World/actions/runs/39961127844) succeeded, using actual Z.AI GLM-4.7 Coding requests inside GitHub Actions. Artifact ID **12505255385**, name g1-glm47-fallback-real-and-readiness-20261023, ZIP SHA256 **9c652477657e8de49071be7f42baa73bccdf4dfeca01dab21aa03c8dce125f9e**. Trial JSON SHA256 **60b0ba442c8483d976b41904334b7abbbb6b9504824432168b50e1c082ab5547**; readiness JSON SHA256 **2e9dc48d61880122d2888e4da8cdf1b2e58d407ca678e9186a6bee30259fd5f5**.

## Experimental condition

New model GLM-4.7, Z.AI Coding endpoint, requested thinking.type=disabled for ALL arms, temperature=0, output cap 1024, up to four concurrent requests and 180-second transport timeout. This was a **prospective change of model and prompt**, NOT a direct replication of the previous GLM-5.3 / GLM-5.2 condition.

**Uniform fallback instruction:** Every arm was instructed that if no actual graded source evidence exists, choose A immediately as the predeclared default; if source grades do exist, infer A/B from those outcomes. Therefore Fresh and Neutral implement an explicitly defined, deterministic no-evidence baseline, NOT unconstrained model guessing.

Two separately reserved technical probes before the experiment checked Fresh and Neutral text control prompts at max_tokens=512. Both returned valid short A/B responses (Fresh: 50 completion tokens / 47 reasoning; Neutral: 9 completion / 6 reasoning). These **two extra physical sends are outside the scientific 40-slot denominator**.

## Full 40-slot denominator, all observed

- **16/16 real graded source calls accepted**.
- **24/24 real holdout calls accepted**, all 8 context triplets fully observed.
- **40/40 provider request slots reserved** and all resulted in an HTTP 200, valid A/B completion; no provider errors, missing attempts or invalid answers in this run.
- Internal source lock closed after 16 source claims before the 24 holdout calls; holdout grades withheld until finalization. No external witness or auditor.

| Family | Learned correct | Fresh correct | Neutral correct | Complete triplets |
|---|---:|---:|---:|---:|
| Arithmetic | **4/4** | 2/4 | 2/4 | 4/4 |
| Text | **4/4** | 2/4 | 2/4 | 4/4 |
| **Total** | **8/8** | **4/8** | **4/8** | **8/8** |

Learned chose A four times and B four times and matched all balanced hidden targets. Fresh and Neutral each chose A eight times; balanced A/B targets yielded four correct each. Both learned-minus-control differences are **+50 percentage points** descriptively.

Across the paired eight context units, Learned wins four pairs, loses zero and ties four against EACH control. The conditional two-sided exact sign/McNemar test on four discordant pairs yields **p=0.125**, not confirmatory scientific acceptance.

## Reported token usage

40-study provider-reported usage: **9,016 prompt tokens**, **2,372 completion tokens**, including **2,234 reported reasoning tokens**. The two readiness probes additionally reported 455 prompt / 59 completion (53 reasoning) tokens, outside the 40.

Learned qualification: 1,927 prompt, 857 completion (831 reasoning).
Fresh qualification: 1,679 prompt, 428 completion (397 reasoning).
Neutral qualification: 1,943 prompt, 65 completion (37 reasoning).

**Important:** Provider reported nonzero reasoning usage although the API was sent thinking.type=disabled. Do NOT assert the endpoint guaranteed zero reasoning. Compute and prompt-token parity are NOT demonstrated; vendor billing was not independently reconciled.

## Research interpretation and next experiment

This is strong **functional/operational evidence** that a model receiving reinserted graded examples can pick the context's hidden A/B choice when the two controls use a fixed A fallback. It is NOT evidence of persistent agent memory, parametric model learning, institutional regeneration, or an externally validated G1 causal effect. The +50pp difference is largely expected by design from balanced binary hidden targets plus deterministic A baselines if the learned arm uses its labeled feedback. The study is small (8 reused context/holdout triplets), changed both model and prompt from earlier runs, does not match token/compute exposure and is not a powered causal study.

The next scientifically discriminating step is a **genuine persistent experience-store agent vs fresh and neutral agents** on NEW private task items and context sets, with internally registered balanced allocation, comparable token/compute and multiple seeds. The user requested no external auditor or approval chain; keep all assurance internal and nonblocking. Do not automatically promote G1 scientific_acceptance or the Pattern Register. PR #310 remains Draft.
