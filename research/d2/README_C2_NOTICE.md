# D2-C2 notice

Issue #180 is the prospective program record for D2-C2.

This branch now contains the complete **preauthorization** C2 scientific apparatus: fresh cohort lock, request/power contract, deterministic shard map, provider shard runner, credential-free aggregator, frozen evaluator, tests, zero-provider audit, and a marker-gated provider workflow.

It still intentionally contains **no `research/d2/RUN_D2_C2_CONFIRMATORY` authorization marker**. The provider workflow triggers only when that marker is added on the designated branch. Therefore nothing currently committed authorizes a provider call.

Before authorization, the exact final scientific candidate SHA must pass general CI plus the dedicated credential-free C2 preexecution audit and be posted prospectively to issue #180 with the exact cohort hash and audit run IDs. Only a subsequent commit adding the marker as the sole post-lock file change may launch provider execution.

Production/default Historical Substrate remains OFF, and no registry promotion is authorized.
