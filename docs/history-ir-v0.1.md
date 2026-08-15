# Resonance World — History IR v0.1

Status: **prospective experimental representation**. History IR is not production architecture and is not established as superior to raw evidence. It exists to make future representation experiments explicit and auditable.

## Objective

History IR provides a small typed representation for historical evidence that preserves provenance and structure without storing a task-specific prescriptive conclusion.

The scientific question is whether such typed structure transfers across fresh schemas better, worse, or equivalently to raw structured evidence and compiled semantic state.

## Constitutional boundary

History IR may represent observations and deterministic relations among observations. It may not silently create current authority, hidden World truth, or a recommended action.

```text
History IR != World truth
History IR != current authority
History IR != policy
History IR != mandatory agent belief
```

Every derived IR object must retain pointers to the evidence records from which it was deterministically computed.

## Core types

### EvidenceRef

```text
EvidenceRef {
  evidence_id
  provenance
  observed_at
}
```

References an immutable source observation.

### TemporalOrder

```text
TemporalOrder {
  earlier: EvidenceRef
  later: EvidenceRef
  relation: before | after | same_window
}
```

Represents registered temporal order only.

### ProvenanceGroup

```text
ProvenanceGroup {
  source_class
  members: [EvidenceRef]
}
```

Groups records by an explicit provenance key without ranking the group.

### EvidenceJoin

```text
EvidenceJoin {
  join_key
  members: [EvidenceRef]
}
```

Declares that records share an explicit registered key. It does not state what conclusion follows from the join.

### EmpiricalCount

```text
EmpiricalCount {
  predicate_key
  support_count
  contradiction_count
  evidence: [EvidenceRef]
}
```

A deterministic count over explicitly defined record predicates.

### EmpiricalRate

```text
EmpiricalRate {
  predicate_key
  numerator
  denominator
  evidence: [EvidenceRef]
}
```

A deterministic arithmetic summary. The IR may expose the rate but may not append "therefore choose X" or a policy recommendation.

### ContradictionSet

```text
ContradictionSet {
  subject_key
  alternatives
  evidence: [EvidenceRef]
}
```

Preserves conflicting evidence as a set rather than resolving it into a single authoritative conclusion.

### SupersessionRelation

```text
SupersessionRelation {
  newer: EvidenceRef
  older: EvidenceRef
  dimension
}
```

Represents an explicit supersession relation only when the experimental schema itself defines supersession. It does not grant execution authority.

### CurrentAuthorityRef

```text
CurrentAuthorityRef {
  authority_record_id
  verification_ref
}
```

References current authority through the separate authority system. Historical evidence cannot synthesize or mutate this object.

## Forbidden fields

History IR v0.1 forbids treatment-produced fields such as:

```text
recommended_action
best_action
preferred_policy
should_choose
final_answer
institutional_belief
confidence_in_recommendation
```

unless a later experiment explicitly defines a separate compiled-state treatment. Such fields are not History IR.

## Determinism and auditability

For a frozen evidence payload and frozen IR operator configuration:

```text
IR(evidence) == IR(evidence)
```

byte-for-byte after canonical serialization.

Every derived object must be reproducible without model calls and must identify all source evidence used. A verifier must be able to recompute all counts, rates, joins, contradictions, and supersession relations from the source payload.

## Operator freeze

The operator set is frozen before confirmatory holdout execution. Development may determine which of the above operators are included in a particular experiment, but no new operator may be added after confirmatory outcomes are inspected.

## Relationship to raw structured evidence

Raw structured evidence is the reference condition. History IR is a transformation of that same scientific information, not an information-addition treatment.

A valid comparison requires:

- identical underlying evidence records;
- identical current-authority facts;
- no hidden evaluator truth in either representation;
- deterministic provenance map from every IR object to source evidence;
- a verifier confirming that the IR does not introduce a task answer.

## Relationship to compiled institutional state

Compiled institutional state is a separate treatment class that may contain semantic or prescriptive conclusions derived from history. It must never be relabeled as History IR.

The purpose of separating the classes is causal: future experiments should be able to distinguish effects of raw evidence, structural derivation, and semantic/prescriptive compilation.

## Generalization requirement

History IR is not eligible for architectural promotion because it works on schemas used to design its operators. A positive mechanism must survive fresh schema/operator-family holdouts under `docs/mechanism-governance-v0.1.md`.
