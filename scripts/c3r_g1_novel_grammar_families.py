"""Novel procedural grammar families for the G1 generalization pilot.

Pure, platform-independent logic: no transport, no private-workspace
rules, no Linux-only primitives. Frozen composition for the 2026-10-26
novel grammar generalization pilot (see
research/c3r_g2/G1_NOVEL_GRAMMAR_GENERALIZATION_PROSPECTIVE_20261026.md;
amendment A1 pre-dispatch: rotate step3 window 7 -> 6 to remove a
structural first7/last7 collision on the 7-character underscore branch).
"""

from __future__ import annotations

import itertools
import random
import string

CODES = tuple("".join(bits) for bits in itertools.product("AB", repeat=5))
FAMILIES = ("digits", "rotate")


def _execute(family: str, task: dict[str, object], code: str) -> str:
    if not _is_code(code):
        raise ValueError("invalid five-step procedure")
    if family == "digits":
        digits = list(str(task["value"]))
        if code[0] == "A":
            digits[1], digits[2] = digits[2], digits[1]
        digits = digits[:2] if code[1] == "A" else digits[-2:]
        digits = [
            str((int(d) + 1) % 10) if code[2] == "A" else str((int(d) + 9) % 10)
            for d in digits
        ]
        digits = sorted(digits, reverse=(code[3] == "A"))
        body = "".join(digits)
        return (str(len(body)) + body) if code[4] == "A" else (body + str(len(body)))
    if family == "rotate":
        value = str(task["value"])
        n = len(value)
        shift = 2 if code[0] == "A" else n - 2
        value = value[shift % n:] + value[: shift % n]
        if code[1] == "A":
            value = "-".join(value[i:i + 2] for i in range(0, len(value), 2))
        else:
            value = "_".join(value[i:i + 3] for i in range(0, len(value), 3))
        value = value[:6] if code[2] == "A" else value[-6:]
        chars = list(value)
        if code[3] == "A":
            for i in range(0, len(chars) - 1, 2):
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
            value = "".join(chars)
        return ("9" + value) if code[4] == "B" else (value + "9")
    raise ValueError("unknown novel procedure family")


def _is_code(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 5
        and all(char in "AB" for char in value)
    )


def _task(rng: random.Random | random.SystemRandom, family: str) -> dict[str, object]:
    """Sample one task whose 32 candidate programs all give distinct outputs."""

    if family == "rotate":
        for _ in range(500):
            value = "".join(rng.choices(string.ascii_lowercase, k=6))
            if _unambiguous(family, {"value": value}):
                return {"value": value}
        raise ValueError("unable to sample unambiguous rotate task")
    if family == "digits":
        for _ in range(500):
            value = "".join(rng.choices("0123456789", k=4))
            if _unambiguous(family, {"value": value}):
                return {"value": value}
        raise ValueError("unable to sample unambiguous digits task")
    raise ValueError(f"unknown novel procedure family {family!r}")


def _unambiguous(family: str, task: dict[str, object]) -> bool:
    outputs = {_execute(family, task, code) for code in CODES}
    return len(outputs) == 32


def _grammar(family: str) -> str:
    if family == "digits":
        return (
            "The input is a 4-digit decimal string. "
            "Step1 A: swap the two middle digits B: leave unchanged; "
            "Step2 A: keep only the first two digits B: keep only the last two; "
            "Step3 A: replace each digit d with (d+1) mod 10 B: with (d+9) mod 10; "
            "Step4 A: arrange digits descending B: ascending; "
            "Step5 A: prefix the digit count B: append the digit count."
        )
    if family == "rotate":
        return (
            "The input is a 6-letter lowercase string. "
            "Step1 A: rotate the string left by 2 B: rotate the string right by 2; "
            "Step2 A: insert '-' after every second character B: insert '_' after "
            "every third character; Step3 A: keep the first 6 characters B: keep "
            "the last 6 characters; Step4 A: swap every adjacent character pair "
            "B: leave unchanged; Step5 A: append '9' B: prepend '5'."
        )
    raise ValueError(f"unknown novel procedure family {family!r}")
