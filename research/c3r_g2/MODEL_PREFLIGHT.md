# C3R G1 — default-off model interface and evaluator boundary

**State:** exploratory construction, unfrozen; opt-in technical qualification is now authorized by the user, but no live run has been evidenced. No scientific authorization or acceptance is implied.
This extension does not change G1/G2 scientific standing and does not unlock G3/G4.

## Scope and why a new boundary is needed

The existing D2-vNext Hermes clients have fixed provider behavior, retry rules and
diagnostic/qualification authorization boundaries. C3R must not borrow those
clients' frozen study semantics or execute provider sends under an unrelated
campaign. Instead, `src/resonance_world/c3r_g1_model_boundary.py` declares
a small `ModelChoicePort` protocol. It contains **no network implementation by itself**. A separate, explicitly enabled, narrowly pinned Z.AI standard-API transport now exists in `c3r_g1_zai_transport.py`; see `LIVE_SMOKE_RUNBOOK.md`.

The injected port receives a `ModelChoiceRequest` with a strict A/B prompt,
the public task operands, and only **prior graded source-development feedback
for the same opaque context**. It returns `ModelChoiceCompletion` with exact
output text plus optional *adapter-reported* usage data. No model, SDK, API key,
or network client is created automatically.

## Public workflow

1. A local `ModelCohortLock` validates no duplicate IDs or public task payloads
   across development and qualification, and deterministically hashes both.
   For science, an independent party must pre-commit and attest this lock.
2. The runner sends development tasks in prescribed order to the injected
   learned port. Choices must be the **exact single character A or B**.
   No coercion, retries, answer repair, or hidden best-of-N selection occurs.
3. The evaluator grades only accepted precommitted actions. Source development
   feedback is returned **after each accepted action**, and never includes
   hidden target plans or evaluator internals.
4. Accepted graded source episodes are linked to deterministic observation
   digests. These checks bind content but **do not authenticate grader ownership**.
5. On disjoint qualification tasks, the learned port can read its frozen
   development feedback while a fresh comparator receives none. Neither
   gets any qualification outcome as subsequent feedback.
6. **Every** prescribed attempt stays in the denominator. Invalid formatting,
   adapter exceptions, invalid result type, and exceeded *reported* send cap
   are distinct failures. Paired-analyzable counts only include trials accepted
   for **both** learned and fresh ports.
7. The canonical diagnostic report omits raw prompts and outputs; it records
   only bounded status, output digest, model identifier and usage metadata.
   No significance test or scientific promotion is computed.

## Explicit limitations (mandatory for claims)

- The grader and adapter share a Python process in construction tests; this
  is API-level information separation, **not process or service isolation**.
  A malicious injected port could retain a reference to the grader via
  external application code. Scientific execution needs independently
  controlled grading and evidence admission.
- The adapter's `physical_sends_reported` is unauthenticated. Checking it
  **after** a response cannot prevent extra physical sends. Live execution
  needs a separately enforced pre-send budget, transport ledger, request
  attribution, timeout policy and credential/endpoint allowlist.
- The current local tasks reveal arithmetic operands and a context label.
  The hidden context rule is fixed and artificial. High scores do not imply
  autonomous model acquisition or transfer to new task schemas.
- A model with internal memory across calls is not automatically equivalent
  to a fresh untrained model. Before a live study, control model identity,
  session state, prompt history, temperature, runtime, cache and retry policy.
- Qualification is a diagnostic holdout, not a confirmatory powered sample.
  Repeated tasks and agents within one organizational development unit are
  not independent organizations.
- The port itself is a protocol, not an implementation for a particular
  model provider. Existing tests use only deliberately simple offline stubs.
- Model response and prompt content are intentionally not retained in the
  summary, so diagnosing future real failures will require a separate
  privacy- and authority-governed trace policy without polluting evaluation.

## Research preflight checklist (not approved)

| Requirement | Current state | Before a live study |
| --- | --- | --- |
| Model port and strict action parser | Constructed | Provider-specific implementation reviewed |
| Training versus qualification feedback isolation | Construction tests | Separate grader process and externally attested lock |
| Complete attempt denominator | Constructed | Backend-attributed attempted/accepted send ledger |
| Source learning beyond deterministic policy | Not demonstrated | Independently powered prospective G1 study |
| Fair trained versus fresh baseline | Fixture-level | Same model/version/compute/session and matched resources |
| Source cohort and holdout semantic independence | Only public-payload uniqueness | Task-generation lock and semantic contamination audit |
| Cost and failure yield | Adapter-reported totals only | Transport-trusted per-schema analyzable yield |
| G2 independent organizational effect | Not demonstrated (C = D in fixture) | New non-equivalent treatment, honest C/B controls, separate G2 freeze |
| G3 successor survival; G4 net regeneration | Not implemented | After G2 independent evidence |

## Negative tests required

- Adapter returning malformed A/B text cannot produce successful evidence.
- Adapter exception or reported over-cap usage cannot disappear from counts.
- Trained port can observe only development feedback for matching contexts.
- Qualification outcomes are never echoed into a later qualification request.
- Duplicate task IDs or public task payloads across splits fail closed.
- Adversarial context text cannot inject new prompt instructions.
- The report must not preserve raw response or prompt text.
- Two injected deterministic stubs should reproduce the same canonical report.

## Runbook

Local CI must run `ruff check .` and `pytest -q`. No CLI that
contacts a provider is included, and no environment credential is read.
The opt-in provider adapter now exists with a **maximum eight-send technical ceiling**,
pre-dispatch reservation, a terminal transport-failure circuit breaker,
and the existing GitHub repository secret `ZAI_API_KEY`, mapped to the internal CLI variable `C3R_ZAI_API_KEY`. It can be
used only through the explicit technical smoke CLI/manual workflow described
in `LIVE_SMOKE_RUNBOOK.md`; this does **not** satisfy the evaluator,
randomization, analyzable-N or inferential preflight for scientific acceptance.

C3R remains posthoc-motivated exploratory apparatus until a preregistered
study establishes independently replicated causal effects.
