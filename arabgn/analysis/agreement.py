"""Inter-annotator agreement. Cohen's κ and the κ ≥ 0.7 gate.

Implements ``docs/architecture.md`` §8.1 and ``docs/linguistic-spec.md`` §8.3/§8.4.
Pure — enters the freeze manifest.

``unclear`` is a **category, not a missing value**
--------------------------------------------------
Spec §8.1: "``unclear`` is a valid answer. Annotators are not asked to guess, and
the rate of ``unclear`` is itself reported." It therefore participates in κ as a
third category rather than being dropped or coerced. Dropping it would inflate κ
by discarding exactly the cases annotators found hardest, which is the same
failure mode CLAUDE.md prohibition 3 forbids for abstentions.

The gate
--------
Architecture §8.1 sets κ ≥ 0.7 as the threshold below which the gold set is not
usable. :func:`assert_gold_set_usable` raises rather than warns — every
precision/recall figure downstream is uninterpretable below it, so a printed
warning that a caller can ignore would be the wrong shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

__all__ = [
    "AnnotationLabel",
    "KappaResult",
    "cohens_kappa",
    "KAPPA_FLOOR",
    "assert_gold_set_usable",
    "GoldSetUnusable",
    "adjudicate",
]

#: Architecture §8.1: "≥ 0.7 before adjudication is usable".
KAPPA_FLOOR = 0.7

#: The three permitted answers (spec §8.1). Ordered for deterministic
#: confusion-matrix construction — never derived from set iteration.
AnnotationLabel = ("applicant", "non_applicant", "unclear")


class GoldSetUnusable(Exception):
    """Raised when κ falls below the floor. Not a warning."""


@dataclass(frozen=True, slots=True)
class KappaResult:
    """Cohen's κ with the counts it was computed from.

    ``kappa`` is ``None`` when κ is mathematically undefined — see
    :func:`cohens_kappa`.
    """

    kappa: float | None
    observed_agreement: float
    expected_agreement: float
    n_items: int
    unclear_rate: float
    undefined_reason: str | None = None

    @property
    def meets_floor(self) -> bool:
        return self.kappa is not None and self.kappa >= KAPPA_FLOOR


def cohens_kappa(
    annotator_a: Sequence[str],
    annotator_b: Sequence[str],
    *,
    labels: Sequence[str] = AnnotationLabel,
) -> KappaResult:
    """Cohen's κ over a double-annotated subset.

    ``κ = (p_o - p_e) / (1 - p_e)``

    Parameters
    ----------
    annotator_a, annotator_b:
        Parallel label sequences over the same items, in the same order.
    labels:
        The label space. Defaults to all three of spec §8.1, **including
        ``unclear``** — see the module docstring.

    Undefined κ
    -----------
    When ``p_e == 1`` the denominator vanishes and κ is undefined. This is not an
    edge case to paper over: it happens exactly when both annotators used a single
    label for everything, which is precisely when an agreement statistic is least
    informative. ``kappa`` is ``None`` with ``undefined_reason`` set, rather than
    returning ``0.0`` or ``1.0`` — either would be a fabricated number entering a
    reported table.

    Examples
    --------
    >>> r = cohens_kappa(["applicant", "non_applicant"], ["applicant", "non_applicant"])
    >>> r.kappa
    1.0
    >>> r.unclear_rate
    0.0
    """
    if len(annotator_a) != len(annotator_b):
        raise ValueError(
            f"annotator sequences differ in length: "
            f"{len(annotator_a)} vs {len(annotator_b)}"
        )
    n = len(annotator_a)
    if n == 0:
        raise ValueError("cannot compute κ over an empty subset")

    label_set = tuple(labels)
    for seq, name in ((annotator_a, "annotator_a"), (annotator_b, "annotator_b")):
        unknown = [x for x in seq if x not in label_set]
        if unknown:
            raise ValueError(
                f"{name} used labels outside the permitted space {label_set}: "
                f"{sorted(set(unknown))}. `unclear` must be recorded as itself, "
                f"never coerced (spec §8.1)."
            )

    agreed = sum(1 for a, b in zip(annotator_a, annotator_b) if a == b)
    p_o = agreed / n

    # Expected agreement by chance, from the marginals. Iterated over `label_set`
    # in declared order, never over a set (prohibition 6).
    p_e = 0.0
    for label in label_set:
        p_a = sum(1 for x in annotator_a if x == label) / n
        p_b = sum(1 for x in annotator_b if x == label) / n
        p_e += p_a * p_b

    unclear_total = sum(1 for x in annotator_a if x == "unclear") + sum(
        1 for x in annotator_b if x == "unclear"
    )
    unclear_rate = unclear_total / (2 * n)

    if p_e >= 1.0:
        return KappaResult(
            kappa=None,
            observed_agreement=p_o,
            expected_agreement=p_e,
            n_items=n,
            unclear_rate=unclear_rate,
            undefined_reason=(
                "expected agreement is 1.0 — both annotators used a single label "
                "for every item, so κ is undefined (0/0). Reported as undefined "
                "rather than as a number."
            ),
        )

    return KappaResult(
        kappa=(p_o - p_e) / (1.0 - p_e),
        observed_agreement=p_o,
        expected_agreement=p_e,
        n_items=n,
        unclear_rate=unclear_rate,
    )


def assert_gold_set_usable(result: KappaResult) -> None:
    """Hard gate. Raise unless κ ≥ 0.7 (architecture §8.1).

    Below the floor the gold set is not usable and every downstream
    precision/recall figure is uninterpretable, so this raises rather than
    warning. This gate can genuinely fail — referent classification is a hard
    annotation task — and a failure means re-briefing annotators or revisiting the
    guidelines, not lowering the floor.
    """
    if result.kappa is None:
        raise GoldSetUnusable(
            f"κ is undefined over n={result.n_items}: {result.undefined_reason}"
        )
    if result.kappa < KAPPA_FLOOR:
        raise GoldSetUnusable(
            f"κ = {result.kappa:.3f} < {KAPPA_FLOOR} (architecture §8.1). "
            f"The gold set is not usable and no precision/recall figure derived "
            f"from it is interpretable. Observed agreement {result.observed_agreement:.3f}, "
            f"expected {result.expected_agreement:.3f}, n={result.n_items}, "
            f"unclear rate {result.unclear_rate:.3f}."
        )


def adjudicate(
    annotator_a: str, annotator_b: str, third: str | None = None
) -> str:
    """Resolve one disagreement. Spec §8.4.

    Agreement stands. A disagreement goes to a third annotator. **Persistent
    disagreement after adjudication is recorded as ``unclear`` and reported, not
    forced to a label** — if the third annotator's answer matches neither of the
    first two, the item is genuinely indeterminate and saying so is the honest
    outcome.
    """
    if annotator_a == annotator_b:
        return annotator_a
    if third is None:
        raise ValueError(
            "disagreement requires a third annotator (spec §8.4); "
            "it must not be resolved by rule"
        )
    if third in (annotator_a, annotator_b):
        return third
    return "unclear"
