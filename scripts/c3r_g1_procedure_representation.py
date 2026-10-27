"""G1 procedure representation comparison: code capsule vs natural-language
instructions — does the REPRESENTATION of a correct procedure determine
execution fidelity?

Pure, platform-independent logic. Frozen design: 8 public five-bit programs
(4 per family, digits + rotate), 2 execution waves, 2 fresh holdout inputs
per program per wave, 2 representations (code capsule / numbered natural-
language instructions). Deterministic holdout derivation from a preregistered
seed so the frozen document + this module fully determine every task.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import string

from c3r_g1_novel_grammar_families import _execute as _novel_execute

CODES = tuple("".join(bits) for bits in itertools.product("AB", repeat=5))
FAMILIES = ("digits", "rotate")
REPRESENTATIONS = ("code", "natural")
WAVES = ("wave1", "wave2")
PROGRAMS_PER_FAMILY = 4
INPUTS_PER_PROGRAM_PER_WAVE = 2

_SEED_DOMAIN = "g1-procedure-representation-v1"


def program_id(family: str, position: int) -> str:
    return f"prog-{family}-{position:02d}"


def all_programs() -> list[dict[str, str]]:
    """The 8 frozen public programs (4 per family)."""

    programs = []
    for family in FAMILIES:
        for position in range(PROGRAMS_PER_FAMILY):
            code = "".join(
                "A" if (hashlib.sha256(
                    f"{_SEED_DOMAIN}:{family}:{position}".encode()
                ).digest()[byte] >> bit) & 1
                else "B"
                for byte, bit in ((0, 0), (0, 2), (0, 4), (0, 6), (1, 0))
            )
            programs.append({
                "program_id": program_id(family, position),
                "family": family,
                "program": code,
            })
    return programs


def _holdout_rng(family: str, program: str, wave: str, input_index: int) -> random.Random:
    digest = hashlib.sha256(
        f"{_SEED_DOMAIN}:holdout:{family}:{program}:{wave}:{input_index}".encode()
    ).digest()
    return random.Random(digest)


def holdout_task(family: str, program: str, wave: str, input_index: int) -> dict[str, object]:
    """Deterministic unambiguous holdout task for one execution request."""

    rng = _holdout_rng(family, program, wave, input_index)
    for _ in range(500):
        if family == "rotate":
            value = "".join(rng.choices(string.ascii_lowercase, k=6))
        else:
            value = "".join(rng.choices("0123456789", k=4))
        task = {"value": value}
        outputs = {_novel_execute(family, task, code) for code in CODES}
        if len(outputs) == 32:
            return task
    raise ValueError(f"unable to sample unambiguous holdout: {family}/{program}/{wave}")


def _grammar(family: str) -> str:
    return {
        "digits": (
            "The input is a 4-digit decimal string. The five steps are: "
            "1) swap the two middle digits, 2) keep only the first two digits "
            "OR keep only the last two digits, 3) replace each digit d with "
            "(d+1) mod 10 OR with (d+9) mod 10, 4) arrange digits descending "
            "OR ascending, 5) prefix the digit count OR append the digit count."
        ),
        "rotate": (
            "The input is a 6-letter lowercase string. The five steps are: "
            "1) rotate the string left by 2 OR right by 2, 2) insert '-' after "
            "every second character OR '_' after every third character, "
            "3) keep the first 6 characters OR the last 6 characters, "
            "4) swap every adjacent character pair OR leave unchanged, "
            "5) append '9' OR prepend '5'."
        ),
    }[family]


def _natural_instructions(family: str, code: str) -> str:
    """Explicit numbered natural-language rendering of EXACTLY this code."""

    lines: list[str] = []
    if family == "digits":
        lines.append("Step 1: swap the two middle digits." if code[0] == "A"
                     else "Step 1: leave the digit order unchanged.")
        lines.append("Step 2: keep only the first two digits." if code[1] == "A"
                     else "Step 2: keep only the last two digits.")
        lines.append("Step 3: replace each digit d with (d+1) mod 10." if code[2] == "A"
                     else "Step 3: replace each digit d with (d+9) mod 10.")
        lines.append("Step 4: arrange the digits in descending order." if code[3] == "A"
                     else "Step 4: arrange the digits in ascending order.")
        lines.append("Step 5: prefix the result with the digit count." if code[4] == "A"
                     else "Step 5: append the digit count to the result.")
    elif family == "rotate":
        lines.append("Step 1: rotate the string left by 2 characters." if code[0] == "A"
                     else "Step 1: rotate the string right by 2 characters.")
        lines.append("Step 2: insert '-' after every second character." if code[1] == "A"
                     else "Step 2: insert '_' after every third character.")
        lines.append("Step 3: keep the first 6 characters." if code[2] == "A"
                     else "Step 3: keep the last 6 characters.")
        lines.append("Step 4: swap every adjacent character pair." if code[3] == "A"
                     else "Step 4: leave the character order unchanged.")
        lines.append("Step 5: append '9' to the end." if code[4] == "A"
                     else "Step 5: prepend '5' to the beginning.")
    return "\n".join(lines)


def representation_prompt(representation: str, family: str, code: str,
                          task: dict[str, object]) -> str:
    """The ONLY variable: how the same correct procedure is represented."""

    if family == "digits":
        domain = "The input is a 4-digit decimal string."
    else:
        domain = "The input is a 6-letter lowercase string."
    head = (
        "This is a new isolated agent session. Execute the following "
        "five-step procedure IN ORDER on the new task below. Output ONLY the "
        "final value, without reasoning, markdown or labels.\n"
    )
    if representation == "code":
        body = (
            f"{domain}\n{_grammar(family)}\n"
            f"Procedure capsule: {code}\n"
        )
    else:
        body = (
            f"{domain}\n{_natural_instructions(family, code)}\n"
        )
    return (
        f"{head}{body}"
        f"New task: {json.dumps(task, sort_keys=True)}\n"
        "Answer with only the final result."
    )
