"""Tier C — inheritance by agreement. Spec §5, adjective branch.

Assertions come from settled fixtures C01/C02/C08 and from spec §5's four-step
procedure, never from what the code returns today.

Why the adjective branch could be wired while D7 and D8 are still open: the role
test applies only to *rational* targets (spec §5.1). A cue whose target is
irrational — ``خبرة واسعة`` — inherits ``non_applicant`` with no author decision
involved, and that is the majority case in real advertisements.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.agreement_target import (
    TargetCandidate,
    VerbBranchNotImplemented,
)
from arabgn.analysis.cues import CandidateAnalysis
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.analysis.tiers import TierCNotImplemented, classify
from arabgn.contracts import AbstainTrigger, Rationality, Referent, Tier

# docs/theta-sweep.md §3 — the most robust point over the nine fixtures.
CFG = ThresholdConfig(theta_high=0.495, theta_low=0.285)


def cand(score, rat, *, pos="noun", gen="f", form_gen="f"):
    return CandidateAnalysis(
        score=score, pos=pos, rat=rat, gen=gen, form_gen=form_gen, stemcat="N/ap"
    )


def target(index, token, pos, gen, candidates=()):
    return TargetCandidate(
        index=index, token=token, pos=pos, gen=gen, candidates=tuple(candidates)
    )


#: `خبرة` — rat=i at 0.90, comfortably irrational under CFG.
IRRATIONAL = (cand(0.90, "i"), cand(0.10, "r"))
#: `المرشحة` — rat=r at 0.75, comfortably rational under CFG.
RATIONAL = (cand(0.75, "r"), cand(0.25, "i"))
#: `حاصلة` — 0.324 / 0.676, the canonical unresolvable case (ADR 001).
UNRESOLVED = (cand(0.324, "r"), cand(0.676, "i"))

#: An adjective carries gender by agreement, so `rat = n` and its own mass is
#: uninformative. That is the whole reason Tier C exists.
ADJECTIVE = (cand(1.0, "n", pos="adj"),)


# ---------------------------------------------------------------------------
# C01 / C02 — settled fixtures, satisfiable today
# ---------------------------------------------------------------------------


def test_c01_wasia_inherits_non_applicant_from_khibra():
    """C01, settled: مطلوب مهندس برمجيات لديه خبرة واسعة في تطوير التطبيقات

    "Guards against the naive 'feminine adjective = female applicant' error."
    واسعة is feminine and refers to the experience, not the engineer.
    """
    tokens = [
        target(0, "خبرة", "noun", "f", IRRATIONAL),
        target(1, "واسعة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "واسعة", "adj", ADJECTIVE, CFG, gen="f", form_gen="f",
        cue_index=1, tokens=tokens,
    )
    assert result.referent is Referent.NON_APPLICANT
    assert result.tier is Tier.C
    assert result.head_token == "خبرة"
    assert result.abstain_reason is None


def test_c02_kabira_inherits_non_applicant_from_sharika():
    """C02, settled: ... في بيئة عمل شركة كبيرة — target شركة (rat=i)."""
    tokens = [
        target(0, "شركة", "noun", "f", IRRATIONAL),
        target(1, "كبيرة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "كبيرة", "adj", ADJECTIVE, CFG, gen="f", form_gen="f",
        cue_index=1, tokens=tokens,
    )
    assert result.referent is Referent.NON_APPLICANT
    assert result.head_token == "شركة"


def test_an_irrational_target_needs_no_author_decision():
    """The point of wiring this branch now.

    D7 governs the role test, which applies only to rational cues (spec §5.1).
    Inheritance from an irrational target is fully determined by the spec, so it
    resolves rather than abstaining — with `role_test_passes` left unset.
    """
    tokens = [
        target(0, "خبرة", "noun", "f", IRRATIONAL),
        target(1, "واسعة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "واسعة", "adj", ADJECTIVE, CFG, gen="f",
        cue_index=1, tokens=tokens, role_test_passes=None,
    )
    assert result.referent is Referent.NON_APPLICANT
    assert result.rationality is Rationality.I


# ---------------------------------------------------------------------------
# C03 — settled, but not satisfiable until D7 closes
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "C03 is a settled fixture expecting `applicant`, and reaching it needs "
        "the role test to pass on the rational target المرشحة. The role test and "
        "its closed list are register D7, still open, so the cue abstains under "
        "AB6 instead. strict=True so this reports a FAILURE the moment D7 is "
        "settled and the fixture starts passing."
    ),
)
def test_c03_almithaliyya_inherits_applicant_from_almurashaha():
    """C03, settled: المرشحة المثالية تتمتع بمهارات تواصل ممتازة

    "Pairs with C01 to show inheritance works in both directions." The direction
    C01 does not cover is exactly the one D7 gates.
    """
    tokens = [
        target(0, "المرشحة", "noun", "f", RATIONAL),
        target(1, "المثالية", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "المثالية", "adj", ADJECTIVE, CFG, gen="f",
        cue_index=1, tokens=tokens,
    )
    assert result.referent is Referent.APPLICANT


def test_a_rational_target_abstains_under_ab6_while_d7_is_open():
    """The behaviour C03 currently gets, asserted positively.

    An unsettled role test is AB6 — "role test indeterminate" — never a default
    to applicant. Tier A already behaves this way; Tier C inherits the treatment
    rather than inventing its own.
    """
    tokens = [
        target(0, "المرشحة", "noun", "f", RATIONAL),
        target(1, "المثالية", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "المثالية", "adj", ADJECTIVE, CFG, gen="f", cue_index=1, tokens=tokens,
    )
    assert result.referent is Referent.ABSTAIN
    assert result.abstain_reason is AbstainTrigger.AB6
    assert result.tier is Tier.C
    assert result.head_token == "المرشحة"


def test_a_settled_role_test_resolves_a_rational_target():
    """When D7 closes, the caller supplies the verdict and inheritance completes.

    This is what C03 will exercise; the machinery is present and only the closed
    list is missing.
    """
    tokens = [
        target(0, "المرشحة", "noun", "f", RATIONAL),
        target(1, "المثالية", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "المثالية", "adj", ADJECTIVE, CFG, gen="f",
        cue_index=1, tokens=tokens, role_test_passes=True,
    )
    assert result.referent is Referent.APPLICANT
    assert result.head_token == "المرشحة"


# ---------------------------------------------------------------------------
# Spec §5 step 4 — abstain routes
# ---------------------------------------------------------------------------


def test_no_recoverable_target_abstains_under_ab2():
    """Spec §6 AB2 — "agreement target not identifiable"."""
    tokens = [target(0, "ممتازة", "adj", "f", ADJECTIVE)]
    result = classify(
        "ممتازة", "adj", ADJECTIVE, CFG, gen="f", cue_index=0, tokens=tokens,
    )
    assert result.referent is Referent.ABSTAIN
    assert result.abstain_reason is AbstainTrigger.AB2
    assert result.tier is Tier.C
    assert result.head_token is None


def test_a_target_that_itself_abstains_gives_ab3():
    """Spec §6 AB3 — "agreement target itself abstains".

    ``حاصلة`` as a head: 0.324 / 0.676 resolves to neither under CFG, so nothing
    can be inherited. Distinct from AB2, where no head was found at all.
    """
    tokens = [
        target(0, "حاصلة", "noun", "f", UNRESOLVED),
        target(1, "ممتازة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "ممتازة", "adj", ADJECTIVE, CFG, gen="f", cue_index=1, tokens=tokens,
    )
    assert result.abstain_reason is AbstainTrigger.AB3
    assert result.head_token == "حاصلة"


def test_a_target_with_no_analyses_gives_ab3_not_an_assumption():
    """An unanalysable head is unresolved, not irrational."""
    tokens = [
        target(0, "خبرة", "noun", "f", ()),
        target(1, "واسعة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "واسعة", "adj", ADJECTIVE, CFG, gen="f", cue_index=1, tokens=tokens,
    )
    assert result.abstain_reason is AbstainTrigger.AB3
    assert result.referent is Referent.ABSTAIN


def test_two_competing_heads_abstain_rather_than_guess():
    """Fixture C04's situation: مهارات تواصل ممتازة.

    Both candidate heads are feminine, so agreement cannot separate them and no
    parser is available. C04 is REVIEW for exactly this reason.
    """
    tokens = [
        target(0, "مهارات", "noun", "f", IRRATIONAL),
        target(1, "تواصل", "noun", "f", IRRATIONAL),
        target(2, "ممتازة", "adj", "f", ADJECTIVE),
    ]
    result = classify(
        "ممتازة", "adj", ADJECTIVE, CFG, gen="f", cue_index=2, tokens=tokens,
    )
    assert result.abstain_reason is AbstainTrigger.AB2


# ---------------------------------------------------------------------------
# What stays blocked
# ---------------------------------------------------------------------------


def test_verbs_still_raise_because_d8_is_open():
    """Spec §5.2 pro-drop. C05/C06/C07 all depend on it and are all REVIEW."""
    tokens = [target(0, "تخرجت", "verb", "f", ADJECTIVE)]
    with pytest.raises(VerbBranchNotImplemented) as exc:
        classify(
            "تخرجت", "verb", (cand(1.0, "n", pos="verb"),), CFG, gen="f",
            cue_index=0, tokens=tokens,
        )
    assert "D8" in str(exc.value)


def test_tier_c_without_sentence_context_raises():
    """Tier C resolves by agreement, so the cue alone is not enough to decide.

    Failing loudly beats silently treating a context-free adjective as
    unresolvable, which would look like a legitimate AB2.
    """
    with pytest.raises(TierCNotImplemented) as exc:
        classify("واسعة", "adj", ADJECTIVE, CFG, gen="f")
    assert "واسعة" in str(exc.value)
    assert "cue_index" in str(exc.value)


# ---------------------------------------------------------------------------
# Tier is a property of the cue, not of the trigger that stopped it (ADR 002)
# ---------------------------------------------------------------------------


def test_an_adjective_abstaining_on_gender_is_tier_c_not_tier_b():
    """AB4 fires for "any" tier (spec §6), and tier tracks the *mechanism* the
    cue would have used to resolve.

    Recording an adjective as Tier B because AB4 fired would corrupt architecture
    §8.1's tier-wise breakdown — the metric would attribute Tier C's cues to
    Tier B whenever their gender was in doubt.
    """
    disagreeing = (
        cand(0.6, "n", pos="adj", gen="f"),
        cand(0.4, "n", pos="adj", gen="m"),
    )
    result = classify("ممتازة", "adj", disagreeing, CFG, gen="f", form_gen="f")
    assert result.abstain_reason is AbstainTrigger.AB4
    assert result.tier is Tier.C


def test_a_nominal_abstaining_on_gender_is_still_tier_b():
    """The converse, so the change above cannot silently reclassify Tier B."""
    disagreeing = (cand(0.6, "i", gen="f"), cand(0.4, "i", gen="m"))
    result = classify("خبرة", "noun", disagreeing, CFG, gen="f", form_gen="f")
    assert result.abstain_reason is AbstainTrigger.AB4
    assert result.tier is Tier.B
