"""Offline contract tests for session-separated three-step real agent protocol."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import threading
from pathlib import Path

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _load():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    name = "g1_three_step_test_module"
    spec = importlib.util.spec_from_file_location(
        name, scripts / "run_c3r_g1_three_step_procedure_live.py",
    )
    assert spec and spec.loader
    instance = importlib.util.module_from_spec(spec)
    sys.modules[name] = instance
    spec.loader.exec_module(instance)
    return instance


def _folder(tmp_path: Path) -> Path:
    private = tmp_path / "owner"
    private.mkdir(mode=0o700)
    return private


def _model(module, *, fail_first_source=False):
    class Port:
        lock = threading.Lock()
        source_calls = 0
        qualification_calls = 0

        def complete_prompt(self, prompt):
            if "Internal agent development action." in prompt:
                with self.lock:
                    self.__class__.source_calls += 1
                    n = self.__class__.source_calls
                if fail_first_source and n == 1:
                    raise TimeoutError("private transport exception must not leak")
                reply = "A"
            else:
                assert "correct=" not in prompt
                assert "source transcript" in prompt
                found = re.search(r"Procedure capsule: ([AB]{3})", prompt)
                assert found
                payload = json.loads(prompt.split("Public input: ", 1)[1].splitlines()[0])
                family = "arithmetic" if "k1" in payload else "text"
                reply = module._execute(family, payload, found.group(1))
                with self.lock:
                    self.__class__.qualification_calls += 1
            return ModelChoiceCompletion(
                output=reply, model_id="glm-5.3",
                physical_sends_reported=1, prompt_tokens_reported=70,
                completion_tokens_reported=12,
                reasoning_tokens_reported=9, finish_reason="stop",
            )
    return Port


def test_novel_procedure_memory_survives_new_interpreter_and_matched_capsules(
    tmp_path: Path,
) -> None:
    module = _load()
    root = _folder(tmp_path)
    name = "g1-procedural-novel-test-01"
    port = _model(module)
    source = module.run_source(root, name, port, workers=4)
    assert source["source_valid"] == 24
    assert source["reserved_source"] == 24
    assert source["source_contexts_eligible"] == 8
    directory = module._run_dir(root, name)
    manifest = module._read(directory, "manifest.json")
    capsule = module._read(directory, "capsules.json")
    assert len({row["context_id"] for row in manifest["units"]}) == 8
    assert len({row["holdout_task_id"] for row in manifest["units"]}) == 8
    assert len({row["private_program"] for row in manifest["units"]}) >= 2
    assert all(
        module._execute(unit["family"], unit["holdout_payload"], c)
        != module._execute(unit["family"], unit["holdout_payload"], other)
        for unit in manifest["units"] for c in module.CODES
        for other in module.CODES if c != other
    )
    assert all(len(row["policy"]) == 3 for row in capsule["procedure_capsules"])
    assert all((directory / f).stat().st_mode & 0o077 == 0 for f in (
        "manifest.json", "capsules.json", "source.json",
    ))
    for unit in manifest["units"]:
        stored = next(c["policy"] for c in capsule["procedure_capsules"]
                      if c["unit_id"] == unit["unit_id"])
        assert stored == unit["private_program"]

    # New module and process-level call receive zero in-memory source state.
    restarted = _load()
    qualification = restarted.run_holdout(root, name, port, workers=3)
    assert qualification["physical_holdout_reservations"] == 24
    assert qualification["qualification_status_counts"] == {"accepted": 24}
    assert qualification["qualification_by_arm"]["learned"]["correct"] == 8
    assert qualification["qualification_by_arm"]["learned"]["accepted"] == 8
    assert qualification["qualification_by_arm"]["fresh"]["prescribed"] == 8
    assert qualification["qualification_by_arm"]["neutral"]["prescribed"] == 8
    assert qualification["same_size_capsules_all_arms"] is True
    assert qualification["raw_source_grades_supplied_to_holdout_model"] is False
    assert qualification["model_parameters_updated"] is False
    assert qualification["scientific_acceptance"] is False
    rows = qualification["qualification_rows_redacted"]
    assert len(rows) == 24
    assert sorted(row["slot_index"] for row in rows) == list(range(24, 48))
    assert all("private_program" not in row and "policy" not in row
               for row in rows)
    serialized = json.dumps(qualification)
    assert "holdout_payload" not in serialized
    assert "source_rows" not in serialized
    assert "private transport exception" not in serialized


def test_single_provider_failure_skips_only_failed_context_triplet(
    tmp_path: Path,
) -> None:
    module = _load()
    root = _folder(tmp_path)
    port = _model(module, fail_first_source=True)
    name = "g1-procedural-one-fail-test-02"
    source = module.run_source(root, name, port)
    assert source["reserved_source"] == 24
    assert source["source_valid"] == 23
    assert source["source_contexts_eligible"] == 7
    qualification = module.run_holdout(root, name, port)
    assert qualification["physical_holdout_reservations"] == 21
    assert qualification["qualification_status_counts"] == {
        "accepted": 21, "not_sent": 3,
    }
    assert qualification["qualification_by_arm"]["learned"]["prescribed"] == 8
    assert qualification["qualification_by_arm"]["neutral"]["prescribed"] == 8
    assert qualification["scientific_acceptance"] is False


def test_mutated_capsule_rejected_without_any_holdout_send(
    tmp_path: Path,
) -> None:
    module = _load()
    root = _folder(tmp_path)
    name = "g1-procedural-tamper-test-03"
    module.run_source(root, name, _model(module))
    directory = module._run_dir(root, name)
    capsule = module._read(directory, "capsules.json")
    original = capsule["procedure_capsules"][0]["policy"]
    capsule["procedure_capsules"][0]["policy"] = (
        "BBB" if original != "BBB" else "AAA"
    )
    (directory / "capsules.json").write_text(json.dumps(capsule))
    with pytest.raises(ValueError, match="integrity"):
        module.run_holdout(root, name, _model(module))
    assert not (directory / "holdout-start.json").exists()
    assert not list(directory.glob("send-2[4-9].json"))


def test_phase_ids_cannot_replay_real_sends(tmp_path: Path) -> None:
    module = _load()
    root = _folder(tmp_path)
    name = "g1-procedural-no-retry-test-04"
    module.run_source(root, name, _model(module))
    with pytest.raises(FileExistsError):
        module.run_source(root, name, _model(module))
    module.run_holdout(root, name, _model(module))
    with pytest.raises(FileExistsError):
        module.run_holdout(root, name, _model(module))


def test_counterbalanced_three_steps_and_capacity_matched_controls() -> None:
    module = _load()
    plan = module._manifest("g1-procedural-balance-test-05")
    assert len(plan["units"]) == 8
    for family in module.FAMILIES:
        group = [u for u in plan["units"] if u["family"] == family]
        assert len(group) == 4
        for bit in range(3):
            assert [u["private_program"][bit] for u in group].count("A") == 2
        for unit in group:
            assert len(unit["private_program"]) == 3
            assert len(unit["fresh_random_program"]) == 3
            assert set(unit["fresh_random_program"]) <= {"A", "B"}


def test_three_step_cli_default_is_offline(capsys) -> None:
    module = _load()
    assert module.main(["--phase", "source", "--run-id", "g1-offline-test-06"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "offline_no_sends"
    assert module.main(["--phase", "holdout", "--run-id", "g1-offline-test-06"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "offline_no_sends"
