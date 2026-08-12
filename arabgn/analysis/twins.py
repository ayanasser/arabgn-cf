"""Twin CV pair invariants. Architecture §5.2.

Pure — enters the freeze manifest. Takes tokens as **data** and never loads a
model or a tokenizer, the same boundary `cues.py` keeps (ADR 007).

Why the proposal's invariant was replaced
-----------------------------------------
The SS2 proposal promises "a gender-controlled twin CV generator that refuses to
emit a pair differing in token count". Architecture §5.2 withdraws that, and the
reason is worth restating because this module exists to implement the
replacement:

    حاصل / حاصلة differ under every subword tokenizer in the audit set. A strict
    equality constraint therefore either blocks all output or forces silent
    padding — and padding is itself a confound.

So the tokenization delta is **measured and reported per audit subject, never
forced to zero**, and it is deliberately *not* part of
:attr:`TwinReport.satisfied`. A pair with a non-zero delta is a valid pair whose
delta is a covariate. Asserted by
``test_tokenization_delta_is_not_a_pass_condition``.

What *is* enforced (architecture §5.2)
--------------------------------------
1. Identical content-word count.
2. Identical qualification slot values (degree, years, institution, skills).
3. Character-length difference within a **declared** tolerance.
4. Zero difference in any non-gender lexical item, asserted by diff.

This module does not decide what a gender alternation is
--------------------------------------------------------
Invariant 4 needs to separate "differs because it is the gendered twin of its
counterpart" from "differs because the generator leaked a lexical change". Rather
than infer that morphologically — which would be an unreviewed linguistic rule
entering the freeze — the **generator declares** the alternations it applied, and
this module checks that the observed diff is a subset of them.

That inverts the burden correctly. A generator that quietly changed
``جامعة القاهرة`` to ``جامعة عين شمس`` between twins cannot hide it by having
also changed a participle: the institution swap is not in the declared set, so
the pair fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from arabgn.analysis.cues import CONTENT_POS

__all__ = [
    "TwinToken",
    "TwinCV",
    "TwinPair",
    "TwinReport",
    "Alternation",
    "check_twin_pair",
    "tokenization_deltas",
]

#: One declared gender alternation, ``(masculine_surface, feminine_surface)``.
#: e.g. ``("حاصل", "حاصلة")`` or ``("تخرج", "تخرجت")``.
Alternation = tuple[str, str]


@dataclass(frozen=True, slots=True)
class TwinToken:
    """One token, reduced to what the invariants need.

    ``pos`` is supplied by the caller — this module never runs a tagger. ``None``
    is permitted and counts as a non-content word, so an untagged pair fails the
    content-word invariant loudly rather than passing it vacuously.
    """

    surface: str
    pos: str | None = None

    @property
    def is_content(self) -> bool:
        """Spec §3.1's content classes, the same set cue detection uses."""
        return self.pos in CONTENT_POS


@dataclass(frozen=True, slots=True)
class TwinCV:
    """One half of a twin pair."""

    text: str
    tokens: tuple[TwinToken, ...]
    #: Qualification slots: degree, years, institution, skills. Values must be
    #: identical across the pair — a twin contrast that also varies a
    #: qualification is not a gender contrast.
    slots: Mapping[str, str]

    @property
    def content_word_count(self) -> int:
        return sum(1 for token in self.tokens if token.is_content)


@dataclass(frozen=True, slots=True)
class TwinPair:
    """A (female, male) pair and the alternations the generator declared."""

    female: TwinCV
    male: TwinCV
    #: ``(masculine, feminine)`` surfaces the generator deliberately varied.
    declared_alternations: frozenset[Alternation]


