"""Execute the locked Phase-4C opaque authority-provenance campaign."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from resonance.experiments.piano_phase4_authority import Phase4AuthorityArm

from experiments.piano_society import phase4b_authority_campaign as phase4b_campaign
from experiments.piano_society.phase3 import config_digest
from experiments.piano_society.phase4c_authority import analyze, materialize_roles, validate_config

_PAYLOAD_SCHEMA = "resonance-world-piano-phase4-authority-arm-v0.1"


def _run_joint_case(case_id: str, *, config: dict, api_key: str):
    roles = [role for role in materialize_roles(config) if role["joint_case_id"] == case_id]
    case_seed = int(roles[0]["case_seed"])
    arm_order = (
        (Phase4AuthorityArm.UNSIGNED, Phase4AuthorityArm.ATTESTED)
        if case_seed % 2 == 1
        else (Phase4AuthorityArm.ATTESTED, Phase4AuthorityArm.UNSIGNED)
    )
    result = {}
    for arm in arm_order:
        result[arm.value] = phase4b_campaign._run_arm_case(
            arm=arm,
            case_roles=roles,
            config=config,
            api_key=api_key,
        )
    return result


def run(config: dict, *, api_key: str):
    normalized = validate_config(config)
    case_ids = list(normalized["joint_case_ids"])
    by_arm: dict[str, list[dict[str, object]]] = {"unsigned": [], "attested": []}
    max_workers = int(config["model_backend"]["max_workers"])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_run_joint_case, case_id, config=config, api_key=api_key)
            for case_id in case_ids
        ]
        for future in as_completed(futures):
            case_result = future.result()
            for arm, records in case_result.items():
                by_arm[arm].extend(records)

    order = {role["scenario_id"]: index for index, role in enumerate(normalized["roles"])}
    digest = config_digest(config)
    payloads = {}
    for arm, records in by_arm.items():
        records.sort(key=lambda record: order[str(record["scenario_id"])])
        payloads[arm] = {
            "schema": _PAYLOAD_SCHEMA,
            "arm": arm,
            "field_revision": normalized["field_revision"],
            "config_digest": digest,
            "records": records,
        }
    result = analyze(config, payloads["unsigned"], payloads["attested"])
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase 4C")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    payloads, result = run(config, api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for arm, payload in payloads.items():
        (output_dir / f"{arm}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
