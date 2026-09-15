# D2 canonical-JSON prompt structured-completion qualification

This apparatus implements issue #270. It asks whether explicit prompt-side JSON-shape reinforcement can make fresh D2-shaped completions satisfy the unchanged exact structured-output contract on the pinned Z.AI GLM Coding Plan / Hermes substrate.

The intervention is intentionally narrow: the system prompt explicitly requires `actions` to be a JSON square-bracket array of exactly eight strings in case order, provides one literal valid shape example, labels that example as shape-only rather than an answer key, and prohibits copying the exemplar choices. The provider request remains `response_format={"type":"json_object"}`. The exact parser remains the #251 parser: only `actions` and optional bounded ASCII `strategy` are recognized; `actions` must be a list of exactly eight values from `KAPPA`, `MICA`, `ORBIT`, `VELA`. There is no projection, repair, coercion, embedded extraction, or object-to-array conversion.

The fresh namespace is `rw.d2-canonical-json-prompt.v1`. Exactly 72 independent engineering probes are registered, balanced 18/18/18/18 across fresh evaluation, developed development, developed evaluation, and oracle evaluation. Developed shapes are balanced six each across budgets 40/80/160. Seeds begin at 4,300,001, strictly above 4,300,000 as required by #270.

`PASS` requires all 72 probes to be attempted, non-empty, valid under the unchanged exact parser, effectively complete under unchanged #251 semantics, and exact-attributed clean at transport. Clean non-empty exact-parser failures classify `FAIL_STRUCTURED_CONTRACT`; JSON-mode compatibility rejection classifies `FAIL_JSON_MODE_COMPATIBILITY`; apparatus ambiguity fails closed.

No scientific scoring or source acquisition occurs. The consumed #263/#258/#255/#251 outcomes remain unchanged, and no scientific campaign or Acceptance-plane authority is created.
