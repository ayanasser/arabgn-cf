"""Rationality resolution and the θ separability gate.

Every case below uses the masses **measured 12 August 2026** and recorded in
ADR 001 / spec §4.2.1. None asserts current behaviour — the expected outcomes come
from the fixtures those tokens belong to (A04, A01, B01).
"""

from __future__ import annotations

import pytest

from arabgn.analysis.thresholds import (
    SeparabilityCase,
    ThresholdConfig,
    resolve_rationality,
    sweep_feasible_region,
)
from arabgn.contracts import Rationality

# Masses measured against calima-msa-r13, recorded in ADR 001.
MASS_KHIBRA = {Rationality.I: 0.904, Rationality.R: 0.096}      # خبرة   — A04
MASS_MURASHAHA = {Rationality.R: 0.747, Rationality.I: 0.254}   # المرشحة — A01
MASS_HASILA_AD = {Rationality.I: 0.676, Rationality.R: 0.324}   # حاصلة  — B01, ad
MASS_HASILA_CV = {Rationality.I: 0.670, Rationality.R: 0.330}   # حاصلة  — B01, cv


# ---------------------------------------------------------------------------
# Spec §4.2 — θ is never defaulted
# ---------------------------------------------------------------------------


def test_thresholds_have_no_defaults():
    """Spec §4.2 — θ is calibrated at Phase 4 and frozen; it must not be guessed.

    A silently-defaulted θ would become a pre-registered constant nobody chose.
    """
    with pytest.raises(TypeError):
        ThresholdConfig()  # type: ignore[call-arg]


def test_thresholds_reject_out_of_range_values():
    with pytest.raises(ValueError, match="probability mass"):
        ThresholdConfig(theta_high=1.5, theta_low=0.3)


def test_theta_low_above_theta_high_is_rejected():
    """The rule needs a dominant mass above θ_high and a competitor below θ_low."""
    with pytest.raises(ValueError, match="theta_low.*theta_high"):
        ThresholdConfig(theta_high=0.3, theta_low=0.7)


# ---------------------------------------------------------------------------
# Spec §4.2 — the rule, on measured masses
# ---------------------------------------------------------------------------


def test_a04_khibra_resolves_irrational():
    """A04 `خبرة` — i = 0.904. "THE canonical negative case" (fixture note)."""
    cfg = ThresholdConfig(theta_high=0.70, theta_low=0.30)
    outcome = resolve_rationality(MASS_KHIBRA, cfg)
    assert outcome.value is Rationality.I
    assert not outcome.abstains


def test_a01_murashaha_resolves_rational():
    """A01 `المرشحة` — r = 0.747. "Cleanest positive case" (fixture note)."""
    cfg = ThresholdConfig(theta_high=0.70, theta_low=0.30)
    outcome = resolve_rationality(MASS_MURASHAHA, cfg)
    assert outcome.value is Rationality.R
    assert not outcome.abstains


def test_b01_hasila_abstains_in_both_contexts():
    """B01 `حاصلة` — neither mass dominant. The case AB1 exists for (spec §5).

    ADR 001 §4.2.2: the split is lexical (`N/ap` "income" vs `Nall` "holder"), so
    both readings are licensed in both contexts and abstention is correct.
    """
    cfg = ThresholdConfig(theta_high=0.70, theta_low=0.30)
    for mass in (MASS_HASILA_AD, MASS_HASILA_CV):
        outcome = resolve_rationality(mass, cfg)
        assert outcome.abstains
        assert outcome.value is None


def test_missing_mass_is_treated_as_zero():
    cfg = ThresholdConfig(theta_high=0.70, theta_low=0.30)
    assert resolve_rationality({Rationality.R: 0.9}, cfg).value is Rationality.R


# ---------------------------------------------------------------------------
# Spec §4.2.1 / ADR 001 — the joint separability gate
# ---------------------------------------------------------------------------

