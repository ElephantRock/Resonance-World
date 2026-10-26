"""Novel procedural grammar families for the interactive-fidelity pilot.

Pure, platform-independent logic (no transport, no POSIX primitives).
Frozen verbatim in
research/c3r_g2/G1_INTERACTIVE_ACQUISITION_EXECUTION_FIDELITY_PROSPECTIVE_
20261026.md. Operation vocabularies and compositions are unused by any
prior C3R-G1 family (arithmetic/text/digits/rotate).
"""

from __future__ import annotations

import itertools
import random

CODES = tuple("".join(bits) for bits in itertools.product("AB", repeat=5))
FAMILIES = ("bracket", "modpair")


def _is_code(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 5
        and all(char in "AB" for char in value)
    )


def _execute(family: str, task: dict[str, object], code: str) -> str:
    if not _is_code(code):
        raise ValueError("invalid five-step procedure")
    if family == "bracket":
        value = str(task["value"])
        if code[0] == "A":
            value = value.replace("<", ">").replace(">", "<")
        if code[1] == "A":
            value = value.replace("<", "")
        else:
            value = value.replace(">", "")
        value = ("<<" + value + ">>") if code[2] == "A" else ("[[" + value + "]]")
        value = ("<>:" + value) if code[3] == "A" else ("><:" + value)
        return (value + value) if code[4] == "A" else (value + str(len(value)))
    if family == "modpair":
        a, b = str(task["a"]), str(task["b"])
        pair = sorted((a, b)) if code[0] == "A" else sorted((a, b), reverse=True)
        value = ("-".join(pair)) if code[1] == "A" else (":".join(pair))
        first, second = pair[0], pair[1]
        value = (first + "-" + value) if code[2] == "A" else (second + ":" + value)
        if code[3] == "A":
            value = value.replace("9", "Z")
        else:
            value = value.replace("0", "O")
        return (
            "(" + value + ")"
            if code[4] == "A"
            else ("<" + value + ">")
        )
    raise ValueError(f"unknown novel procedure family {family!r}")


def _grammar(family: str) -> str:
    if family == "bracket":
        return (
            "The input is a 5-character string over the symbols < and >. "
            "Step1 A: flip every character (< becomes > and > becomes <) "
            "B: leave unchanged; Step2 A: delete every remaining '<' B: delete "
            "every remaining '>'; Step3 A: wrap as <<value>> B: wrap as "
            "[[value]]; Step4 A: prefix the pair '<>:' B: prefix the pair "
            "'><:'; Step5 A: duplicate the string B: append the string length "
            "as a decimal digit."
        )
    if family == "modpair":
        return (
            "The input is two distinct 2-digit numbers named a and b. "
            "Step1 A: order the two numbers ascending B: descending; "
            "Step2 A: join them with '-' B: join them with ':'; "
            "Step3 A: prefix a duplicate of the smaller number's string B: "
            "prefix a duplicate of the larger number's string; "
            "Step4 A: replace every '9' with 'Z' B: replace every '0' with "
            "'O'; Step5 A: wrap in parentheses B: wrap in angle brackets."
        )
    raise ValueError(f"unknown novel procedure family {family!r}")


def _task(rng: random.Random | random.SystemRandom, family: str) -> dict[str, object]:
    """Sample one task whose 32 candidate programs all give distinct outputs."""

    if family == "bracket":
        for _ in range(500):
            value = "".join(rng.choice("<>") for _ in range(5))
            if _unambiguous(family, {"value": value}):
                return {"value": value}
        raise ValueError("unable to sample unambiguous bracket task")
    if family == "modpair":
        for _ in range(500):
            a = rng.randrange(10, 100)
            b = rng.randrange(10, 100)
            if a == b:
                continue
            if _unambiguous(family, {"a": a, "b": b}):
                return {"a": a, "b": b}
        raise ValueError("unable to sample unambiguous modpair task")
    raise ValueError(f"unknown novel procedure family {family!r}")


def _unambiguous(family: str, task: dict[str, object]) -> bool:
    outputs = {_execute(family, task, code) for code in CODES}
    return len(outputs) == 32
