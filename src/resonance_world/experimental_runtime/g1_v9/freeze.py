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
from datetime import datetime
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
FROZEN_UNAUTHORIZED_STATUS = "frozen-unauthorized"

#: Mandatory top-level fields of a freeze manifest (strict mode).
REQUIRED_MANIFEST_KEYS = (
    "schema",
    "status",
    "code_commit",
    "contract_digest",
    "rules_version",
    "machine_fingerprint",
    "scenario_file_hashes",
    "call_budget",
    "statistical_plan",
    "provider",
    "blinded_inputs",
    "operational_contract",
    "holds",
)

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

#: Pinned FINAL by governance annex A (PR #312 review): the practical
#: effect threshold. Changing it requires a new freeze record.
PRACTICAL_THRESHOLD_PP_FINAL = 20
#: Pinned FINAL by governance annex A (PR #312 review): the minimum
#: number of analyzable worlds. Changing it requires a new freeze record.
MINIMUM_ANALYZABLE_WORLDS_FINAL = 18


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
    status: str = MANIFEST_STATUS,
) -> FreezeManifest:
    """Build the freeze manifest for the current pinned files.

    ``code_commit`` must name the commit whose content the file hashes
    pin. ``status`` is ``candidate-pre-freeze`` by default; the final
    emission passes ``frozen-unauthorized`` (see
    ``FROZEN_UNAUTHORIZED_STATUS``). Provider authorization is always
    false in this builder; a frozen, authorized manifest is produced
    only by a separate explicit human authorization step.
    """

    if status not in (MANIFEST_STATUS, FROZEN_UNAUTHORIZED_STATUS):
        raise ValueError(f"unknown manifest status {status!r}")
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
        "status": status,
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
            "statistical_test": "two-sided paired t-test over the per-world "
            "post-switch accuracy differences",
            "confidence_interval": "95% t-based confidence interval on the "
            "per-world paired differences",
            "statistical_success": "lower bound of the 95% CI > 0",
            "practical_success": "lower bound of the 95% CI > "
            f"{practical_threshold_pp / 100:.2f} (independent criterion; "
            "both claims reported separately)",
            "incomplete_worlds": "worlds with failed/expired sends are "
            "apparatus failures; not replaced; analysis runs on analyzable "
            "worlds with a minimum analyzable worlds floor of 18 "
            "(proposed-pending-freeze); apparatus failures recorded "
            "separately",
            "decision_correlation": "planning power/MDE is reported over an "
            "intra-world decision-correlation (rho) sensitivity grid via "
            "power.intra_world_correlation_table; MDE values are "
            "scenario-specific under declared rho assumptions, not "
            "guarantees",
        },
        "operational_contract": {
            "identity_version": "pinned at authorization",
            "input_limits": "pinned at authorization",
            "output_limits": "pinned at authorization",
            "timeout_and_failure_rules": "pinned at authorization",
            "physical_send_meter": (
                "call_contract.py is accounting and policy, not a runtime "
                "meter; an enforcing send meter is implemented before any "
                "authorized execution"
            ),
        },
        "blinded_inputs": {
            "evaluator_seed": (
                "per-world independent evaluation seeds derived from "
                "operator-held material; raw seeds held by the evaluator "
                "until outcome lock; never in the manifest or evidence. "
                "Only the DERIVED rule tables are sealed at genesis - the "
                "raw seed is not"
            ),
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


def _is_full_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value)
    )


