# D1b execution record

Status: **authoritative replication campaign complete; scientific record frozen**.

Parent mechanism: D1 scientific candidate `46010232f9b73e481eaa6de4b60cc721f4ad2273`, preserved at `af39e10a79c14feafb3cae9903b618829df80489`.

D1b preregistration: issue #163.

## Apparatus freeze

Initial apparatus candidate `abd91e3767f3f01ebdbcdb5ae6dd5f0dd579d2c6` failed before confirmatory execution because the shell attempted to tee a materializer log into a directory that did not yet exist. Confirmatory/evaluator jobs were skipped and no D1b outcome existed.

Transport-only repair commit `2129b0892c35cce70a75dfafdb23d7ca5d33933b` created the output directories before tee. No scientific code, cohort, treatment, statistic, margin, or evaluator changed.

Hosted apparatus workflow `31861922294` then completed successfully with confirmatory and evaluator jobs skipped. It froze:

- D1b plan SHA-256 `e3e7a0698d2cb89b58da973aeef6f4d48ddc6a4f6946212657eb952aeef45bdb`;
- D1b lock SHA-256 `8cea47bed19b054b68023a39a64de1b9b17ab9cb40db737b076075332e5df393`;
- 36 Field pairs, seeds `50000..50035`;
- exact 12/12/12 skill balance;
- exact unchanged D1 scientific runner/evaluator hashes;
- exact conventional P2 NI margin `0.05931396484374999`.

The classifiable candidate `00a5d84e09939e51d54cc59c7ecf1e27f6acbd3c` was created as an unreferenced Git commit, posted prospectively on issue #163, and only then attached to the branch.

## Authoritative replication

Workflow `31861974865` completed successfully.

- apparatus lock: success;
- confirmatory run: success;
- 36 / 36 fresh Field pairs completed;
- confirmatory output executed twice and byte-compared;
- frozen evaluator ran twice against the same output;
- result/audit/manifest byte identity: success;
- evaluator exit statuses: 0 / 0;
- unchanged evaluator classification: `D1-S3 / d1_capability_reproduction_supported`;
- D1b study mapping: `D1b-S3 / fresh capability-reproduction replication supported`.

Artifacts:

- apparatus `9240852006` (`sha256:1a5554c077d7b9184bb0af4744472ebc9b1cab6dbe5a573a9f1b5aec5d811d3f`)
- confirmatory output `9240856188` (`sha256:30e687a2b5de96c612ab34972152373808001e10b50d7b6e2f364f9c569a31c4`)
- evaluation `9240861461` (`sha256:8381d848bd386a5f4274a7634e622f10ef4d400f4696f799f9485676f4cba146`)

Content hashes:

- confirmatory output `a212be892c04c63a66daacf99b9db30bc4b4a0344c8642392e42e257ded8aebb`
- result `56e85a609c32b7dc62c16b94f07efa16c7f550497c8dc81eeb84517bd13dc200`
- audit `34b9e40c4ed35271d0b38c6e0c86433d010063d63f942c8d489ac6b48ee323f0`
- manifest `320ca765c1a2c67a857bc894d222e7d4eb15a0199c6bd0a41010fe3e0c60cd6a`

## Post-classification rule

No D1b confirmatory execution or evaluator rerun is authorized after classification. Credential-free apparatus reconstruction remains available for provenance verification only.

The next scientific/governance step is a separate acceptance review of D1 + D1b. That review, not this experiment, controls any Mechanism Registry transition to `internally_replicated` and must satisfy proposer/acceptor separation.

Production/default Historical Substrate remains OFF.