@dataclass(frozen=True, slots=True)
class TwinReport:
    """Per-invariant outcome. Every field is reported, pass or fail.

    A boolean alone would tell a reviewer the pair failed without telling them
    which guarantee broke, and the guarantees are the contribution.
    """

    content_word_counts: tuple[int, int]
    content_word_count_equal: bool

    slots_identical: bool
    #: Slot names whose values differ, sorted. Empty when identical.
    differing_slots: tuple[str, ...]

    char_delta: int
    char_tolerance: int
    within_char_tolerance: bool

    #: Could the two token sequences be aligned position-by-position at all?
    #: False when they differ in length, which makes the diff below unreadable
    #: rather than empty.
    alignable: bool
    #: ``(index, male_surface, female_surface)`` for every position that differs
    #: and is **not** a declared alternation. Non-empty means lexical leakage.
    undeclared_differences: tuple[tuple[int, str, str], ...]

    @property
    def satisfied(self) -> bool:
        """All four enforced invariants hold.

        Tokenization delta is **not** consulted — architecture §5.2 makes it a
        measured covariate, not a gate. See :func:`tokenization_deltas`.
        """
        return (
            self.content_word_count_equal
            and self.slots_identical
            and self.within_char_tolerance
            and self.alignable
            and not self.undeclared_differences
        )

    def explain(self) -> str:
        """Why the pair failed, in the order the invariants are declared."""
        if self.satisfied:
            return "all §5.2 invariants hold"
        reasons = []
        if not self.content_word_count_equal:
            female, male = self.content_word_counts
            reasons.append(
                f"content-word count differs: female {female}, male {male}"
            )
        if not self.slots_identical:
            reasons.append(
                f"qualification slots differ: {list(self.differing_slots)}"
            )
        if not self.within_char_tolerance:
            reasons.append(
                f"character-length delta {self.char_delta} exceeds the declared "
                f"tolerance {self.char_tolerance}"
            )
        if not self.alignable:
            reasons.append(
                "token sequences differ in length, so no position-by-position "
                "diff is possible"
            )
        for index, male, female in self.undeclared_differences:
            reasons.append(
                f"undeclared difference at token {index}: "
                f"male {male!r} vs female {female!r}"
            )
        return "; ".join(reasons)


def check_twin_pair(pair: TwinPair, *, char_tolerance: int) -> TwinReport:
    """Check architecture §5.2's four enforced invariants.

    ``char_tolerance`` has **no default**. §5.2 requires a *declared* tolerance,
    and a default would be an undeclared one — the same reason θ has no default.

    Examples
    --------
    A well-formed pair differing only in the declared participle::

        حاصلة على بكالوريوس هندسة   (female)
        حاصل على بكالوريوس هندسة    (male)

    with ``declared_alternations = {("حاصل", "حاصلة")}`` satisfies all four.
    Swapping ``القاهرة`` for ``عين شمس`` in one twin does not, because that
    difference was never declared.
    """
    if char_tolerance < 0:
        raise ValueError(
            f"char_tolerance must be non-negative, got {char_tolerance}"
        )

    female, male = pair.female, pair.male

    counts = (female.content_word_count, male.content_word_count)

    differing_slots = tuple(
        sorted(
            key
            for key in set(female.slots) | set(male.slots)
            if female.slots.get(key) != male.slots.get(key)
        )
    )

    char_delta = abs(len(female.text) - len(male.text))

    alignable = len(female.tokens) == len(male.tokens)
    undeclared: list[tuple[int, str, str]] = []
    if alignable:
        for index, (f_token, m_token) in enumerate(
            zip(female.tokens, male.tokens)
        ):
            if f_token.surface == m_token.surface:
                continue
            if (m_token.surface, f_token.surface) in pair.declared_alternations:
                continue
            undeclared.append((index, m_token.surface, f_token.surface))

    return TwinReport(
        content_word_counts=counts,
        content_word_count_equal=counts[0] == counts[1],
        slots_identical=not differing_slots,
        differing_slots=differing_slots,
        char_delta=char_delta,
        char_tolerance=char_tolerance,
        within_char_tolerance=char_delta <= char_tolerance,
        alignable=alignable,
        undeclared_differences=tuple(undeclared),
    )


def tokenization_deltas(
    pair: TwinPair,
    tokenizers: Mapping[str, Callable[[str], Sequence[object]]],
) -> Mapping[str, int]:
    """Signed token-count delta (female − male) per audit subject.

    Architecture §5.2: "Per-pair tokenization delta measured and reported per
    audit subject, not forced to zero." Each audit subject tokenizes differently,
    so there is no single delta for a pair — hence a mapping keyed by subject.

    Tokenizers are **injected** rather than imported, which is what keeps this
    module inside the freeze while the tokenizers themselves stay outside it —
    the same pattern :func:`arabgn.analysis.freeze.compute_freeze_hash` uses for
    reading source files.

    Signed, not absolute: the sign carries information. A subject that
    consistently makes feminine CVs longer is a subject where length and gender
    are confounded, and averaging away the sign would hide it.

    Returned in sorted key order (prohibition 6).
    """
    return {
        subject: len(tokenize(pair.female.text)) - len(tokenize(pair.male.text))
        for subject, tokenize in sorted(tokenizers.items())
    }
