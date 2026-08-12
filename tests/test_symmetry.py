"""Phase 3 — twin symmetry, Tiers A and B only. **Provisional.**

This is a smoke test, not the invariant. Tier C is unimplemented (Phase 5), so the
cues carrying the paper's phenomenon are absent and only symmetry-in-abstention is
exercised. The binding run is Phase 6, across all tiers.

Assertions trace to fixtures T01/T02, fixture B02's note, or architecture §5.2.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.cues import CandidateAnalysis
from arabgn.analysis.symmetry import (
    check_all_pairs,
    check_twin_symmetry,
    genders_differ,
    shape_of,
)
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.analysis.tiers import classify
from arabgn.contracts import AbstainTrigger, Gender, Referent, Tier
from conftest import of_type, skip_if_review

# Sits inside the feasible region measured in docs/theta-sweep.md
# (θ_high=0.495, θ_low=0.285 is the most robust point over the 9 fixtures).
CFG = ThresholdConfig(theta_high=0.495, theta_low=0.285)

TWIN_FIXTURES = of_type("twin_symmetry")


class _Cue:
    """Minimal cue stand-in: the fields symmetry actually compares."""

    def __init__(self, tier, referent, abstain_reason=None, gen=None, token_index=0):
        self.tier = tier
        self.referent = referent
        self.abstain_reason = abstain_reason
        self.gen = gen
        self.token_index = token_index


# ---------------------------------------------------------------------------
# The comparison itself
# ---------------------------------------------------------------------------


def test_identical_structure_is_symmetric():
    """Same tier, referent and trigger; only gender differs — the target state."""
    f = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F)]
    m = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.M)]
    assert check_twin_symmetry(f, m).symmetric


def test_differing_referent_is_asymmetric():
    """Fixture B02's note — the fatal case.

    "If the tagger abstains on the feminine form but resolves the masculine, the
    instrument is itself gender-asymmetric, which would be fatal to the paper."
    """
    f = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F)]
    m = [_Cue(Tier.A, Referent.APPLICANT, None, Gender.M)]
    report = check_twin_symmetry(f, m)
    assert not report.symmetric
    kinds = {a.kind for a in report.asymmetries}
    assert {"tier", "referent", "abstain_trigger"} <= kinds


def test_differing_cue_count_is_asymmetric():
    """A twin emitting more cues than its partner is already asymmetric."""
    f = [_Cue(Tier.A, Referent.APPLICANT), _Cue(Tier.A, Referent.NON_APPLICANT)]
    m = [_Cue(Tier.A, Referent.APPLICANT)]
    report = check_twin_symmetry(f, m)
    assert not report.symmetric
    assert any(a.kind == "cue_count" for a in report.asymmetries)


def test_differing_abstain_trigger_is_asymmetric():
    """Same label reached by different routes is still an asymmetry.

    Adjudication is stratified by trigger (spec §8.3), so twins abstaining for
    different reasons land in different strata.
    """
    f = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F)]
    m = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB4, Gender.M)]
    report = check_twin_symmetry(f, m)
    assert not report.symmetric
    assert [a.kind for a in report.asymmetries] == ["abstain_trigger"]


def test_gender_is_excluded_from_the_comparison():
    """`gen` is the one field twins are supposed to differ on (fixture T01)."""
    assert "gen" not in shape_of(_Cue(Tier.A, Referent.APPLICANT, gen=Gender.F)).__slots__


# ---------------------------------------------------------------------------
# Architecture §5.2 — what must NOT be asserted
# ---------------------------------------------------------------------------


def test_character_offsets_are_not_compared_by_default():
    """Architecture §5.2 — `حاصلة` is one character longer than `حاصل`.

    Requiring index equality would re-introduce the length constraint §5.2
    rejects as "likely unsatisfiable", which "either blocks all output or forces
    silent padding, which is itself a confound".
    """
    f = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F, token_index=5)]
    m = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.M, token_index=4)]
    assert check_twin_symmetry(f, m).symmetric
    assert not check_twin_symmetry(f, m, compare_index=True).symmetric


def test_no_token_count_assertion_exists():
    """T02's note documents why strict token-count matching is unsatisfiable."""
    import arabgn.analysis.symmetry as module

    source = module.__doc__ or ""
    assert "unsatisfiable" in source
    assert not hasattr(module, "assert_token_count_equal")


