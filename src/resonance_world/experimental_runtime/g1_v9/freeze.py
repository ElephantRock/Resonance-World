"""Machine-verifiable freeze manifest for the G1 v9 scientific gate.

The manifest is the freeze anchor — not ``contract.digest()`` alone. It
records the contract digest, the code commit it describes, the machine
fingerprint, content hashes of every pinned source and governance file,
the call budget split (decision slots versus model sends), the pinned
statistical fields, the blinded-input definition, and the provider
identity with ``provider_authorized = false``.

Security invariants:

- the manifest contains **no** evaluator seed material and **no**
  commitment keys; blinded inputs are described by custody statements
  only and live outside the manifest and outside published evidence;
- the send cap recorded here is zero until a separate authorization
  names the exact code commit, provider, model, and hard ceiling.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.adapters import sha256_json

from ..machine import StateMachine
from .call_contract import (
    ENDPOINT_FAMILY,
    MODEL,
    PROVIDER,
    RUNTIME_SPEC,
    arm_call_contracts,
    budget_summary,
)
from .contract import G1V9Contract, default_contract
from .scenario import build_machine

MANIFEST_SCHEMA = "g1-v9-freeze-manifest-v1"
MANIFEST_STATUS = "candidate-pre-freeze"

#: Files whose content hashes pin the frozen scenario definition.
PINNED_FILES = (
    "docs/g1-v9-freeze-file.md",
    "docs/g1-v9-scenario-contract.md",
    "src/resonance_world/experimental_runtime/g1_v9/__init__.py",
    "src/resonance_world/experimental_runtime/g1_v9/acceptance.py",
    "src/resonance_world/experimental_runtime/g1_v9/arms.py",
    "src/resonance_world/experimental_runtime/g1_v9/call_contract.py",
    "src/resonance_world/experimental_runtime/g1_v9/contract.py",
    "src/resonance_world/experimental_runtime/g1_v9/evaluator.py",
    "src/resonance_world/experimental_runtime/g1_v9/freeze.py",
    "src/resonance_world/experimental_runtime/g1_v9/memory.py",
    "src/resonance_world/experimental_runtime/g1_v9/power.py",
    "src/resonance_world/experimental_runtime/g1_v9/scenario.py",
)

HYPOTHESIS = (
    "Across independent worlds, a model-mediated agent whose per-context "
    "experience memory persists across a counterbalanced hidden-rule "
    "switch achieves higher post-switch accuracy than the paired agent "
    "whose memory is ablated at the switch, under identical shared "
    "acquisition history, sealed evaluator rules, and equal information."
)
PRIMARY_ESTIMAND = (
    "paired post-switch accuracy difference "
    "post_accuracy(arm A) - post_accuracy(arm B), one difference per "
    "independent world"
)
ANALYSIS_METHOD = (
    "mean of the per-world paired differences with a two-sided 95% "
    "confidence interval over worlds; preregistered paired test; the "
    "independent world is the unit of analysis"
)
PRACTICAL_THRESHOLD_PP = 20
WORLDS_PLANNED = 24


class FreezeManifest:
    """The complete, digestable freeze record (candidate or frozen)."""

    manifest: dict[str, Any]

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest

    def digest(self) -> str:
        """Return the canonical manifest digest (the freeze anchor)."""

        return sha256_json(self.manifest)

    def to_json(self) -> str:
        """Serialize as ``{"digest": ..., "manifest": ...}`` for custody.

        The digest covers the inner manifest only, so auditors recompute
        it from the manifest content alone.
        """

        return json.dumps(
            {"digest": self.digest(), "manifest": self.manifest},
            sort_keys=True,
            indent=2,
        )


def build_freeze_manifest(
    *,
    repo_root: Path,
    code_commit: str,
    machine_fingerprint: str | None = None,
    contract: G1V9Contract | None = None,
    worlds: int = WORLDS_PLANNED,
    practical_threshold_pp: int = PRACTICAL_THRESHOLD_PP,
) -> FreezeManifest:
    """Build the freeze manifest for the current pinned files.

    ``code_commit`` must name the commit whose content the file hashes
    pin. The machine fingerprint is computed from the scenario machine
    bound to the contract. Provider authorization is always false in
    this builder; a frozen, authorized manifest is produced only by a
    separate explicit human authorization step.
    """

    contract = contract or default_contract()
    machine: StateMachine = build_machine(contract)
    fingerprint = machine_fingerprint or machine.fingerprint()

    files_root = Path(repo_root)
    file_hashes = []
    for relative in PINNED_FILES:
        content = (files_root / relative).read_bytes()
        file_hashes.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    arms = arm_call_contracts(contract)
    arm_slots = {
        branch: {
            "model_backed": arms[branch].model_backed,
            "decision_slots": arms[branch].decision_slots,
            "calls_per_decision": arms[branch].calls_per_decision,
            "model_sends_per_world": arms[branch].model_sends,
        }
        for branch in (
            "acquisition",
            contract.arm_a_branch,
            contract.arm_b_branch,
            contract.arm_c_branch,
            contract.arm_d_branch,
        )
    }
    budget = budget_summary(contract)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": MANIFEST_STATUS,
        "code_commit": code_commit,
        "contract_digest": contract.digest(),
        "rules_version": contract.rules_version,
        "machine_fingerprint": fingerprint,
        "scenario_file_hashes": file_hashes,
        "provider": {
            "provider": PROVIDER,
            "model": MODEL,
            "endpoint_family": ENDPOINT_FAMILY,
            "runtime_spec": RUNTIME_SPEC,
            "provider_authorized": False,
            "authorization_reference": None,
        },
        "call_budget": {
            "max_provider_sends_this_gate": contract.max_provider_sends_this_gate,
            "decision_slots_per_world": budget["decision_slots_per_world"],
            "model_sends_per_world": budget["model_sends_per_world"],
            "computational_slots_per_world": budget["computational_slots_per_world"],
            "calls_per_decision": 1,
            "retries_or_replacements_allowed": False,
            "per_arm": arm_slots,
            "note": (
                "decision slots are computational; a model send happens "
                "only for model-backed arms at exactly one send per slot"
            ),
        },
        "statistical_plan": {
            "hypothesis": HYPOTHESIS,
            "primary_estimand": PRIMARY_ESTIMAND,
            "analysis_method": ANALYSIS_METHOD,
            "unit_of_analysis": "independent world",
            "worlds_planned": worlds,
            "practical_threshold_pp": practical_threshold_pp,
            "practical_threshold_status": "proposed-pending-freeze",
        },
        "blinded_inputs": {
            "evaluator_seed": "operator-held material; never in the manifest or evidence",
            "commitment_key": "operator-held HMAC key; never in published evidence",
            "hidden_tables": "sealed ledger only, keyed commitments in public events",
        },
        "holds": [
            "historical W/H/D results are not rewritten",
            "no outcome-based retuning after results are seen",
            "negative results are preserved as first-class records",
        ],
    }
    return FreezeManifest(manifest)


def manifest_digest(manifest: FreezeManifest) -> str:
    """Return the canonical freeze-anchor digest of a manifest."""

    return manifest.digest()


def verify_pinned_files(
    manifest: FreezeManifest, repo_root: Path
) -> tuple[bool, list[str]]:
    """Recompute every pinned file hash; return (ok, mismatched paths)."""

    mismatched: list[str] = []
    for entry in manifest.manifest["scenario_file_hashes"]:
        path = repo_root / entry["path"]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            mismatched.append(entry["path"])
    return (not mismatched, mismatched)