CASES = (
    SeparabilityCase("A04 خبرة", mass_r=0.096, mass_i=0.904, expected=Rationality.I),
    SeparabilityCase("A01 المرشحة", mass_r=0.747, mass_i=0.254, expected=Rationality.R),
    SeparabilityCase("B01 حاصلة ad", mass_r=0.324, mass_i=0.676, expected=None),
    SeparabilityCase("B01 حاصلة cv", mass_r=0.330, mass_i=0.670, expected=None),
)

GRID = tuple(i / 1000 for i in range(0, 1001, 5))


def test_a_feasible_region_exists_on_the_measured_masses():
    """ADR 001 — the four measured cases are separable. If this fails, AB1 is
    unimplementable as specified and must be redesigned, not tuned."""
    report = sweep_feasible_region(CASES, grid=GRID)
    assert report.separable, (
        f"no feasible θ on the measured masses; failures: {report.failures_by_case}"
    )


def test_the_feasible_region_matches_the_disjunction_derived_in_adr_001():
    """ADR 001 derives two independent routes::

        θ_high ∈ (0.676, 0.747]   OR   θ_low ∈ (0.254, 0.324]

    Every feasible point must satisfy at least one. This is the assertion that
    makes the joint sweep necessary rather than merely tidy.
    """
    report = sweep_feasible_region(CASES, grid=GRID)
    for theta_high, theta_low in report.feasible:
        assert (0.676 < theta_high <= 0.747) or (0.254 < theta_low <= 0.324), (
            f"({theta_high}, {theta_low}) is feasible but satisfies neither "
            f"route derived in ADR 001"
        )


def test_both_routes_are_actually_reachable():
    """Both disjuncts must be non-empty on the grid.

    If only one were reachable, a θ_high-only sweep would be adequate and ADR
    001's warning would be moot. This asserts the warning is live.
    """
    report = sweep_feasible_region(CASES, grid=GRID)
    via_high = [p for p in report.feasible if 0.676 < p[0] <= 0.747]
    via_low = [p for p in report.feasible if 0.254 < p[1] <= 0.324]
    assert via_high, "no feasible point via the θ_high route"
    assert via_low, "no feasible point via the θ_low route"


def test_a_theta_high_only_sweep_would_miss_feasible_points():
    """The concrete failure ADR 001 warns about.

    Fixing θ_low at a value outside (0.254, 0.324] and sweeping θ_high alone finds
    a strictly smaller region than the joint sweep — so a θ_high-only gate can
    report "no feasible θ" while valid configurations exist.
    """
    joint = set(sweep_feasible_region(CASES, grid=GRID).feasible)
    via_low_only = {p for p in joint if not (0.676 < p[0] <= 0.747)}
    assert via_low_only, (
        "expected feasible points reachable only via the θ_low route; "
        "without them the joint-sweep requirement would be unfalsifiable"
    )


def test_an_unseparable_case_set_reports_no_feasible_region():
    """The gate must be able to fail — otherwise it licenses nothing.

    Two cues with near-identical masses but opposite required outcomes cannot be
    separated by any threshold pair.
    """
    contradictory = (
        SeparabilityCase("x", mass_r=0.5, mass_i=0.5, expected=Rationality.R),
        SeparabilityCase("y", mass_r=0.5, mass_i=0.5, expected=Rationality.I),
    )
    report = sweep_feasible_region(contradictory, grid=GRID)
    assert not report.separable
    assert report.theta_high_range is None


def test_sweep_is_deterministic():
    """Prohibition 6 — same inputs, byte-identical region, in the same order."""
    a = sweep_feasible_region(CASES, grid=GRID)
    b = sweep_feasible_region(CASES, grid=GRID)
    assert a.feasible == b.feasible


def test_sweep_reports_per_case_failures():
    """A failing gate must say which case failed, or it cannot be acted on."""
    report = sweep_feasible_region(CASES, grid=GRID)
    assert set(report.failures_by_case) == {c.label for c in CASES}
