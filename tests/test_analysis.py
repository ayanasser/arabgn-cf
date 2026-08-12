"""Phase 10 — synthetic backend, variance, inference and guarded reporting.

Every estimator is checked against **known ground truth**: the synthetic backend
injects an effect of known size and a known variance structure, so a test can
assert recovery rather than asserting whatever the code returns.

Architecture §2: "Lets a reviewer re-run every estimator against known ground
truth." That is what makes these tests meaningful rather than circular.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.inference import (
    holm,
    power_curve,
    required_n_ads,
    tost,
)
from arabgn.analysis.reporting import (
    CellVerdict,
    ForbiddenClaim,
    assert_no_forbidden_claim,
    format_interval,
    render_report,
    verdict_for_cell,
)
from arabgn.analysis.variance import (
    VarianceComponents,
    decompose_variance,
    naive_iid_se,
    predicted_se,
    se_inflation_factor,
    two_way_cluster_robust_se,
)
from arabgn.scoring import ScoredPair, SyntheticBackend, SyntheticConfig


def differences(pairs):
    return [(p.ad_id, p.pair_id, p.difference) for p in pairs]


def synth(**over):
    cfg = SyntheticConfig(**over)
    backend = SyntheticBackend(cfg)
    ads = [f"ad{i:03d}" for i in range(40)]
    twins = [f"pair{i:03d}" for i in range(50)]
    return backend.score_pairs(ads, twins)


# ---------------------------------------------------------------------------
# Architecture §2 — the synthetic backend
# ---------------------------------------------------------------------------


def test_backend_is_deterministic_given_a_seed():
    """Prohibition 6 — the seed enters the run config and the freeze hash."""
    a = synth(effect=0.3, seed=7)
    b = synth(effect=0.3, seed=7)
    assert [p.difference for p in a] == [p.difference for p in b]


def test_backend_is_independent_of_id_order():
    """Prohibition 6 — output must not depend on the order ids arrive in."""
    cfg = SyntheticConfig(effect=0.2, seed=3)
    backend = SyntheticBackend(cfg)
    ads = ["a1", "a2", "a3"]
    twins = ["p1", "p2", "p3"]
    forward = backend.score_pairs(ads, twins)
    backward = backend.score_pairs(list(reversed(ads)), list(reversed(twins)))
    assert {(p.ad_id, p.pair_id, p.difference) for p in forward} == {
        (p.ad_id, p.pair_id, p.difference) for p in backward
    }


def test_different_seeds_give_different_draws():
    assert [p.difference for p in synth(seed=1)] != [
        p.difference for p in synth(seed=2)
    ]


def test_pair_LEVEL_effect_cancels_in_the_difference():
    """Architecture §7.3's open issue, made concrete.

    A CV-level random effect cancels in the female-minus-male difference.
    Raising `sd_pair` 100x must not change the differences at all — so σ²_cv in
    the SE formula CANNOT mean a CV-level random effect, or the formula would be
    wrong as written.
    """
    small = [p.difference for p in synth(effect=0.4, sd_pair=0.1, seed=5)]
    huge = [p.difference for p in synth(effect=0.4, sd_pair=10.0, seed=5)]
    assert small == pytest.approx(huge)


def test_pair_GENDER_interaction_does_not_cancel():
    """Twin discordance survives differencing — this is what σ²_cv denotes.

    Together with the test above, this pins the definition architecture §10
    decision 4 still owes a sentence for: σ²_cv is twin-discordance variance,
    not a CV-level random effect.
    """
    small = [p.difference for p in synth(effect=0.4, sd_pair_gender=0.01, seed=5)]
    large = [p.difference for p in synth(effect=0.4, sd_pair_gender=2.0, seed=5)]
    assert small != pytest.approx(large)


def test_ad_gender_interaction_does_not_cancel():
    """Ads differ in how much gender matters to them — σ²_ad in the SE formula."""
    small = [p.difference for p in synth(effect=0.4, sd_ad_gender=0.01, seed=5)]
    large = [p.difference for p in synth(effect=0.4, sd_ad_gender=2.0, seed=5)]
    assert small != pytest.approx(large)


def test_zero_effect_cell_has_no_signal():
    """Architecture §8.4 — the zero-cue calibration cell.

    "The instrument should return null. If it returns a signal, the pipeline has
    a leak."
    """
    result = two_way_cluster_robust_se(differences(synth(effect=0.0, seed=11)))
    low, high = result.confidence_interval()
    assert low < 0 < high, (
        f"zero-effect cell produced an interval excluding zero: [{low}, {high}] "
        f"— this indicates a leak (architecture §8.4)"
    )


def test_backend_rejects_an_empty_design():
    backend = SyntheticBackend(SyntheticConfig())
    with pytest.raises(ValueError, match="at least one ad"):
        backend.score_pairs([], ["p1"])


# ---------------------------------------------------------------------------
# Architecture §8.3 — positive control: recover a known effect
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("effect", [0.25, 0.5, 1.0])
def test_known_effect_is_recovered(effect):
    """Architecture §8.3 — instrument sensitivity.

    "If the instrument fails to recover it, every null elsewhere is
    uninterpretable. This is what makes a null result meaningful at all."
    """
    result = two_way_cluster_robust_se(
        differences(synth(effect=effect, seed=13))
    )
    low, high = result.confidence_interval()
    assert low <= effect <= high, (
        f"injected effect {effect} not covered by [{low:.4f}, {high:.4f}]"
    )
    assert result.mean_difference == pytest.approx(effect, abs=0.15)


# ---------------------------------------------------------------------------
# Architecture §7.3 — variance decomposition
# ---------------------------------------------------------------------------


def test_components_are_recovered_from_a_known_structure():
    """σ²_resid is recoverable; on the difference scale it is 2·sd_resid²."""
    components = decompose_variance(
        differences(synth(effect=0.0, sd_ad=0.0, sd_resid=1.0, seed=17))
    )
    assert components.sigma2_resid == pytest.approx(2.0, rel=0.2)


def test_sigma2_cv_is_documented_as_twin_discordance():
    """Architecture §10 decision 4 — the notation reads like a CV random effect.

    The definition travels with the value so a reader cannot mistake it. The
    author still owes the defining sentence; this makes the ambiguity impossible
    to miss.
    """
    components = decompose_variance(differences(synth(seed=19)))
    assert "twin-discordance" in components.sigma2_cv_definition
    assert "NOT a CV-level random effect" in components.sigma2_cv_definition


def test_decomposition_rejects_an_unbalanced_design():
    """Silently dropping cells would bias the components."""
    with pytest.raises(ValueError, match="unbalanced"):
        decompose_variance([("a1", "p1", 0.1), ("a1", "p2", 0.2), ("a2", "p1", 0.3)])


def test_decomposition_needs_at_least_two_of_each():
    with pytest.raises(ValueError, match=">=2 ads"):
        decompose_variance([("a1", "p1", 0.1), ("a1", "p2", 0.2)])


def test_predicted_se_shrinks_with_more_ads_and_pairs():
    components = VarianceComponents(0.1, 0.1, 1.0, 40, 50)
    assert predicted_se(components, 100, 50) < predicted_se(components, 10, 50)
    assert predicted_se(components, 40, 100) < predicted_se(components, 40, 10)


def test_the_ad_axis_caps_attainable_precision():
    """Architecture §7.3 consequence (i).

    "The ad axis — the expensive, human-authored one — caps attainable precision,
    so buying more ads cannot reach a tight equivalence margin at any number of
    CVs." The dual also holds: with σ²_cv > 0, SE has a floor no A can beat.
    """
    components = VarianceComponents(sigma2_ad=0.0, sigma2_cv=0.25, sigma2_resid=0.0,
                                    n_ads=40, n_pairs=50)
    floor = predicted_se(components, 10**6, 50)
    assert floor == pytest.approx((0.25 / 50) ** 0.5, rel=1e-6)
    assert predicted_se(components, 10**9, 50) == pytest.approx(floor, rel=1e-6)


# ---------------------------------------------------------------------------
# Architecture §7.3 — clustering
# ---------------------------------------------------------------------------


def test_level_effects_alone_produce_no_clustering_to_correct_for():
    """A model with only level effects gives iid differences.

    Both `ad[a]` and `pair[c]` cancel in the twin difference, so there is nothing
    for cluster-robust variance to recover and it should agree with the naive
    estimator. Asserting inflation here would be asserting an artifact.

    Averaged over seeds: at 40x50 the inflation factor has sd ~0.15 across
    draws, so a single seed is a noisy read on a quantity whose *expectation* is
    the claim. (Verified: mean 0.988 over 20 seeds at 40x50, 1.002 at 100x100.)
    """
    factors = [
        se_inflation_factor(
            differences(
                synth(effect=0.3, sd_ad=1.0, sd_pair=1.0,
                      sd_ad_gender=0.0, sd_pair_gender=0.0, seed=s)
            )
        )
        for s in range(20)
    ]
    assert sum(factors) / len(factors) == pytest.approx(1.0, abs=0.1)


def test_cluster_robust_se_exceeds_the_naive_iid_se():
    """The proposal's reportable finding: real structure inflates the SE.

    Inflation requires *interaction* terms — ads that differ in how much gender
    matters to them, and twin pairs that discord. Those survive differencing and
    are what σ²_ad and σ²_cv denote in architecture §7.3.
    """
    diffs = differences(
        synth(effect=0.3, sd_ad=1.0, sd_pair=1.0,
              sd_ad_gender=0.8, sd_pair_gender=0.8, seed=23)
    )
    assert two_way_cluster_robust_se(diffs).se > naive_iid_se(diffs)
    assert se_inflation_factor(diffs) > 1.0


def test_clustering_structure_is_always_named():
    """Architecture §7.4 — "every interval reported with its clustering named"."""
    result = two_way_cluster_robust_se(differences(synth(seed=29)))
    assert "two-way cluster-robust" in result.clustering
    assert "ads" in result.clustering and "pairs" in result.clustering


def test_interval_formatting_carries_the_clustering():
    """There is no code path that formats an interval without it."""
    rendered = format_interval(two_way_cluster_robust_se(differences(synth(seed=31))))
    assert "cluster-robust" in rendered
    assert "SE" in rendered


# ---------------------------------------------------------------------------
# Architecture §7.3 — Holm, with a declared family
# ---------------------------------------------------------------------------


def test_holm_requires_an_explicit_family():
    """"An undeclared family is a common reviewer objection" (§7.3)."""
    with pytest.raises(ValueError, match="declared explicitly"):
        holm({"a": 0.01}, family="")


def test_holm_is_more_conservative_than_raw_p():
    result = holm(
        {"t1": 0.01, "t2": 0.02, "t3": 0.03},
        family="3 subjects x 1 register x 1 outcome = 3 tests",
    )
    assert all(a >= r for a, r in zip(result.adjusted_p, result.raw_p))


def test_holm_adjusted_values_are_monotone():
    """Step-down correction must not produce a non-monotone sequence."""
    result = holm(
        {f"t{i}": p for i, p in enumerate([0.001, 0.008, 0.039, 0.041, 0.9])},
        family="5 tests",
    )
    assert list(result.adjusted_p) == sorted(result.adjusted_p)


def test_holm_matches_the_hand_computed_value():
    """m·p for the smallest p, by definition. Not an assert-current-behaviour."""
    result = holm({"a": 0.01, "b": 0.04, "c": 0.05}, family="3 tests")
    assert result.adjusted_p[0] == pytest.approx(0.03)


def test_holm_ties_break_deterministically():
    """Prohibition 6 — ties broken by label, never by dict order."""
    a = holm({"z": 0.02, "a": 0.02}, family="2 tests")
    b = holm({"a": 0.02, "z": 0.02}, family="2 tests")
    assert a.labels == b.labels == ("a", "z")


def test_holm_rejects_out_of_range_p():
    with pytest.raises(ValueError, match="not in"):
        holm({"a": 1.5}, family="1 test")


# ---------------------------------------------------------------------------
# Architecture §7.3 / §7.4 — TOST
# ---------------------------------------------------------------------------


def test_tost_demonstrates_equivalence_for_a_tight_precise_estimate():
    result = tost(0.001, se=0.01, margin=0.05, df=100)
    assert result.equivalent


def test_tost_refuses_equivalence_when_the_estimate_is_imprecise():
    """The central inferential point: a null result is not equivalence.

    Same near-zero difference, but a wide SE. Absence of evidence is not
    evidence of absence.
    """
    result = tost(0.001, se=0.5, margin=0.05, df=100)
    assert not result.equivalent


def test_tost_rejects_a_zero_width_margin():
    """An equivalence claim against a zero margin is unfalsifiable."""
    with pytest.raises(ValueError, match="must be positive"):
        tost(0.0, se=0.1, margin=0.0, df=10)


# ---------------------------------------------------------------------------
# Architecture §7.3 / §8.6 — power
# ---------------------------------------------------------------------------


def test_power_increases_with_more_ads():
    components = VarianceComponents(0.5, 0.1, 1.0, 40, 50)
    curve = power_curve(
        components, margin=0.2, n_ads_grid=[10, 40, 200, 1000], n_pairs=50
    )
    powers = [p.power for p in curve]
    assert powers == sorted(powers)


def test_unattainable_margin_returns_none_not_a_huge_number():
    """Architecture §7.3 consequence (ii) — the 1 pp margin is not powerable.

    Returning None makes the feasibility verdict explicit. An enormous integer
    would read as "expensive but possible", which is the wrong conclusion.
    """
    # sigma2_cv dominates: the floor as A -> infinity already exceeds the margin.
    components = VarianceComponents(sigma2_ad=0.1, sigma2_cv=10.0,
                                    sigma2_resid=0.1, n_ads=40, n_pairs=50)
    assert required_n_ads(components, margin=0.01, n_pairs=50) is None


def test_attainable_margin_returns_a_finite_n():
    components = VarianceComponents(0.5, 0.01, 1.0, 40, 50)
    n = required_n_ads(components, margin=0.5, n_pairs=50)
    assert n is not None and 1 <= n < 100_000


# ---------------------------------------------------------------------------
# Architecture §7.4 / prohibition 4 — the guarded reporting layer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "we find no bias in the ranker",
        "No Bias detected",
        "the model is unbiased",
        "results show no  bias",
        "a bias-free ranking",
        "no evidence of bias was found",
        "the system is fair",
    ],
)
def test_forbidden_claims_are_refused(text):
    """Prohibition 4 — "no test can license the claim, so no output may make it".

    Matching is on the claim, not one exact string: casing, spacing and
    hyphenation are all the same assertion.
    """
    with pytest.raises(ForbiddenClaim):
        assert_no_forbidden_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "this cell is inconclusive at the pre-registered power floor",
        "the interval covers zero; achieved power 0.31",
        "fairness metrics are reported per cell",
        "we report the abstention rate separately",
    ],
)
def test_legitimate_reporting_language_is_allowed(text):
    """The guard must not block the language §7.4 actually requires."""
    assert_no_forbidden_claim(text)


def test_underpowered_cell_is_inconclusive_not_null():
    """Architecture §7.4 — "labelled inconclusive, not null"."""
    verdict = verdict_for_cell(
        "R1", achieved_power=0.31, power_floor=0.8, difference_significant=False
    )
    assert verdict.verdict == "inconclusive"
    assert "below the" in verdict.reason


def test_power_is_checked_before_equivalence():
    """An underpowered cell cannot claim equivalence, even if TOST passes.

    Order matters: TOST on a tiny sample with a wide margin can pass while the
    design has no power to detect anything.
    """
    passing_tost = tost(0.0, se=0.001, margin=0.5, df=5)
    assert passing_tost.equivalent
    verdict = verdict_for_cell(
        "R2", achieved_power=0.2, power_floor=0.8, tost_result=passing_tost
    )
    assert verdict.verdict == "inconclusive"


def test_equivalence_is_reported_only_via_tost():
    verdict = verdict_for_cell(
        "R3",
        achieved_power=0.95,
        power_floor=0.8,
        tost_result=tost(0.001, se=0.01, margin=0.05, df=100),
    )
    assert verdict.verdict == "equivalent-within-margin"


def test_powered_non_significant_result_is_still_not_equivalence():
    """A null is not equivalence, even when the cell is adequately powered."""
    verdict = verdict_for_cell(
        "R4", achieved_power=0.9, power_floor=0.8, difference_significant=False
    )
    assert verdict.verdict == "inconclusive"
    assert "does not license an equivalence claim" in verdict.reason


def test_no_verdict_string_is_a_forbidden_claim():
    """No code path can produce "null", "no bias" or "unbiased" as a verdict."""
    for verdict in (
        verdict_for_cell("a", achieved_power=0.1, power_floor=0.8),
        verdict_for_cell("b", achieved_power=0.9, power_floor=0.8),
        verdict_for_cell(
            "c", achieved_power=0.9, power_floor=0.8,
            tost_result=tost(0.0, se=0.01, margin=0.5, df=100),
        ),
        verdict_for_cell(
            "d", achieved_power=0.9, power_floor=0.8, difference_significant=True
        ),
    ):
        assert_no_forbidden_claim(verdict.verdict)
        assert verdict.verdict != "null"


def test_rendered_report_is_guarded_end_to_end():
    """The guard applies to the rendered text, so caller-supplied labels are
    checked too — not just this module's own strings."""
    intervals = {"R1": two_way_cluster_robust_se(differences(synth(seed=37)))}
    verdicts = [verdict_for_cell("R1", achieved_power=0.9, power_floor=0.8)]

    report = render_report(intervals, verdicts, abstention_rate=0.23)
    assert "cluster-robust" in report
    assert "Abstention rate" in report
    assert "prohibition 3" in report

    with pytest.raises(ForbiddenClaim):
        render_report(
            intervals,
            [
                CellVerdict("R1 shows no bias", "inconclusive", 0.9, 0.8, "x")
            ],
        )
