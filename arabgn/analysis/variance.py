"""Variance decomposition and two-way cluster-robust inference. Architecture §7.3.

Pure — enters the freeze manifest.

The decomposition
-----------------
For a twin contrast over ``A`` ads × ``C`` CV twins::

    SE² = σ²_ad / A  +  σ²_cv / C  +  σ²_resid / (A · C)

**Open issue, architecture §7.3 and §10 decision 4.** In a paired design where the
female and male twin from the same pair are differenced, the pair-level random
effect *cancels in that difference* and should not contribute to the SE of the
contrast. If σ²_cv denotes **twin-discordance variance** — the variance of the
difference across pairs — the formula is correct; but the notation reads like a
CV-level random effect, and a statistics reviewer will query it.

This module implements the twin-discordance reading and says so in
:func:`decompose_variance`, because that is the one that is arithmetically correct
for a paired contrast. **The author must still write the defining sentence** — the
choice of words is not an implementer's call, and it blocks the C4 freeze.

Two-way cluster-robust variance
-------------------------------
Observations cluster on **both** ads and twins, and the clusters are crossed, not
nested. :func:`two_way_cluster_robust_se` uses the Cameron–Gelbach–Miller
inclusion–exclusion estimator::

    V = V_ad + V_pair − V_both

The proposal reports a 1.6× inflation on real structure versus treating resample
draws as units, and that resample-as-unit understates SE "by more than an order of
magnitude". :func:`naive_iid_se` exists so that comparison can be computed and
reported — it is itself a finding, not a strawman.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

__all__ = [
    "VarianceComponents",
    "ClusterRobustResult",
    "decompose_variance",
    "predicted_se",
    "two_way_cluster_robust_se",
    "naive_iid_se",
    "se_inflation_factor",
]


@dataclass(frozen=True, slots=True)
class VarianceComponents:
    """Estimated components. ``sigma2_cv`` is twin-discordance variance.

    See the module docstring: the naming follows architecture §7.3, but the
    *meaning* is the variance of the per-pair difference, not a CV-level random
    effect. Architecture §10 decision 4 must state this in one sentence before
    the C4 freeze.
    """

    sigma2_ad: float
    sigma2_cv: float
    sigma2_resid: float
    n_ads: int
    n_pairs: int
    #: Carried so a reader cannot mistake the reading. Reported verbatim.
    sigma2_cv_definition: str = (
        "twin-discordance variance: the variance of the female-minus-male "
        "difference across pairs, NOT a CV-level random effect. The pair-level "
        "effect cancels in the paired difference (architecture §7.3, §10 #4 — "
        "author must confirm the wording)."
    )


def _pivot(differences: Sequence[tuple[str, str, float]]):
    """(ad_id, pair_id, difference) → matrix, with sorted axes.

    Sorted so the result never depends on input order (prohibition 6).
    """
    ads = sorted({a for a, _, _ in differences})
    pairs = sorted({p for _, p, _ in differences})
    index_ad = {a: i for i, a in enumerate(ads)}
    index_pair = {p: i for i, p in enumerate(pairs)}

    matrix = np.full((len(ads), len(pairs)), np.nan)
    for ad_id, pair_id, value in differences:
        matrix[index_ad[ad_id], index_pair[pair_id]] = value
    return matrix, ads, pairs


def decompose_variance(
    differences: Sequence[tuple[str, str, float]],
) -> VarianceComponents:
    """Estimate σ²_ad, σ²_cv and σ²_resid from per-pair differences.

    Uses a balanced two-way ANOVA decomposition on the **difference** scale, which
    is where the contrast lives. Working on the difference scale is what makes the
    pair-level effect cancel — see the module docstring.

    Components are clipped at zero: a negative variance estimate is a known
    artifact of the method of moments on small samples, and reporting a negative
    variance would be worse than reporting zero. The clipping is disclosed here
    rather than hidden.
    """
    matrix, ads, pairs = _pivot(differences)
    n_ads, n_pairs = matrix.shape
    if n_ads < 2 or n_pairs < 2:
        raise ValueError(
            f"need >=2 ads and >=2 pairs to separate the components; "
            f"got {n_ads} x {n_pairs}"
        )
    if np.isnan(matrix).any():
        raise ValueError(
            "unbalanced design: every (ad, pair) cell must be present. "
            "Silently dropping cells would bias the components."
        )

    grand = matrix.mean()
    ad_means = matrix.mean(axis=1)
    pair_means = matrix.mean(axis=0)

    ms_ad = n_pairs * ((ad_means - grand) ** 2).sum() / (n_ads - 1)
    ms_pair = n_ads * ((pair_means - grand) ** 2).sum() / (n_pairs - 1)

    residual = matrix - ad_means[:, None] - pair_means[None, :] + grand
    ms_resid = (residual**2).sum() / ((n_ads - 1) * (n_pairs - 1))

    return VarianceComponents(
        sigma2_ad=max(0.0, (ms_ad - ms_resid) / n_pairs),
        sigma2_cv=max(0.0, (ms_pair - ms_resid) / n_ads),
        sigma2_resid=max(0.0, ms_resid),
        n_ads=n_ads,
        n_pairs=n_pairs,
    )


def predicted_se(
    components: VarianceComponents, n_ads: int, n_pairs: int
) -> float:
    """SE² = σ²_ad/A + σ²_cv/C + σ²_resid/(A·C). Architecture §7.3.

    Used for the power curves: it answers "what SE would we get at this A and C?"
    without running the design.
    """
    if n_ads < 1 or n_pairs < 1:
        raise ValueError("n_ads and n_pairs must be >= 1")
    variance = (
        components.sigma2_ad / n_ads
        + components.sigma2_cv / n_pairs
        + components.sigma2_resid / (n_ads * n_pairs)
    )
    return float(np.sqrt(variance))


@dataclass(frozen=True, slots=True)
class ClusterRobustResult:
    """A mean difference with its SE and the clustering that produced it.

    ``clustering`` is carried, not optional: architecture §7.4 requires "every
    interval reported with its clustering structure named". An interval whose
    clustering is unstated is not reportable.
    """

    mean_difference: float
    se: float
    n_observations: int
    n_ad_clusters: int
    n_pair_clusters: int
    clustering: str = "two-way cluster-robust over ads and twin pairs"

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float]:
        return (
            self.mean_difference - z * self.se,
            self.mean_difference + z * self.se,
        )


def two_way_cluster_robust_se(
    differences: Sequence[tuple[str, str, float]],
) -> ClusterRobustResult:
    """Cameron–Gelbach–Miller two-way cluster-robust SE of the mean difference.

    ``V = V_ad + V_pair − V_both``. Clusters on ads and twin pairs are **crossed**,
    so one-way clustering on either alone understates the SE.

    The estimator can return a negative variance in small samples — a documented
    property of the inclusion–exclusion form. When it does, this falls back to
    ``max(V_ad, V_pair)`` and says so in ``clustering``, rather than taking the
    square root of a negative number or silently returning zero.
    """
    matrix, ads, pairs = _pivot(differences)
    if np.isnan(matrix).any():
        raise ValueError("unbalanced design: every (ad, pair) cell must be present")

    n_ads, n_pairs = matrix.shape
    n = n_ads * n_pairs
    mean = matrix.mean()
    centred = matrix - mean

    # Sum of within-cluster score sums, squared — the standard sandwich form for
    # a mean, scaled to the variance of the mean.
    v_ad = (centred.sum(axis=1) ** 2).sum() / (n**2)
    v_pair = (centred.sum(axis=0) ** 2).sum() / (n**2)
    v_both = (centred**2).sum() / (n**2)

    variance = v_ad + v_pair - v_both
    clustering = "two-way cluster-robust over ads and twin pairs"

    if variance <= 0:
        variance = max(v_ad, v_pair)
        clustering += (
            " (inclusion-exclusion gave a non-positive variance in this sample; "
            "fell back to max of the one-way estimators)"
        )

    return ClusterRobustResult(
        mean_difference=float(mean),
        se=float(np.sqrt(variance)),
        n_observations=n,
        n_ad_clusters=n_ads,
        n_pair_clusters=n_pairs,
        clustering=clustering,
    )


def naive_iid_se(differences: Sequence[tuple[str, str, float]]) -> float:
    """SE treating every observation as independent. **Wrong by construction.**

    Exists so the comparison in architecture §7.3 can be computed and reported:
    treating resample draws as units of analysis "understates the standard error
    by more than an order of magnitude, whereas two-way cluster-robust variance
    over ads and twins recovers a 1.6× inflation on real structure — that
    comparison is itself a reportable finding."

    Never use this for inference.
    """
    values = np.array([d for _, _, d in differences], dtype=float)
    if values.size < 2:
        raise ValueError("need >=2 observations")
    return float(values.std(ddof=1) / np.sqrt(values.size))


def se_inflation_factor(differences: Sequence[tuple[str, str, float]]) -> float:
    """Cluster-robust SE ÷ naive iid SE. Architecture §7.3, §8.6.

    A reportable quantity, not a diagnostic: it measures how much the design's
    real clustering structure inflates uncertainty relative to the common (wrong)
    practice.
    """
    robust = two_way_cluster_robust_se(differences).se
    naive = naive_iid_se(differences)
    if naive == 0:
        raise ValueError("naive SE is zero; inflation factor is undefined")
    return robust / naive
