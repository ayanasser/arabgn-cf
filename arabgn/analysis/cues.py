"""Cue detection and rationality mass. Spec §2, §3.1, §4.2.

Pure — enters the freeze manifest. Takes candidate analyses as **data** and never
loads a model; the disambiguator lives in :mod:`arabgn.tagger.analyzer` (ADR 007).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from arabgn.contracts import Gender, Rationality

__all__ = [
    "CONTENT_POS",
    "EXCLUDED_POS",
    "CandidateAnalysis",
    "is_cue_pos",
    "carries_gender",
    "rationality_mass",
    "gender_disagreement",
    "form_divergence",
    "dominant_gender",
]

#: Spec §3.1 — included POS classes.
CONTENT_POS = frozenset(
    {"noun", "noun_prop", "adj", "verb", "adj_comp", "noun_quant"}
)

#: Spec §3.1 — excluded. Function words return spurious gender and rationality:
#: ``على`` returns ``rat={n, na, r}``, which would flood the abstain queue.
#: Guarded by fixtures N01 (``على``) and N02 (``2018``).
EXCLUDED_POS = frozenset(
    {"prep", "conj", "part", "pron", "punc", "digit", "abbrev"}
)


@dataclass(frozen=True, slots=True)
class CandidateAnalysis:
    """One scored candidate analysis, reduced to the fields the design uses.

    Deliberately not the raw CAMeL dict: keeping this narrow is what lets
    ``analysis/`` stay independent of the toolkit and testable without model
    downloads.
    """

    score: float
    pos: str | None
    rat: str | None
    gen: str | None
    form_gen: str | None
    stemcat: str | None


def is_cue_pos(pos: str | None) -> bool:
    """Spec §3.1 — is this POS a content class eligible to be a cue?

    Examples
    --------
    >>> is_cue_pos("noun"), is_cue_pos("verb")
    (True, True)
    >>> is_cue_pos("prep")      # على — fixture N01
    False
    >>> is_cue_pos("digit")     # 2018 — fixture N02
    False
    """
    if pos is None:
        return False
    return pos in CONTENT_POS


def carries_gender(gen: str | None) -> bool:
    """Spec §2 — a cue's analysis must carry ``gen ∈ {m, f}``.

    ``na`` is excluded explicitly by §3.1.
    """
    return gen in ("m", "f")


def rationality_mass(
    candidates: Iterable[CandidateAnalysis],
) -> dict[Rationality, float]:
    """Probability mass per rationality value across candidate analyses.

    Mass is the summed candidate ``score`` for each ``rat`` value, normalised by
    the total score across all candidates.

    Verified 12 August 2026 against ``BERTUnfactoredDisambiguator.pretrained(
    'msa', top=100)``. This method reproduces every mass recorded in ADR 001 to
    within 0.001:

    ======================  =========================
    ``خبرة`` (A04)          i = 0.9039  (ADR: 0.904)
    ``المرشحة`` (A01)       r = 0.7465  (ADR: 0.747)
    ``حاصلة`` (B01)         i = 0.6757  (ADR: 0.676)
    ======================  =========================

    .. note::
       **Spec wording discrepancy.** Spec §4.2 says the mass is computed "using
       the analyses' log-probabilities". Summing ``exp(pos_lex_logprob)`` instead
       gives i = 0.7632 / r = 0.2368 for ``حاصلة`` — which does *not* reproduce
       ADR 001's calibration evidence. The ``score`` field does. Since θ is
       calibrated against these numbers and then frozen, the two methods are not
       interchangeable and the spec wording needs amending to say "candidate
       scores". Raised for author decision; recorded in `docs/AUTHOR-ACTIONS.md`.

    Returns ``{}`` for an empty candidate set — the caller decides whether that is
    an abstain or a non-cue, rather than this function inventing a mass.
    """
    # math.fsum, not the `+` operator. Floating-point addition is not
    # associative, so plain summation makes the result depend on candidate order
    # in the last bits — 0.5625 vs 0.5625000000000001. That is a prohibition-6
    # violation with two real consequences: a mass sitting near θ could resolve
    # differently depending on iteration order, and serialised output would not
    # be byte-stable, so the freeze hash would not reproduce. fsum is
    # exactly-rounded and therefore genuinely order-independent.
    buckets: dict[Rationality, list[float]] = defaultdict(list)
    scores: list[float] = []
    for candidate in candidates:
        scores.append(candidate.score)
        if candidate.rat in ("r", "i", "n"):
            buckets[Rationality(candidate.rat)].append(candidate.score)

    total = math.fsum(scores)
    if total <= 0.0:
        return {}

    totals = {rat: math.fsum(vals) for rat, vals in buckets.items()}

    # Iterated in the declared canonical order, never over a dict/set whose order
    # could vary (prohibition 6).
    return {
        rat: totals[rat] / total
        for rat in (Rationality.R, Rationality.I, Rationality.N)
        if rat in totals
    }


def gender_disagreement(candidates: Sequence[CandidateAnalysis]) -> bool:
    """AB4 — do candidate analyses disagree on ``gen`` after disambiguation?

    Only ``m`` / ``f`` count; ``na`` and ``None`` are not gender readings and a
    token carrying both ``f`` and ``na`` is not in disagreement about gender.
    """
    genders = {c.gen for c in candidates if c.gen in ("m", "f")}
    return len(genders) > 1


def form_divergence(gen: str | None, form_gen: str | None) -> bool:
    """AB5 — functional/form gender divergence (spec §7.4).

    ``طلبة`` is form-feminine but functionally masculine plural. Both must be
    real gender values for the comparison to mean anything.
    """
    if not carries_gender(gen) or not carries_gender(form_gen):
        return False
    return gen != form_gen


def dominant_gender(candidates: Sequence[CandidateAnalysis]) -> Gender | None:
    """The gender carried by the highest-scoring gendered candidate.

    Ties are broken by ``m`` before ``f`` — declared rather than left to sort
    stability, so the result cannot vary with candidate ordering (prohibition 6).
    """
    gendered = [c for c in candidates if carries_gender(c.gen)]
    if not gendered:
        return None
    best = max(gendered, key=lambda c: (c.score, c.gen == "m"))
    return Gender(best.gen)
