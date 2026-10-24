"""Three-arm G1 runner whose grader lives outside the model process.

All qualification grades remain unavailable until every prescribed task is
submitted. Connection/authorship of the evaluator is NOT independently
attested; use a separately managed OS account and key for real experiments.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol, TextIO

from .c3r_g1_model_boundary import ModelChoiceCompletion
from .c3r_g1_multischema import (
    ARMS,
    Attempt,
    Feedback,
    PortFactory,
    PublicCohort,
    SchemaRequest,
    V2Report,
    _digest,
)

MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 256 * 1024


class EvaluatorSession(Protocol):
    def ready(self) -> dict[str, Any]: ...
    def submit(self, request: dict[str, object]) -> dict[str, Any]: ...
    def finalize(self) -> dict[str, Any]: ...


class JsonLineEvaluatorSession:
    """Transport only; does not spawn the worker or access its secret key."""

    def __init__(self, reader: TextIO, writer: TextIO) -> None:
        self._reader = reader
        self._writer = writer
        self._used_ready = False

    def _receive(self) -> dict[str, Any]:
        line = self._reader.readline(MAX_RESPONSE_BYTES + 1)
        if not line or len(line.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise ValueError("evaluator reply missing or exceeds size limit")
        try:
            result = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("evaluator reply was not valid JSON") from exc
        if not isinstance(result, dict):
            raise ValueError("evaluator response must be an object")
        return result

    def ready(self) -> dict[str, Any]:
        if self._used_ready:
            raise ValueError("evaluator readiness must only be consumed once")
        self._used_ready = True
        return self._receive()

    def _send(self, request: dict[str, object]) -> dict[str, Any]:
        data = json.dumps(request, sort_keys=True, separators=(",", ":"))
        if len(data.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ValueError("evaluator request exceeds size limit")
        self._writer.write(data + "\n")
        self._writer.flush()
        return self._receive()

    def submit(self, request: dict[str, object]) -> dict[str, Any]:
        return self._send(request)

    def finalize(self) -> dict[str, Any]:
        return self._send({"op": "finalize"})


@dataclass(frozen=True, slots=True)
class SealedRunResult:
    report: V2Report
    evaluator_commitment: str
    evaluator_record_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-sealed-pilot-result-v0.1",
            "status": "externally_graded_local_apparatus_unattested",
            "target_commitment": self.evaluator_commitment,
            "evaluator_records_sha256": self.evaluator_record_digest,
            "graded_only_after_full_qualification": True,
            "report": self.report.to_dict(),
            "evaluator_identity_attested": False,
            "provider_activity_verified": False,
            "scientific_acceptance": False,
        }


class SealedPilotRunner:
    def __init__(self, cohort: PublicCohort, session: EvaluatorSession) -> None:
        self.cohort = cohort
        self._session = session

    def _outcome(self, port: object, request: SchemaRequest) -> tuple[str, str | None]:
        try:
            completion = port.complete(request)  # type: ignore[attr-defined]
        except Exception:
            return "adapter_exception", None
        if not isinstance(completion, ModelChoiceCompletion):
            return "invalid_completion", None
        if completion.model_id != self.cohort.design.model_id:
            return "wrong_model", None
        if completion.output not in ("A", "B"):
            return "invalid_format", None
        return "accepted", completion.output

    def run(self, *, port_factory: PortFactory) -> SealedRunResult:
        ready = self._session.ready()
        expected_dev = (
            self.cohort.design.units * 2 * self.cohort.design.development_per_family
        )
        expected_qualification = (
            self.cohort.design.units * 2 * self.cohort.design.qualification_per_family * 3
        )
        commitment = ready.get("target_commitment")
        if (ready.get("schema") != "c3r-g1-evaluator-v0.1"
                or ready.get("phase") != "accept_development"
                or ready.get("public_cohort_digest") != self.cohort.digest
                or ready.get("development_expected") != expected_dev
                or ready.get("qualification_expected") != expected_qualification
                or ready.get("independently_attested") is not False
                or not isinstance(commitment, str)
                or len(commitment) != 64
                or any(c not in "0123456789abcdef" for c in commitment)):
            raise ValueError("evaluator readiness does not match frozen public cohort")

        used_ports: list[object] = []
        source: dict[tuple[str, str], tuple[tuple[Feedback, ...], tuple[Feedback, ...]]] = {}
        exposure: list[tuple[str, str, int, int]] = []
        submitted: dict[tuple[str, str, str, str], dict[str, object]] = {}
        grades: dict[tuple[str, str, str, str], bool] = {}

        def new_port(unit_id: str, arm: str, stage: str) -> object:
            port = port_factory(unit_id, arm, stage)  # type: ignore[arg-type]
            if (port is None or not callable(getattr(port, "complete", None))
                    or any(port is previous for previous in used_ports)):
                raise ValueError("port object reused or not callable")
            used_ports.append(port)
            return port

        def transmit(
            unit_id: str, arm: str, stage: str, task_id: str,
            status: str, choice: str | None,
        ) -> tuple[tuple[str, str, str, str], dict[str, Any]]:
            request: dict[str, object] = {
                "op": "submit", "unit_id": unit_id, "arm": arm,
                "stage": stage, "task_id": task_id,
                "status": status, "choice": choice,
            }
            key = (unit_id, arm, stage, task_id)
            if key in submitted:
                raise ValueError("duplicate local submission")
            answer = self._session.submit(request)
            submitted[key] = request
            return key, answer

        # Training phase globally precedes every holdout submission, so the
        # evaluator cannot accidentally disclose a qualification grade.
        for unit in self.cohort.units:
            port = new_port(unit.unit_id, "learned", "development")
            for family in unit.families:
                feedback: list[Feedback] = []
                for task in family.development:
                    status, choice = self._outcome(
                        port, SchemaRequest(
                            unit.unit_id, "learned", "development", task, tuple(feedback)
                        ),
                    )
                    key, answer = transmit(
                        unit.unit_id, "learned", "development",
                        task.task_id, status, choice,
                    )
                    if (set(answer) != {
                        "schema", "phase", "task_id", "grade", "accepted",
                        "development_received",
                    } or answer["schema"] != "c3r-g1-evaluator-v0.1"
                            or answer["phase"] != "development_feedback"
                            or answer["task_id"] != task.task_id
                            or answer["development_received"] != len(submitted)
                            or answer["accepted"] is not (status == "accepted")):
                        raise ValueError("invalid development receipt")
                    grade = answer["grade"]
                    if status == "accepted":
                        if type(grade) is not bool:
                            raise ValueError("development grade is not Boolean")
                        assert choice in ("A", "B")
                        feedback.append(Feedback(
                            task.task_id, task.context, choice, grade
                        ))
                        grades[key] = grade
                    elif grade is not None:
                        raise ValueError("failed development action had a grade")
                    else:
                        grades[key] = False
                sham = [
                    Feedback(
                        record.task_id, record.context,
                        "A" if int((h := _digest([
                            "placebo-independent-of-source-outcome-v2",
                            self.cohort.design.public_seed,
                            unit.unit_id, record.task_id,
                        ]))[:8], 16) % 2 == 0 else "B",
                        bool(int(h[8:16], 16) % 2),
                    )
                    for record in feedback
                ]
                source[unit.unit_id, family.context] = (tuple(feedback), tuple(sham))
                exposure.append((unit.unit_id, family.family,
                                 len(feedback), len(sham)))

        for unit in self.cohort.units:
            qualifying = {
                arm: new_port(unit.unit_id, arm, "qualification") for arm in ARMS
            }
            for family in unit.families:
                learned, sham = source[unit.unit_id, family.context]
                for index, task in enumerate(family.qualification):
                    rotation = (index + int(unit.unit_id[-3:])) % len(ARMS)
                    for arm in (*ARMS[rotation:], *ARMS[:rotation]):
                        feedback = (
                            learned if arm == "learned"
                            else sham if arm == "placebo" else ()
                        )
                        status, choice = self._outcome(
                            qualifying[arm], SchemaRequest(
                                unit.unit_id, arm, "qualification", task, feedback
                            ),
                        )
                        _key, answer = transmit(
                            unit.unit_id, arm, "qualification",
                            task.task_id, status, choice,
                        )
                        # Fail closed if even a single partial holdout grade
                        # or derived success signal crosses this interface.
                        if (set(answer) != {
                            "schema", "phase", "task_id", "qualification_received"
                        } or answer["schema"] != "c3r-g1-evaluator-v0.1"
                                or answer["phase"] != "qualification_sealed"
                                or answer["task_id"] != task.task_id
                                or answer["qualification_received"] != (
                                    len(submitted) - expected_dev
                                )):
                            raise ValueError("holdout grade leaked or receipt invalid")

        outcome = self._session.finalize()
        records = outcome.get("records")
        digest = outcome.get("records_sha256")
        if (outcome.get("schema") != "c3r-g1-evaluator-final-v0.1"
                or outcome.get("status")
                != "local_process_fixture_no_scientific_acceptance"
                or outcome.get("public_cohort_digest") != self.cohort.digest
                or outcome.get("target_commitment") != commitment
                or outcome.get("development_attempts") != expected_dev
                or outcome.get("qualification_attempts") != expected_qualification
                or outcome.get("scientific_acceptance") is not False
                or outcome.get("independently_attested") is not False
                or outcome.get("provider_sends_verified") is not False
                or not isinstance(records, list)
                or len(records) != len(submitted)
                or not isinstance(digest, str)
                or hashlib.sha256(json.dumps(
                    records, sort_keys=True, separators=(",", ":")
                ).encode()).hexdigest() != digest):
            raise ValueError("incomplete or inconsistent sealed evaluator report")

        attempts: list[Attempt] = []
        seen: set[tuple[str, str, str, str]] = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("invalid evaluator grade record")
            key = tuple(record.get(field) for field in (
                "unit_id", "arm", "stage", "task_id"
            ))
            if key not in submitted or key in seen:
                raise ValueError("missing or duplicate evaluator record")
            seen.add(key)
            original = submitted[key]
            if any(record.get(field) != original[field] for field in (
                "unit_id", "arm", "stage", "task_id", "status", "choice"
            )) or type(record.get("success")) is not bool:
                raise ValueError("grade record disagrees with submitted action")
            if key in grades and record["success"] is not grades[key]:
                raise ValueError("development grade retroactively changed")
            task = next(
                task for unit in self.cohort.units if unit.unit_id == key[0]
                for family in unit.families
                for task in (*family.development, *family.qualification)
                if task.task_id == key[3]
            )
            if (record.get("family") != task.family
                    or record.get("context") != task.context
                    or (original["status"] != "accepted" and record["success"])):
                raise ValueError("final grade is inconsistent with public task")
            attempts.append(Attempt(
                key[0], key[1], key[2], key[3], task.family, task.context,
                original["status"], original["choice"], record["success"],
            ))
        if len(seen) != len(submitted):
            raise ValueError("missing final evaluator grades")

        return SealedRunResult(
            V2Report(
                self.cohort.digest, self.cohort.design, tuple(attempts),
                tuple(exposure), fixture_ports_only=False,
            ),
            commitment, digest,
        )