# ---------------------------------------------------------------------------
# Fixtures T01 / T02
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", TWIN_FIXTURES, ids=[f["id"] for f in TWIN_FIXTURES]
)
def test_twin_fixture_texts_differ_only_in_gender_morphology(fixture):
    """T01, T02 — the pair must be a real twin, not two unrelated sentences.

    Guards the fixture itself: a "symmetric" result over texts that are not
    actually twins would be vacuous.
    """
    skip_if_review(fixture)
    text_f, text_m = fixture["text_f"], fixture["text_m"]
    assert text_f != text_m
    assert len(text_f) >= len(text_m), (
        "feminine agreement morphology is longer or equal in these pairs"
    )
    # The non-gender lexical content must be shared (architecture §5.2:
    # "zero difference in any non-gender lexical item").
    shared = set(text_f.split()) & set(text_m.split())
    assert len(shared) >= 3, f"only {len(shared)} shared tokens — not a twin pair"


def test_t01_is_settled_and_t02_is_review(get_fixture):
    """Phase 3's real coverage, stated rather than implied.

    T01 is binding. T02 is REVIEW — it depends on Tier C, which is Phase 5 — so
    Phase 3's binding twin coverage is exactly **one** fixture.
    """
    assert get_fixture("T01")["confidence"] == "settled"
    assert get_fixture("T02")["confidence"] == "REVIEW"


# ---------------------------------------------------------------------------
# The property-style sweep — fixture T01's note
# ---------------------------------------------------------------------------


def test_check_all_pairs_reports_every_pair_not_just_the_first():
    """T01: "Run this over every twin pair the generator emits."

    A sweep that stopped at the first failure would hide the rest, and at Phase 8
    the generator emits pairs by the hundred.
    """
    def tagger(text):
        if text == "bad_f":
            return [_Cue(Tier.A, Referent.APPLICANT, None, Gender.F)]
        if text == "bad_m":
            return [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.M)]
        return [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F)]

    reports = check_all_pairs(
        [("ok_f", "ok_m"), ("bad_f", "bad_m"), ("ok_f", "ok_m")],
        tagger,
        labels=["first", "broken", "third"],
    )
    assert len(reports) == 3
    assert [r.symmetric for r in reports] == [True, False, True]
    assert reports[1].label == "broken"


def test_check_all_pairs_rejects_mismatched_labels():
    with pytest.raises(ValueError, match="labels"):
        check_all_pairs([("a", "b")], lambda t: [], labels=["x", "y"])


def test_report_describes_the_asymmetry_actionably():
    """A failing gate must say what differed, or it cannot be acted on."""
    f = [_Cue(Tier.B, Referent.ABSTAIN, AbstainTrigger.AB1, Gender.F)]
    m = [_Cue(Tier.A, Referent.APPLICANT, None, Gender.M)]
    described = check_twin_symmetry(f, m, label="T01").describe()
    assert "ASYMMETRIC" in described
    assert "T01" in described
    assert "referent" in described


# ---------------------------------------------------------------------------
# Guard against a vacuous pass
# ---------------------------------------------------------------------------


def test_genders_differ_detects_a_non_twin():
    """Symmetry over two same-gender inputs proves nothing."""
    same = [_Cue(Tier.A, Referent.APPLICANT, None, Gender.F)]
    assert not genders_differ(same, [_Cue(Tier.A, Referent.APPLICANT, None, Gender.F)])
    assert genders_differ(same, [_Cue(Tier.A, Referent.APPLICANT, None, Gender.M)])


# ---------------------------------------------------------------------------
# End-to-end on the measured masses — T01's `حاصلة` / `حاصل`
# ---------------------------------------------------------------------------


def test_t01_twins_classify_identically_on_measured_mass():
    """T01 — `حاصلة` (r=0.3243) and `حاصل` (r=0.3184), measured 12 Aug 2026.

    Both must reach Tier B / ABSTAIN / AB1. If one resolved and the other
    abstained, the instrument would be gender-asymmetric on the single most
    important lexeme in the fixture set (fixture B02's note).
    """
    def cues(mass_r, mass_i, gen):
        result = classify(
            "حاصل", "noun",
            [CandidateAnalysis(mass_r, "noun", "r", gen, gen, "Nall"),
             CandidateAnalysis(mass_i, "noun", "i", gen, gen, "N/ap")],
            CFG,
        )
        return [_Cue(result.tier, result.referent, result.abstain_reason,
                     Gender(gen))]

    feminine = cues(0.3243, 0.6757, "f")
    masculine = cues(0.3184, 0.6816, "m")

    assert genders_differ(feminine, masculine), "not a real twin pair"
    report = check_twin_symmetry(feminine, masculine, label="T01")
    assert report.symmetric, report.describe()
    assert feminine[0].tier is Tier.B
    assert feminine[0].abstain_reason is AbstainTrigger.AB1