def verify_freeze_anchor(
    manifest: FreezeManifest,
    repo_root: Path,
    *,
    expected_commit: str,
    require_status: str | None = None,
    expected_machine_fingerprint: str | None = None,
    expected_contract_digest: str | None = None,
    strict_frozen: bool = False,
    outer_digest: str | None = None,
) -> tuple[bool, list[str]]:
    """Strictly verify a freeze anchor against a named Git commit.

    With ``strict_frozen=True`` the verification becomes fail-closed for
    the final ``frozen-unauthorized`` emission: mandatory fields must all
    be present, the pinned file list must equal ``PINNED_FILES`` exactly
    (complete, no duplicates), schema/status/provider-authorization/send
    cap are pinned, and ``outer_digest``, ``expected_machine_fingerprint``,
    and ``expected_contract_digest`` are **mandatory** - the pre-
    authorization audit interface never verifies an anchor without them.
    """

    failures: list[str] = []
    manifest_dict = manifest.manifest

    if strict_frozen:
        # Pre-authorization audit interface: these three expectations are
        # mandatory in strict mode, so an anchor can never be "verified"
        # without independently supplied comparison values.
        if outer_digest is None:
            failures.append(
                "strict_frozen verification requires outer_digest (the "
                "emitted artifact's digest field)"
            )
        if expected_machine_fingerprint is None:
            failures.append(
                "strict_frozen verification requires expected_machine_fingerprint"
            )
        if expected_contract_digest is None:
            failures.append(
                "strict_frozen verification requires expected_contract_digest"
            )
        for key in REQUIRED_MANIFEST_KEYS:
            if key not in manifest_dict:
                failures.append(f"missing mandatory freeze field: {key}")
        if manifest_dict.get("schema") != MANIFEST_SCHEMA:
            failures.append(
                f"schema is {manifest_dict.get('schema')!r}, expected {MANIFEST_SCHEMA!r}"
            )
        if manifest_dict.get("status") != FROZEN_UNAUTHORIZED_STATUS:
            failures.append(
                f"status is {manifest_dict.get('status')!r}, "
                f"expected {FROZEN_UNAUTHORIZED_STATUS!r}"
            )
        hashes = manifest_dict.get("scenario_file_hashes")
        if not isinstance(hashes, list) or not hashes:
            failures.append("scenario_file_hashes is empty or missing")
        else:
            pinned_paths = [
                entry["path"]
                for entry in hashes
                if isinstance(entry, dict) and "path" in entry
            ]
            if len(pinned_paths) != len(hashes):
                failures.append("scenario_file_hashes contains malformed entries")
            if len(set(pinned_paths)) != len(pinned_paths):
                failures.append("scenario_file_hashes contains duplicate paths")
            expected_paths = sorted(PINNED_FILES)
            if sorted(pinned_paths) != expected_paths:
                failures.append(
                    "scenario_file_hashes does not equal the pinned file set"
                )
        provider = manifest_dict.get("provider")
        if not isinstance(provider, dict):
            failures.append("provider section missing")
        else:
            if provider.get("provider_authorized") is not False:
                failures.append("provider_authorized must be false")
        budget = manifest_dict.get("call_budget")
        if not isinstance(budget, dict):
            failures.append("call_budget section missing")
        elif budget.get("max_provider_sends_this_gate") != 0:
            failures.append("provider send cap must be zero")
        if outer_digest is not None:
            if outer_digest != manifest.digest():
                failures.append(
                    "outer artifact digest does not match the manifest content digest"
                )

    if not _is_full_sha(manifest_dict.get("code_commit")):
        failures.append("code_commit is not a full 40-hex commit SHA")
    elif manifest_dict["code_commit"] != expected_commit:
        failures.append("code_commit does not match the expected commit")
    if not _is_full_sha(expected_commit):
        failures.append("expected_commit is not a full 40-hex commit SHA")

    if require_status is not None and manifest_dict.get("status") != require_status:
        failures.append(f"status is {manifest_dict.get('status')!r}, expected {require_status!r}")

    if (
        expected_machine_fingerprint is not None
        and manifest_dict.get("machine_fingerprint") != expected_machine_fingerprint
    ):
        failures.append("machine fingerprint does not match the expected value")
    if (
        expected_contract_digest is not None
        and manifest_dict.get("contract_digest") != expected_contract_digest
    ):
        failures.append("contract digest does not match the expected value")

    import subprocess

    for entry in manifest_dict.get("scenario_file_hashes", []):
        path = entry["path"]
        try:
            blob = subprocess.run(
                ["git", "show", f"{expected_commit}:{path}"],
                cwd=repo_root,
                capture_output=True,
                check=True,
            ).stdout
        except (subprocess.CalledProcessError, OSError) as error:
            failures.append(f"cannot read {path} from {expected_commit}: {error}")
            continue
        if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
            failures.append(f"pinned hash mismatch for {path} at {expected_commit}")

    return (not failures, failures)


GOVERNANCE_ACTIONS = frozenset(
    {
        "candidate-emitted",
        "frozen-unauthorized",
        "authorized",
        "executed",
        "closed",
    }
)


def governance_entry(
    manifest: FreezeManifest,
    *,
    action: str,
    recorded_by: str,
    recorded_at: str | None = None,
) -> dict[str, str]:
    """Build one append-only governance-log entry for a manifest.

    ``recorded_by`` is the attesting identity (required); ``recorded_at``
    defaults to the current UTC time and must be an ISO-8601 timestamp
    when supplied. The entry is written to the independent governance
    log - never only into the manifest file itself.
    """

    if action not in GOVERNANCE_ACTIONS:
        raise ValueError(f"unknown governance action {action!r}")
    if not isinstance(recorded_by, str) or not recorded_by.strip():
        raise ValueError("recorded_by is required")
    if recorded_at is None:
        from datetime import UTC, datetime

        recorded_at = datetime.now(UTC).isoformat()
    try:
        datetime.fromisoformat(recorded_at)
    except ValueError as error:
        raise ValueError("recorded_at must be an ISO-8601 timestamp") from error
    return {
        "action": action,
        "manifest_digest": manifest.digest(),
        "code_commit": manifest.manifest["code_commit"],
        "status": manifest.manifest["status"],
        "contract_digest": manifest.manifest["contract_digest"],
        "rules_version": manifest.manifest["rules_version"],
        "recorded_at": recorded_at,
        "recorded_by": recorded_by,
    }


def validate_governance_entry(entry: dict[str, str]) -> list[str]:
    """Return the list of schema violations of one governance entry."""

    failures: list[str] = []
    required = (
        "action",
        "manifest_digest",
        "code_commit",
        "status",
        "contract_digest",
        "rules_version",
        "recorded_at",
        "recorded_by",
    )
    for key in required:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"missing or empty field: {key}")
    if entry.get("action") not in GOVERNANCE_ACTIONS:
        failures.append("unknown governance action")
    manifest_digest_value = entry.get("manifest_digest", "")
    if len(manifest_digest_value) != 64 or any(
        char not in "0123456789abcdef" for char in manifest_digest_value
    ):
        failures.append("manifest_digest must be a full 64-hex digest")
    if not _is_full_sha(entry.get("code_commit", "")):
        failures.append("code_commit must be a full 40-hex commit SHA")
    try:
        datetime.fromisoformat(entry.get("recorded_at", ""))
    except (ValueError, TypeError):
        failures.append("recorded_at must be an ISO-8601 timestamp")
    return failures
