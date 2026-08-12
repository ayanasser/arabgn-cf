"""Multiplicity correction, equivalence testing and power. Architecture §7.3.

Pure — enters the freeze manifest.

Three required components:

* **Holm correction**, with the family **declared explicitly**. Architecture §7.3:
  "subjects × registers × outcome measures multiplies quickly, and an undeclared
  family is a common reviewer objection." :func:`holm` therefore *requires* a
  family description and refuses to run without one.
* **TOST** for equivalence margins. Absence of evidence is not evidence of
  absence: a non-significant difference does not license "equivalent". TOST is
  what licenses it, and only within a declared margin.
* **Power curves** over A and C at the declared margins, so the feasibility
  verdict in C3 is derived rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy import stats

from arabgn.analysis.variance import VarianceComponents, predicted_se

__all__ = [
    "HolmResult",
    "holm",
    "TOSTResult",
    "tost",
    "PowerPoint",
    "power_curve",
    "required_n_ads",
]


# ---------------------------------------------------------------------------
# Holm — architecture §7.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HolmResult:
    """Holm-adjusted p-values with the family that was corrected over."""

    labels: tuple[str, ...]
    raw_p: tuple[float, ...]
    adjusted_p: tuple[float, ...]
    rejected: tuple[bool, ...]
    alpha: float
    #: Required. An undeclared family is the reviewer objection §7.3 names.
    family: str

    def summary(self) -> str:
        lines = [f"Holm correction over family: {self.family}", f"alpha = {self.alpha}"]
        for label, raw, adj, rej in zip(
            self.labels, self.raw_p, self.adjusted_p, self.rejected
        ):
            lines.append(
                f"  {label}: p={raw:.5f} -> {adj:.5f} "
                f"{'REJECT' if rej else 'retain'}"
            )
        return "\n".join(lines)


def holm(
    p_values: Mapping[str, float], *, alpha: float = 0.05, family: str
) -> HolmResult:
    """Holm step-down correction.

    ``family`` is a **required keyword** describing what was corrected over — for
    example ``"6 subjects x 5 registers x 2 outcome measures = 60 tests"``.
    Architecture §7.3 makes an undeclared family a named reviewer objection, so
    the parameter cannot be omitted or left blank.

    Deterministic: ties in p are broken by label, never by dict order
    (prohibition 6).
    """
    if not family or not family.strip():
        raise ValueError(
            "the Holm family must be declared explicitly (architecture §7.3). "
            "An undeclared family is a common reviewer objection."
        )
    if not p_values:
        raise ValueError("no p-values supplied")
    for label, p in p_values.items():
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"p-value for {label!r} is {p}, not in [0, 1]")

    # Sorted by p, then label — a deterministic tie-break.
    ordered = sorted(p_values.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(ordered)

    adjusted: list[float] = []
    running = 0.0
    for i, (_, p) in enumerate(ordered):
        running = max(running, (m - i) * p)  # enforce monotonicity
        adjusted.append(min(1.0, running))

    labels = tuple(label for label, _ in ordered)
    return HolmResult(
        labels=labels,
        raw_p=tuple(p for _, p in ordered),
        adjusted_p=tuple(adjusted),
        rejected=tuple(a <= alpha for a in adjusted),
        alpha=alpha,
        family=family.strip(),
    )


# ---------------------------------------------------------------------------
# TOST — architecture §7.3, §7.4
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TOSTResult:
    """Two one-sided tests for equivalence within ±``margin``."""

    mean_difference: float
    se: float
    margin: float
    p_lower: float
    p_upper: float
    df: float
    alpha: float

    @property
    def p_value(self) -> float:
        """TOST p is the larger of the two one-sided p-values."""
        return max(self.p_lower, self.p_upper)

    @property
    def equivalent(self) -> bool:
        """Equivalence is *demonstrated*, not inferred from a null result."""
        return self.p_value <= self.alpha


def tost(
    mean_difference: float,
    se: float,
    *,
    margin: float,
    df: float,
    alpha: float = 0.05,
) -> TOSTResult:
    """Two one-sided tests against ±``margin``.

    A non-significant difference does **not** demonstrate equivalence — that is
    the inferential error the whole paper is about. TOST is what licenses an
    equivalence claim, and only inside the declared margin.

    ``margin`` must be positive: an equivalence claim against a zero-width margin
    is unfalsifiable.
    """
    if margin <= 0:
        raise ValueError(
            f"equivalence margin must be positive, got {margin}. A zero-width "
            f"margin makes the claim unfalsifiable."
        )
    if se <= 0:
        raise ValueError(f"se must be positive, got {se}")

    t_lower = (mean_difference + margin) / se
    t_upper = (mean_difference - margin) / se
    return TOSTResult(
        mean_difference=mean_difference,
        se=se,
        margin=margin,
        p_lower=float(stats.t.sf(t_lower, df)),
        p_upper=float(stats.t.cdf(t_upper, df)),
        df=df,
        alpha=alpha,
    )


# ---------------------------------------------------------------------------
# Power — architecture §7.3, §8.6
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PowerPoint:
    """Achieved power at one (A, C) design point."""

    n_ads: int
    n_pairs: int
    se: float
    power: float
    margin: float


def power_curve(
    components: VarianceComponents,
    *,
    margin: float,
    n_ads_grid: Sequence[int],
    n_pairs: int,
    alpha: float = 0.05,
) -> tuple[PowerPoint, ...]:
    """Power to detect an effect of size ``margin`` across a grid of A.

    Architecture §7.3's key consequence: the **ad axis caps attainable
    precision**, because σ²_ad/A does not shrink with C. Sweeping A at fixed C is
    what shows that — buying more CVs cannot buy past the ad-level term.

    Two-sided z-approximation; adequate for a feasibility verdict, and stated as
    an approximation rather than presented as exact.
    """
    if margin <= 0:
        raise ValueError("margin must be positive")

    critical = stats.norm.isf(alpha / 2.0)
    points: list[PowerPoint] = []
    for n_ads in sorted(set(n_ads_grid)):
        se = predicted_se(components, n_ads, n_pairs)
        ncp = margin / se
        power = float(stats.norm.sf(critical - ncp) + stats.norm.cdf(-critical - ncp))
        points.append(
            PowerPoint(
                n_ads=n_ads, n_pairs=n_pairs, se=se, power=power, margin=margin
            )
        )
    return tuple(points)


def required_n_ads(
    components: VarianceComponents,
    *,
    margin: float,
    n_pairs: int,
    target_power: float = 0.8,
    alpha: float = 0.05,
    max_ads: int = 100_000,
) -> int | None:
    """Smallest A reaching ``target_power``, or ``None`` if unattainable.

    ``None`` is a real and important answer, not a failure: architecture §7.3
    reports that at a top-10-of-100 base rate the principled 1 pp margin "is not
    powerable on the selection-rate outcome at feasible cost". Returning ``None``
    rather than an enormous number makes that verdict explicit.

    The ad-axis floor is why: as A → ∞, SE → sqrt(σ²_cv / C), which does not
    depend on A at all. If that floor already exceeds what the margin needs, no
    number of ads suffices.
    """
    if not 0 < target_power < 1:
        raise ValueError("target_power must be in (0, 1)")

    # Floor as A -> infinity: only the pair-level term survives.
    floor_se = float(np.sqrt(components.sigma2_cv / n_pairs))
    if floor_se > 0:
        critical = stats.norm.isf(alpha / 2.0)
        best_power = float(
            stats.norm.sf(critical - margin / floor_se)
            + stats.norm.cdf(-critical - margin / floor_se)
        )
        if best_power < target_power:
            return None  # unattainable at any A

    low, high = 1, max_ads
    if (
        power_curve(
            components, margin=margin, n_ads_grid=[high], n_pairs=n_pairs, alpha=alpha
        )[0].power
        < target_power
    ):
        return None

    while low < high:
        mid = (low + high) // 2
        power = power_curve(
            components, margin=margin, n_ads_grid=[mid], n_pairs=n_pairs, alpha=alpha
        )[0].power
        if power >= target_power:
            high = mid
        else:
            low = mid + 1
    return low
