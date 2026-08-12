"""Cue detection, rationality mass, and Tier A/B classification — pure layer.

No model needed: every test supplies candidate analyses as data. That is the
point of the ADR 007 split.

Assertions trace to spec §2, §3.1, §4.2, §5, §6, or to a fixture id.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.cues import (
    CONTENT_POS,
    EXCLUDED_POS,
    CandidateAnalysis,
    carries_gender,
    dominant_gender,
    form_divergence,
    gender_disagreement,
    is_cue_pos,
    rationality_mass,
)
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.analysis.tiers import TierCNotImplemented, classify
from arabgn.contracts import AbstainTrigger, Gender, Rationality, Referent, Tier

CFG = ThresholdConfig(theta_high=0.70, theta_low=0.30)


def cand(score, rat, pos="noun", gen="f", form_gen="f", stemcat="Nall"):
    return CandidateAnalysis(
        score=score, pos=pos, rat=rat, gen=gen, form_gen=form_gen, stemcat=stemcat
    )


# ---------------------------------------------------------------------------
# Spec §3.1 — POS filtering. Fixtures N01, N02.
# ---------------------------------------------------------------------------


def test_content_pos_classes_match_the_spec():
    """Spec §3.1 — include noun, noun_prop, adj, verb, adj_comp, noun_quant."""
    assert CONTENT_POS == {
        "noun", "noun_prop", "adj", "verb", "adj_comp", "noun_quant"
    }


def test_n01_preposition_is_not_a_cue():
    """N01 `على` — a function word. Returns rat={n, na, r}.

    Spec §3.1: without POS filtering this would flood the abstain queue.
    """
    assert not is_cue_pos("prep")


def test_n02_digit_is_not_a_cue():
    """N02 `2018` — a digit. No gender."""
    assert not is_cue_pos("digit")


def test_excluded_and_content_classes_are_disjoint():
    assert not (CONTENT_POS & EXCLUDED_POS)


def test_pronouns_are_excluded_pending_d6():
    """Spec §3.2 — attached pronouns are genuine cues but currently excluded.

    Register D6 is open: whether the enclitic is a separate cue with its own span
    is an author decision. Excluding them is the documented status quo, not a
    judgement made here.
    """
    assert "pron" in EXCLUDED_POS


def test_gender_na_is_not_a_gender_reading():
    """Spec §3.1 excludes anything with `gen ∈ {na}`."""
    assert carries_gender("f") and carries_gender("m")
    assert not carries_gender("na")
    assert not carries_gender(None)


# ---------------------------------------------------------------------------
# Spec §4.2 — rationality mass. Values measured 12 Aug 2026, ADR 001.
# ---------------------------------------------------------------------------


def test_mass_normalises_over_total_score():
    mass = rationality_mass([cand(3.0, "i"), cand(1.0, "r")])
    assert mass[Rationality.I] == pytest.approx(0.75)
    assert mass[Rationality.R] == pytest.approx(0.25)


def test_mass_ignores_unknown_rationality_values_but_keeps_them_in_the_total():
    """A candidate with `rat=na` still carries score.

    Dropping it from the denominator would inflate the remaining masses and could
    push a genuinely ambiguous cue over θ_high.
    """
    mass = rationality_mass([cand(1.0, "i"), cand(1.0, "na")])
    assert mass[Rationality.I] == pytest.approx(0.5)


def test_mass_of_empty_candidate_set_is_empty():
    """No candidates means no mass — not a fabricated distribution."""
    assert rationality_mass([]) == {}


def test_mass_is_order_independent():
    """Prohibition 6 — candidate order must not change the result."""
    cands = [cand(0.9, "i"), cand(0.5, "r"), cand(0.2, "n")]
    assert rationality_mass(cands) == rationality_mass(list(reversed(cands)))


# ---------------------------------------------------------------------------
# Spec §6 — AB4 and AB5
# ---------------------------------------------------------------------------


def test_ab4_fires_when_candidates_disagree_on_gender():
    assert gender_disagreement([cand(1.0, "r", gen="m"), cand(0.9, "r", gen="f")])


def test_ab4_does_not_fire_on_na_gender():
    """`na` is not a gender reading, so f + na is not gender disagreement."""
    assert not gender_disagreement([cand(1.0, "r", gen="f"), cand(0.9, "r", gen="na")])


def test_ab5_fires_on_form_functional_divergence():
    """Spec §7.4 — `طلبة` is form-feminine, functionally masculine plural."""
    assert form_divergence("m", "f")
    assert not form_divergence("f", "f")


def test_ab5_needs_two_real_gender_values():
    assert not form_divergence("f", "na")
    assert not form_divergence(None, "f")


def test_dominant_gender_breaks_ties_deterministically():
    """Prohibition 6 — a declared tie-break, not sort stability."""
    tied = [cand(1.0, "r", gen="f"), cand(1.0, "r", gen="m")]
    assert dominant_gender(tied) is dominant_gender(list(reversed(tied)))


# ---------------------------------------------------------------------------
# Spec §5 — Tier A/B classification
# ---------------------------------------------------------------------------


def test_a04_irrational_resolves_to_non_applicant():
    """A04 `خبرة` — i = 0.904 measured. "THE canonical negative case"."""
    result = classify("خبرة", "noun", [cand(0.904, "i"), cand(0.096, "r")], CFG)
    assert result.tier is Tier.A
    assert result.referent is Referent.NON_APPLICANT
    assert result.abstain_reason is None


def test_a01_rational_passing_the_role_test_is_applicant():
    """A01 `المرشحة` — r = 0.747 measured. "Cleanest positive case"."""
    result = classify(
        "المرشحة", "noun", [cand(0.747, "r"), cand(0.253, "i")], CFG,
        role_test_passes=True,
    )
    assert result.tier is Tier.A
    assert result.referent is Referent.APPLICANT


def test_b01_ambiguous_abstains_under_ab1():
    """B01 `حاصلة` — i = 0.676, r = 0.324. The case AB1 exists for (spec §5)."""
    result = classify("حاصلة", "noun", [cand(0.676, "i"), cand(0.324, "r")], CFG)
    assert result.tier is Tier.B
    assert result.referent is Referent.ABSTAIN
    assert result.abstain_reason is AbstainTrigger.AB1


def test_rational_with_indeterminate_role_test_abstains_under_ab6():
    """Spec §6 AB6 — a rational cue whose role test is indeterminate abstains.

    Spec §5.1: rational ≠ applicant. Defaulting to `applicant` here would count
    every hiring manager and client as the applicant.
    """
    result = classify(
        "المدير", "noun", [cand(0.95, "r"), cand(0.05, "i")], CFG,
        role_test_passes=None,
    )
    assert result.referent is Referent.ABSTAIN
    assert result.abstain_reason is AbstainTrigger.AB6
    assert result.tier is Tier.A


def test_rational_failing_the_role_test_is_non_applicant():
    """Spec §5.1 — `المدير` in "works under the supervision of the director"."""
    result = classify(
        "المدير", "noun", [cand(0.95, "r"), cand(0.05, "i")], CFG,
        role_test_passes=False,
    )
    assert result.referent is Referent.NON_APPLICANT


def test_ab4_takes_precedence_over_the_rationality_rule():
    """A cue whose gender is in doubt cannot have a trustworthy referent."""
    result = classify(
        "x", "noun",
        [cand(0.9, "i", gen="m"), cand(0.9, "i", gen="f")], CFG,
    )
    assert result.abstain_reason is AbstainTrigger.AB4


def test_ab5_fires_before_resolution():
    result = classify(
        "طلبة", "noun", [cand(1.0, "i")], CFG, gen="m", form_gen="f"
    )
    assert result.abstain_reason is AbstainTrigger.AB5


def test_tier_is_always_recorded():
    """Architecture §8.1 requires tier-wise metrics; tier is never re-inferred."""
    for cands, kwargs in (
        ([cand(1.0, "i")], {}),
        ([cand(0.5, "i"), cand(0.5, "r")], {}),
        ([cand(1.0, "r")], {"role_test_passes": True}),
    ):
        assert classify("x", "noun", cands, CFG, **kwargs).tier in (Tier.A, Tier.B)


def test_mass_is_carried_on_every_classification():
    """Prohibition 3 — an abstention must be explicable, not just counted."""
    result = classify("حاصلة", "noun", [cand(0.676, "i"), cand(0.324, "r")], CFG)
    assert result.mass[Rationality.R] == pytest.approx(0.324, abs=1e-3)


# ---------------------------------------------------------------------------
# Tier C is deliberately absent — Phase 5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pos", ["verb", "adj", "adj_comp"])
def test_tier_c_raises_naming_cue_and_pos(pos):
    """Tier C is Phase 5, blocked on D7 and D8. It must fail loudly, not guess."""
    with pytest.raises(TierCNotImplemented) as exc:
        classify("تخرجت", pos, [cand(1.0, "n")], CFG)
    assert "تخرجت" in str(exc.value)
    assert pos in str(exc.value)
    assert "D7" in str(exc.value) and "D8" in str(exc.value)


def test_hasila_does_not_route_to_tier_c():
    """Register D2 probe correction.

    An earlier reading predicted `حاصلة` would tag `adj` and collide with B01/B02.
    The verified analysis is `pos=noun` (`stemcat` N/ap vs Nall), so it routes to
    Tier B as the fixtures expect.
    """
    result = classify("حاصلة", "noun", [cand(0.676, "i"), cand(0.324, "r")], CFG)
    assert result.tier is Tier.B
