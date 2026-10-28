"""Unburned five-step grammar families for the feedback-acquisition campaign.

Pure, platform-independent logic: no transport, no prompt rendering, no
natural-language procedure text. Frozen composition for the 2026-10-28
feedback-acquired procedural memory campaign (see
research/c3r_g2/G1_FEEDBACK_ACQUIRED_PROCEDURAL_MEMORY_PROSPECTIVE_20261028.md).

Design invariant (campaign-wide since the representation study): for an
UNAMBIGUOUS input all 32 codes produce distinct outputs, so any wrong
procedure yields a wrong answer. Steps 1-4 of both families are
therefore bijections on the full 8-character state (no subset-keeping,
no sorting, no information loss); only step 5 places a count (prefix or
append). Both families are NEW to the model: no earlier campaign used
these alphabets, steps or programs.
"""

from __future__ import annotations

import hashlib
import itertools
import random
import string

CODES = tuple("".join(bits) for bits in itertools.product("AB", repeat=5))
FAMILIES = ("binary", "alpha")

_SEED_DOMAIN = "g1-feedback-acquisition-v1"
# v2 (operational rehabilitation, owner conditional GO 2026-10-28):
# new program codes and new inputs; same frozen families and evaluator.
_SEED_DOMAIN_V2 = "g1-feedback-acquisition-v2"


def _derive_code(seed_domain: str, family: str, position: int) -> str:
    return "".join(
        "A" if (hashlib.sha256(
            f"{seed_domain}:{family}:{position}".encode()
        ).digest()[byte] >> bit) & 1
        else "B"
        for byte, bit in ((0, 0), (0, 2), (0, 4), (0, 6), (1, 0))
    )


def _is_code(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 5
        and all(char in "AB" for char in value)
    )


def _execute(family: str, task: dict[str, object], code: str) -> str:
    if not _is_code(code):
        raise ValueError("invalid five-step procedure")
    if family == "binary":
        value = str(task["value"])
        # 1: flip every bit OR reverse the string
        if code[0] == "A":
            value = "".join("1" if bit == "0" else "0" for bit in value)
        else:
            value = value[::-1]
        # 2: swap the two halves OR leave unchanged
        if code[1] == "A":
            value = value[4:] + value[:4]
        # 3: move the first bit to the end OR the last bit to the front
        if code[2] == "A":
            value = value[1:] + value[:1]
        else:
            value = value[-1:] + value[:-1]
        # 4: flip the first bit only OR the last bit only
        if code[3] == "A":
            value = ("1" if value[0] == "0" else "0") + value[1:]
        else:
            value = value[:-1] + ("1" if value[-1] == "0" else "0")
        # 5: prefix OR append the count of 1-bits
        ones = sum(1 for bit in value if bit == "1")
        return (str(ones) + value) if code[4] == "A" else (value + str(ones))
    if family == "alpha":
        value = str(task["value"])
        # 1: swap the two halves OR reverse the whole string
        if code[0] == "A":
            value = value[4:] + value[:4]
        else:
            value = value[::-1]
        # 2: shift each letter +2 (z->b) OR -2 (a->y)
        shift = 2 if code[1] == "A" else -2
        value = "".join(
            chr((ord(ch) - 97 + shift) % 26 + 97) for ch in value
        )
        # 3: move the first character to the end OR the last to the front
        if code[2] == "A":
            value = value[1:] + value[:1]
        else:
            value = value[-1:] + value[:-1]
        # 4: swap the 1st and 3rd characters OR the 2nd and 4th
        if code[3] == "A":
            value = value[2] + value[1] + value[0] + value[3:]
        else:
            value = value[0] + value[3] + value[2] + value[1] + value[4:]
        # 5: prefix OR append the number of distinct letters
        distinct = len(set(value))
        return (str(distinct) + value) if code[4] == "A" else (
            value + str(distinct)
        )
    raise ValueError("unknown feedback-acquisition family")


def program_id(family: str, position: int) -> str:
    return f"prog-{family}-{position:02d}"


def all_programs() -> list[dict[str, str]]:
    """The 4 frozen v1 programs (2 per family), derived deterministically."""

    programs = []
    for family in FAMILIES:
        for position in range(2):
            programs.append({
                "program_id": program_id(family, position),
                "family": family,
                "program": _derive_code(_SEED_DOMAIN, family, position),
            })
    return programs


def all_programs_v2() -> list[dict[str, str]]:
    """The 4 frozen v2 programs (2 per family) — the rehabilitation units."""

    programs = []
    for family in FAMILIES:
        for position in range(2):
            code = _derive_code(_SEED_DOMAIN_V2, family, position)
            if code == _derive_code(_SEED_DOMAIN, family, position):
                raise RuntimeError(
                    f"v2 code collides with v1 for {family}/{position}"
                )
            programs.append({
                "program_id": program_id(family, position),
                "family": family,
                "program": code,
            })
    return programs


def qualification_program() -> dict[str, str]:
    """The dedicated v2 qualification unit (never evaluated in the campaign).

    The code is chosen deterministically (scanning positions downward
    from 99) so it differs from every v1 and v2 campaign code.
    """

    taken = {
        p["program"] for p in all_programs() + all_programs_v2()
    }
    for position in range(99, 0, -1):
        code = _derive_code(_SEED_DOMAIN_V2, "binary", position)
        if code not in taken:
            return {
                "program_id": "prog-binary-qual",
                "family": "binary",
                "program": code,
            }
    raise RuntimeError("no distinct qualification code available")


def sample_alphabet(family: str) -> str:
    return "01" if family == "binary" else string.ascii_lowercase


def sample_length(family: str) -> int:
    return 8


def is_unambiguous(family: str, value: str) -> bool:
    """All 32 codes give distinct outputs on this input."""

    outputs = {
        _execute(family, {"value": value}, code) for code in CODES
    }
    return len(outputs) == 32


def derive_input(family: str, program_id_value: str, role: str,
                 index: int, exclude: frozenset[str] = frozenset(),
                 version: int = 1) -> str:
    """Deterministic fresh unambiguous input for a given role.

    Roles: evidence / probe / eval / qual. Retry-by-index until
    unambiguous AND not colliding with any input in ``exclude`` (the
    caller accumulates the other roles' inputs of the same program, so
    evaluation inputs can never coincide with evidence or probe inputs
    — no contamination). ``version`` selects the seed domain (2 = the
    rehabilitation units; v2 inputs are disjoint from v1 by seed).
    """

    domain = _SEED_DOMAIN if version == 1 else f"{_SEED_DOMAIN_V2}"
    for attempt in range(2000):
        digest = hashlib.sha256(
            f"{domain}:input:{program_id_value}:{role}:{index}"
            f":{attempt}".encode()
        ).digest()
        rng = random.Random(digest)
        value = "".join(
            rng.choices(sample_alphabet(family), k=sample_length(family))
        )
        if value in exclude:
            continue
        if is_unambiguous(family, value):
            return value
    raise ValueError(
        f"unable to sample unambiguous input: {program_id_value}/{role}/{index}"
    )
