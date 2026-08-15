# D1 execution record

Status: **authoritative confirmatory campaign complete; scientific record frozen**.

Parent design: issue #160. Program base: `09da54404eca975c512137c70bb94d2a207e8178` from program PR #158.

## D1-0 development calibration

D1-0 was development-only and never counted as confirmatory evidence. The initial calibration surfaced a prospective integrity flaw: a raw deterministic source seed was exported as provenance and could reconstruct source-private state. Before any confirmatory D1 data existed, that field was removed from the Capability Artifact and classified as forbidden reconstructive information. Repaired hosted calibration preserved behavioral/planning values.

The final apparatus lock used calibration SHA-256 `9ec5481eaf9106fe670ccd5a25efb1c2ab1710d2062ff143e28ebb050a1b2799`, a 90% conventional reproduction-fidelity convention, and an absolute P2 NI margin `0.05931396484374999`.

## Pre-confirmatory lock

Apparatus commit: `f11037e4f58cde6ba4e58c56ee93202da6f31681`.

Hosted apparatus workflow `31861239586` completed credential-free with confirmatory/evaluator jobs skipped. It froze:

- 36 independent confirmatory Field pairs, seeds `30000..30035`;
- exact 12/12/12 skill-alias balance;
- confirmatory plan SHA-256 `8223d441f8399d89901ecd7f704d8744c571a8035c7ebdc94150435f92ba8858`;
- lock report SHA-256 `15f479faae0f9d2a9ec9d859b1359c103c2d1075628ba1e872cdb71a900e5cfd`;
- fixed-sequence P0→P1→P2 analysis;
- fixed normal + 100,000-replicate bootstrap gate implementation;
- no early stopping / missing-pair integrity policy;
- Capability Artifact private/reconstructive export boundary.

The exact classifiable candidate `46010232f9b73e481eaa6de4b60cc721f4ad2273` was created as an unreferenced Git commit, posted prospectively on issue #160, and only then attached to the D1 branch.

## Authoritative confirmatory execution

Workflow `31861296898`:

- apparatus lock: success;
- confirmatory run: success;
- 36 / 36 independent Field pairs completed;
- confirmatory output executed twice and byte-compared before upload;
- frozen confirmatory output SHA-256: `f65e67fee740a5f0a2471479af08e18571c8592ca1e6c6f34c5c2486770df936`;
- output artifact: `9240651101` (`sha256:b1baac6c2ae582a4566bbd5ea3950ae6a902666aa6e3dfdb1cf56f7eea5dc659`).

The first evaluator job failed before reading scientific output because the artifact was addressed using a nonexistent `d1-run-a/` subdirectory. The artifact stored `d1-confirmatory-output.json` at its root.

## Evaluator-only transport repair

Repair commit: `83f4b5d1877095163e8e5911bffb7f908675c96b`.

Repair workflow `31861464055`:

- confirmatory-run: skipped;
- original frozen-evaluator: skipped;
- evaluator-only repair: success;
- downloaded exact apparatus/output artifacts from authoritative workflow `31861296898`;
- verified plan, lock, and output SHA-256 values before invoking evaluation;
- invoked unchanged evaluator twice against scientific candidate `46010232...`;
- result/audit/manifest byte identity: success;
- evaluator exit statuses: 0 / 0;
- classification: `D1-S3` / `d1_capability_reproduction_supported`;
- evaluation artifact: `9240703702` (`sha256:a8958c107dfecfedf11e10da9dc45e0ef16aae6ba7d1421543a4a7a071c98844`).

## Post-classification rule

No D1 confirmatory execution, evaluator repair, or scientific retuning/rerun is authorized after classification. The workflow retains credential-free D1-0/apparatus reconstruction only.

A fresh D1b study must be separately preregistered and must not reuse D1 confirmatory seeds. Only successful fresh replication may motivate `internally_replicated` registry acceptance by an independent acceptor.

Production/default Historical Substrate remains OFF.
