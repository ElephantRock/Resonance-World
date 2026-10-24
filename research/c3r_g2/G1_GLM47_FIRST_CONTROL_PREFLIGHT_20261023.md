# GLM-4.7 REAL no-thinking readiness probe, first pass (2026-10-23)

Source: GitHub Actions run [39960216630](https://github.com/ElephantRock/Resonance-World/actions/runs/39960216630), artifact ID **12504151880** (ZIP SHA256 **73f2d66450e313223e183b43a12e7cc2418a5527f770f54cd27f52a7ae154ef3**). New G1 trial was **not launched** because the automatic control-readiness test failed.

Exactly **two real Z.AI GLM-4.7 Coding endpoint control prompts**, with thinking.type=disabled, 512-token output cap and 90-second timeout:

| Control | Result | Completion tokens | Reasoning tokens |
| --- | --- | ---: | ---: |
| Fresh — no history | Invalid; finish_reason=length | 512 | 510 |
| Neutral — masked development history | Valid short answer; finish_reason=stop | 23 | 19 |

The nonthinking request did not eliminate reasoning tokens in this calibration, and Fresh exhausted the short output cap. This evidence isolates a *prompt-format/control availability* disparity in the same model and endpoint; it does not reveal the underlying provider's implementation of the thinking flag. Both technical requests are excluded from the G1 40-slot experimental denominator and were never retried.

## Prospectively changed protocol for new trial

The next trial explicitly states a uniform fallback in every arm prompt: **if no actual graded outcome is present, choose A immediately** because the hidden context rule is randomized independently of public task operands. This is a deliberate substantive **prompt protocol modification**, not an exact replication of the earlier GLM-5.3/5.2 trials. Learned still receives actual development grades; neutral receives masked grades; fresh receives none. All arms receive the *same* fallback instruction. This makes control choice an explicitly specified fixed-guess baseline rather than measuring unconstrained model guessing; balanced A/B hidden rules imply 50% baseline in expectation, but that is a design expectation and not a measured result.

A fresh pair of real control-readiness probes will validate the new prompt before launching a separate 40-slot GLM-4.7 cohort. The previous probe's two sends and the prior science cohorts must not be replayed or pooled as independent task-material replications. No third-party authorization is required.
