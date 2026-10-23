"""No-provider tests of paired two-wave terminal-grade study aggregation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _analyzer():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    path = scripts / "analyze_c3r_g1_terminal_retention.py"
    spec = importlib.util.spec_from_file_location("c3r_g1_terminal_audit_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _evidence(tmp_path: Path):
    paths = []
    for i in range(3):
        run = f"g1-terminal-synthetic-{i}"
        source = {
            "schema": "c3r-g1-terminal-grade-two-retentions-v0.1",
            "phase": "source", "run_id": run,
            "source_slots_prescribed": 56,
            "source_sends_reserved": 30, "source_not_sent": 26,
            "source_accepted": 30,
            "eligible_contexts": 8, "scientific_acceptance": False,
        }
        files = []
        file = tmp_path / f"{i}-source.json"
        file.write_text(json.dumps(source))
        files.append(file)
        for index, wave in enumerate(("retention1", "retention2")):
            rows = []
            for unit in range(8):
                for pos, arm in enumerate(("learned", "fresh", "neutral")):
                    rows.append({
                        "index": 56 + index*24 + unit*3 + pos,
                        "unit_id": f"ctx-{unit}", "family": (
                            "arithmetic" if unit < 4 else "text"
                        ),
                        "arm": arm, "status": "accepted",
                        "correct": arm == "learned" and unit != (7 if index else 6),
                    })
            summary = {
                arm: {
                    "prescribed": 8,
                    "accepted": 8,
                    "correct": sum(r["correct"] for r in rows if r["arm"] == arm),
                } for arm in ("learned", "fresh", "neutral")
            }
            result = {
                "schema": source["schema"], "phase": wave, "run_id": run,
                "scientific_acceptance": False,
                "prescribed_holdout_slots": 24,
                "separate_interpreter_required": True,
                "equal_capacity_and_independent_uniform_control_capsules": True,
                "learned_capsule_unmodified_between_waves": True,
                "source_transcript_reinserted_in_prompt": False,
                "eligible_contexts": 8,
                "qualification_rows_redacted": rows,
                "qualification_by_arm": summary,
                "physical_holdout_reservations": 24,
            }
            file = tmp_path / f"{i}-{wave}.json"
            file.write_text(json.dumps(result))
            files.append(file)
        paths.append(tuple(files))
    return tuple(paths)


def test_full_three_cohort_two_wave_summary_is_paired(tmp_path: Path):
    result = _analyzer().analyze(_evidence(tmp_path))
    assert result["planned_logical_attempts"] == 312
    assert result["source_physical_reservations"] == 90
    assert result["holdout_physical_reservations"] == 144
    assert result["totals"]["retention1"]["learned"]["correct"] == 21
    assert result["totals"]["retention2"]["learned"]["correct"] == 21
    assert result["totals"]["retention1"]["fresh"]["prescribed"] == 24
    assert result["same_contexts_retested_across_waves"] is True
    for cohort in result["cohorts"]:
        paired = cohort["same_context_learned_retention_changes"]
        assert paired == {
            "correct_both": 6, "lost_by_wave2": 1,
            "recovered_by_wave2": 1, "incorrect_both": 0,
        }
        assert cohort["waves"]["retention1"]["paired"]["fresh"] == {
            "learned_only": 7, "control_only": 0, "ties": 1,
        }
    assert result["scientific_acceptance"] is False
    public = json.dumps(result)
    assert "private_target" not in public
    assert "candidate_order" not in public


def test_refuses_arm_grade_tamper_and_preserves_missingness(tmp_path: Path):
    module = _analyzer()
    paths = _evidence(tmp_path)
    file = paths[0][1]
    data = json.loads(file.read_text())
    data["qualification_rows_redacted"][0]["correct"] = False
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="per-arm grade mismatch"):
        module.analyze(paths)


def test_rejects_duplicate_cohort_and_bad_retention_order(tmp_path: Path):
    module = _analyzer()
    paths = _evidence(tmp_path)
    with pytest.raises(ValueError, match="duplicated"):
        module.analyze((paths[0], paths[0], paths[2]))
    file = paths[1][2]
    data = json.loads(file.read_text())
    data["qualification_rows_redacted"][1]["index"] = 80
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="index duplicated"):
        module.analyze(paths)
