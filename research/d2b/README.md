# D2b — fresh stochastic capability-reproduction replication

Status: **prospective zero-provider replication scaffold; not yet a provider-execution candidate**.

Preregistration issue: #186.

Parent mechanism node: `d2_stochastic_capability_reproduction`, currently `discovery_supported` after independent Acceptance review #183 and mainline promotion commit `03f2ce01c9376492503d59da97a9befd384edc90`.

D2b is the fresh replication required before the mechanism may be considered for `internally_replicated`. It is the same mechanism node, not a child hypothesis and not a repair/rerun of D2-C1 or D2-C2.

The replication principle is strict: reuse the D2-C2 scientific contract without tuning from D2-C2 outcomes; change only fresh cohort identity plus replication metadata. The already-audited 18×20 durable execution topology is retained as engineering apparatus, but no provider runner or authorization marker exists in this scaffold.

Current sequence:

1. freeze D2b scientific/replication plan and implementation contract;
2. materialize a completely fresh 360-pair cohort in the reserved `3,200,000` namespace and hash-lock it;
3. derive the D2b runner/aggregator/evaluator from the D2-C2 apparatus with only replication identity/cohort changes;
4. pass zero-provider tests, general CI, and dedicated D2b audit;
5. post the exact candidate SHA and cohort hash to #186;
6. only after separate explicit authorization, add the sole run marker and execute provider shards;
7. preserve the evaluator-emitted replication class;
8. if and only if D2b-S3 is preserved, open a separate independent Acceptance-plane review for `discovery_supported → internally_replicated`.

No registry promotion is automatic. Production/default Historical Substrate remains OFF.
