"""Linux host-shared C3R campaign slots: process restarts and concurrency.

Only synthetic ports and precommitted calibration prompts; no live Z.AI calls.
The file is NOT provider spending authority, external custody or multi-host.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from resonance_world.c3r_g1_calibration_audit import _request_digest
from resonance_world.c3r_g1_host_campaign_budget import (
    CampaignBudgetRejected,
    HostCampaignBudget,
)
from resonance_world.c3r_g1_multischema_calibration import (
    CalibrationRunner,
    make_calibration_plan,
)
from resonance_world.c3r_g1_zai_transport import (
    CODING_ENDPOINT,
    STANDARD_ENDPOINT,
    PhysicalSendLedger,
    TransportResponse,
    ZaiStandardModelPort,
)

CAMPAIGN = "g1-host-reservation-test-20261022"
MODEL = "glm-5.3"


def _digests() -> tuple[str, ...]:
    return tuple(
        _request_digest(p.prompt(), model=MODEL, max_tokens=512)
        for p in make_calibration_plan()
    )


def _budget(
    directory: Path, *, maximum: int = 8,
    endpoint: str = CODING_ENDPOINT, create: bool = True,
) -> HostCampaignBudget:
    path = directory / "campaign-budget.json"
    guard = HostCampaignBudget(
        path, campaign_id=CAMPAIGN, endpoint=endpoint,
        planned_digests=_digests(), maximum=maximum,
    )
    if create:
        guard.initialize()
    return guard


def test_campaign_initialization_is_exclusive_and_restarts_retain_count(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)
    assert guard.inspect()["reserved"] == 0
    with pytest.raises(FileExistsError):
        guard.initialize()
    first = guard.reserve(request_digest=_digests()[0], endpoint=CODING_ENDPOINT)
    assert first == 1
    fresh = _budget(tmp_path, create=False)
    assert fresh.inspect()["reserved"] == 1
    assert fresh.inspect()["remaining"] == 7
    second = fresh.reserve(request_digest=_digests()[1], endpoint=CODING_ENDPOINT)
    assert second == 2
    assert guard.inspect()["reserved"] == 2
    with pytest.raises(CampaignBudgetRejected, match="next provider request"):
        fresh.reserve(request_digest=_digests()[0], endpoint=CODING_ENDPOINT)


def test_wrong_route_model_budget_and_order_are_denied_before_spending_slot(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)
    with pytest.raises(CampaignBudgetRejected, match="endpoint"):
        guard.reserve(request_digest=_digests()[0], endpoint=STANDARD_ENDPOINT)
    with pytest.raises(CampaignBudgetRejected, match="next provider request"):
        guard.reserve(
            request_digest=_request_digest(
                make_calibration_plan()[0].prompt(), model=MODEL,
                max_tokens=256,
            ),
            endpoint=CODING_ENDPOINT,
        )
    with pytest.raises(CampaignBudgetRejected, match="next provider request"):
        guard.reserve(request_digest=_digests()[1], endpoint=CODING_ENDPOINT)
    assert guard.inspect()["reserved"] == 0
    other_route = _budget(tmp_path, create=False, endpoint=STANDARD_ENDPOINT)
    with pytest.raises(CampaignBudgetRejected, match="header"):
        other_route.inspect()


def test_budget_consumption_is_never_refunded_or_reset(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path, maximum=2)
    for index in range(2):
        assert guard.reserve(
            request_digest=_digests()[index], endpoint=CODING_ENDPOINT
        ) == index + 1
    assert guard.inspect()["remaining"] == 0
    with pytest.raises(CampaignBudgetRejected, match="exhausted"):
        guard.reserve(request_digest=_digests()[2], endpoint=CODING_ENDPOINT)
    assert _budget(tmp_path, maximum=2, create=False).inspect()["reserved"] == 2
    with pytest.raises(FileExistsError):
        _budget(tmp_path, maximum=2, create=True)
    with pytest.raises(CampaignBudgetRejected, match="header"):
        _budget(tmp_path, maximum=3, create=False).inspect()


@pytest.mark.parametrize("attack", [
    "truncate", "change_digest", "reset", "unsafe_mode", "hardlink",
    "substitute_inode", "wrong_campaign",
])
def test_corrupted_or_replaced_shared_budget_fails_closed(
    tmp_path: Path, attack: str,
) -> None:
    guard = _budget(tmp_path)
    guard.reserve(request_digest=_digests()[0], endpoint=CODING_ENDPOINT)
    file = guard.path
    if attack == "truncate":
        file.write_text("{", encoding="utf-8")
    elif attack in ("change_digest", "reset", "wrong_campaign"):
        data = json.loads(file.read_text(encoding="utf-8"))
        if attack == "change_digest":
            data["reservations"][0]["request_sha256"] = "0" * 64
        elif attack == "reset":
            data["reservations"] = []
            # Honest local API never supports a refund; malicious owner can
            # rewrite a fully coherent file, which cannot be detected alone.
            # Here we deliberately make the rollback *observable* by preserving
            # the old event count elsewhere in the declared lock.
            data["maximum"] = 7
        else:
            data["campaign_id"] = "substituted-campaign-2026"
        file.write_text(json.dumps(data), encoding="utf-8")
    elif attack == "unsafe_mode":
        file.chmod(0o644)
    elif attack == "hardlink":
        os.link(file, tmp_path / "alias.json")
    else:
        file.unlink()
        file.write_text("{}", encoding="utf-8")
    with pytest.raises(CampaignBudgetRejected):
        guard.inspect()


def test_symlink_and_shared_directory_are_rejected(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    with pytest.raises(CampaignBudgetRejected, match="private"):
        _budget(shared)
    shared.chmod(0o700)
    target = shared / "real.json"
    target.write_text("{}")
    (shared / "campaign-budget.json").symlink_to(target)
    with pytest.raises(CampaignBudgetRejected, match="nonsymlink"):
        _budget(shared, create=False)


def test_concurrent_threads_get_only_one_next_reservation(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)

    def attempt(_index: int) -> str:
        try:
            _budget(tmp_path, create=False).reserve(
                request_digest=_digests()[0], endpoint=CODING_ENDPOINT,
            )
            return "reserved"
        except CampaignBudgetRejected:
            return "rejected"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count("reserved") == 1
    assert results.count("rejected") == 11
    assert guard.inspect()["reserved"] == 1


def test_genuine_child_process_reserves_after_parent_and_cannot_repeat(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)
    guard.reserve(request_digest=_digests()[0], endpoint=CODING_ENDPOINT)
    child_code = (
        "import sys;"
        "from pathlib import Path;"
        "from resonance_world.c3r_g1_host_campaign_budget import HostCampaignBudget;"
        "from resonance_world.c3r_g1_calibration_audit import _request_digest;"
        "from resonance_world.c3r_g1_multischema_calibration import make_calibration_plan;"
        "from resonance_world.c3r_g1_zai_transport import CODING_ENDPOINT;"
        "prompts=make_calibration_plan();"
        "digests=tuple(_request_digest(p.prompt(),model='glm-5.3',max_tokens=512)"
        " for p in prompts);"
        "guard=HostCampaignBudget(Path(sys.argv[1]),campaign_id=sys.argv[2],"
        "endpoint=CODING_ENDPOINT,planned_digests=digests,maximum=8);"
        "print(guard.reserve(request_digest=digests[1],endpoint=CODING_ENDPOINT))"
    )
    args = [
        sys.executable, "-c", child_code, str(guard.path), CAMPAIGN,
    ]
    root = Path(__file__).resolve().parents[1]
    outcome = subprocess.run(
        args, cwd=root, text=True, capture_output=True, check=False, timeout=15
    )
    assert outcome.returncode == 0, outcome.stderr
    assert outcome.stdout.strip() == "2"
    assert guard.inspect()["reserved"] == 2
    with pytest.raises(CampaignBudgetRejected):
        guard.reserve(request_digest=_digests()[1], endpoint=CODING_ENDPOINT)


def test_port_integration_refuses_third_request_after_durable_cap(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path, maximum=2)
    sends: list[str] = []

    def fake_transport(_url, _headers, body, _timeout):
        sends.append(json.loads(body)["messages"][0]["content"])
        return TransportResponse(
            200, json.dumps({
                "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}]
            }).encode(),
        )

    local = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="synthetic-not-sent", model_id=MODEL, ledger=local,
        route="coding", campaign_budget=guard, transport=fake_transport,
        enabled=True, max_tokens=512,
    )
    report = CalibrationRunner(MODEL).run(port).to_dict()
    assert len(sends) == 2
    assert local.consumed == 2
    assert guard.inspect()["reserved"] == 2
    assert port.halted is True
    assert report["attempt_records"][2]["status"] == "adapter_exception"
    assert all(
        row["status"] == "not_sent_after_failure"
        for row in report["attempt_records"][3:]
    )
    assert report["scientific_acceptance"] is False
    assert report["technical_yield_gate"]["passed"] is False

    new_local = PhysicalSendLedger(8)
    fresh = ZaiStandardModelPort(
        api_key="synthetic-not-sent", model_id=MODEL, ledger=new_local,
        route="coding", campaign_budget=_budget(tmp_path, maximum=2, create=False),
        transport=fake_transport, enabled=True,
    )
    with pytest.raises(Exception, match="campaign reservation"):
        fresh.complete_prompt(make_calibration_plan()[0].prompt())
    assert new_local.consumed == 0
    assert len(sends) == 2


def test_host_budget_does_not_authorize_default_disabled_port(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)
    port = ZaiStandardModelPort(
        api_key="synthetic-not-sent", model_id=MODEL,
        ledger=PhysicalSendLedger(8), route="coding",
        campaign_budget=guard, enabled=False,
    )
    with pytest.raises(PermissionError):
        port.complete_prompt(make_calibration_plan()[0].prompt())
    assert guard.inspect()["reserved"] == 0



def test_initialize_and_inspect_cli_never_consume_calls_or_reinitialize(
    tmp_path: Path,
) -> None:
    path = tmp_path / "offline-campaign.json"
    common = [
        sys.executable, "-m", "resonance_world.c3r_g1_host_campaign_budget",
        "--path", str(path), "--campaign-id", CAMPAIGN,
        "--route", "coding", "--model", MODEL,
        "--max-tokens", "512", "--maximum", "8",
    ]
    root = Path(__file__).resolve().parents[1]
    prepared = subprocess.run(
        [*common[:3], "initialize", *common[3:]], cwd=root,
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    data = json.loads(prepared.stdout)
    assert data["reserved"] == 0
    assert data["remaining"] == 8
    assert data["scientific_acceptance"] is False

    checked = subprocess.run(
        [*common[:3], "inspect", *common[3:]], cwd=root,
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert checked.returncode == 0
    assert json.loads(checked.stdout)["reserved"] == 0
    repeated = subprocess.run(
        [*common[:3], "initialize", *common[3:]], cwd=root,
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert repeated.returncode == 2
    assert json.loads(repeated.stdout)["scientific_acceptance"] is False
    assert path.exists()


def test_simultaneous_child_processes_compete_for_one_next_slot(
    tmp_path: Path,
) -> None:
    guard = _budget(tmp_path)
    code = (
        "import sys;"
        "from pathlib import Path;"
        "from resonance_world.c3r_g1_host_campaign_budget import "
        "HostCampaignBudget, CampaignBudgetRejected;"
        "from resonance_world.c3r_g1_calibration_audit import _request_digest;"
        "from resonance_world.c3r_g1_multischema_calibration import make_calibration_plan;"
        "from resonance_world.c3r_g1_zai_transport import CODING_ENDPOINT;"
        "ds=tuple(_request_digest(x.prompt(),model='glm-5.3',max_tokens=512) "
        "for x in make_calibration_plan());"
        "budget=HostCampaignBudget(Path(sys.argv[1]),campaign_id=sys.argv[2],"
        "endpoint=CODING_ENDPOINT,planned_digests=ds,maximum=8);"
        "result='rejected';"
        "\ntry:\n"
        " budget.reserve(request_digest=ds[0],endpoint=CODING_ENDPOINT)\n"
        " result='reserved'\n"
        "except CampaignBudgetRejected:\n"
        " pass\n"
        "print(result)\n"
    )
    root = Path(__file__).resolve().parents[1]
    commands = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(guard.path), CAMPAIGN],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for _ in range(5)
    ]
    outcomes = [p.communicate(timeout=15) for p in commands]
    assert all(p.returncode == 0 for p in commands), outcomes
    values = [output.strip() for output, _ in outcomes]
    assert values.count("reserved") == 1
    assert values.count("rejected") == 4
    assert guard.inspect()["reserved"] == 1



def test_identical_blinded_arm_bodies_still_consume_distinct_ordered_slots(
    tmp_path: Path,
) -> None:
    planned = _digests()
    # All three technical-arm prompts are deliberately identical: prompt
    # parity is necessary and body hashes cannot prove arm attribution.
    assert planned[2] == planned[3] == planned[4]
    assert planned[5] == planned[6] == planned[7]
    guard = _budget(tmp_path)
    for index, digest in enumerate(planned, start=1):
        assert guard.reserve(
            request_digest=digest, endpoint=CODING_ENDPOINT
        ) == index
    assert guard.inspect()["reserved"] == 8
    assert guard.inspect()["remaining"] == 0
    with pytest.raises(CampaignBudgetRejected, match="exhausted"):
        guard.reserve(request_digest=planned[-1], endpoint=CODING_ENDPOINT)
