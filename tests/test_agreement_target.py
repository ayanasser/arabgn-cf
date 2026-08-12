"""Tier C agreement-target identification, adjective branch. Spec §5.

Driven by the settled Tier C fixtures C01, C02 and C03 — all adjective cases.
C04 is REVIEW (attachment ambiguity) and C05–C07 are REVIEW (pro-drop, D8).
"""

from __future__ import annotations

import pytest

from arabgn.analysis.agreement_target import (
    TargetCandidate,
    VerbBranchNotImplemented,
    find_agreement_target,
)
from arabgn.contracts import AbstainTrigger
from conftest import skip_if_review


def tok(index, token, pos, gen=None):
    return TargetCandidate(index=index, token=token, pos=pos, gen=gen)


# ---------------------------------------------------------------------------
# Settled fixtures C01, C02, C03
# ---------------------------------------------------------------------------


def test_c01_wasia_attaches_to_khibra(get_fixture):
    """C01 `خبرة واسعة` — "the other half of the paper's canonical example".

    Feminine adjective, `rat=n`, target `خبرة` (`rat=i`) → inherits
    non_applicant. Guards against the naive "feminine adjective = female
    applicant" error.
    """
    fixture = get_fixture("C01")
    skip_if_review(fixture)

    # مطلوب مهندس برمجيات لديه خبرة واسعة في تطوير التطبيقات
    tokens = [
        tok(0, "مطلوب", "adj", "m"),
        tok(1, "مهندس", "noun", "m"),
        tok(2, "برمجيات", "noun", "f"),
        tok(3, "لديه", "prep", None),
        tok(4, "خبرة", "noun", "f"),
        tok(5, "واسعة", "adj", "f"),
    ]
    result = find_agreement_target(5, "adj", "f", tokens)
    assert result.resolved
    assert result.target.token == "خبرة"


def test_c02_kabira_attaches_to_sharika(get_fixture):
    """C02 `شركة كبيرة` — adjective, target `شركة` (`rat=i`)."""
    fixture = get_fixture("C02")
    skip_if_review(fixture)

    tokens = [
        tok(0, "بيئة", "noun", "f"),
        tok(1, "عمل", "noun", "m"),
        tok(2, "شركة", "noun", "f"),
        tok(3, "كبيرة", "adj", "f"),
    ]
    result = find_agreement_target(3, "adj", "f", tokens)
    assert result.resolved
    assert result.target.token == "شركة"


def test_c03_mithaliya_attaches_to_murashaha(get_fixture):
    """C03 `المرشحة المثالية` — target `المرشحة` (`rat=r`) → applicant.

    "Pairs with C01 to show inheritance works in both directions."
    """
    fixture = get_fixture("C03")
    skip_if_review(fixture)

    tokens = [
        tok(0, "المرشحة", "noun", "f"),
        tok(1, "المثالية", "adj", "f"),
    ]
    result = find_agreement_target(1, "adj", "f", tokens)
    assert result.resolved
    assert result.target.token == "المرشحة"


# ---------------------------------------------------------------------------
# C04 — the attachment ambiguity, which must abstain rather than guess
# ---------------------------------------------------------------------------


def test_c04_competing_heads_abstain_under_ab2(get_fixture):
    """C04 `مهارات تواصل ممتازة` — does `ممتازة` attach to `مهارات` or `تواصل`?

    The fixture is REVIEW for exactly this reason. Both candidates are feminine,
    so agreement cannot separate them and no parser is available. Abstaining is
    the honest outcome; picking one would silently settle an open question.
    """
    tokens = [
        tok(0, "بمهارات", "noun", "f"),
        tok(1, "تواصل", "noun", "f"),
        tok(2, "ممتازة", "adj", "f"),
    ]
    result = find_agreement_target(2, "adj", "f", tokens)
    assert not result.resolved
    assert result.abstain_reason is AbstainTrigger.AB2
    assert len(result.ambiguous_between) == 2
    assert "abstains rather than guessing" in result.reason


# ---------------------------------------------------------------------------
# Adjacency: what it can and cannot do
# ---------------------------------------------------------------------------


def test_coordination_is_skipped():
    """`خبرة واسعة وعميقة` — the second adjective's head is two back."""
    tokens = [
        tok(0, "خبرة", "noun", "f"),
        tok(1, "واسعة", "adj", "f"),
        tok(2, "و", "conj", None),
        tok(3, "عميقة", "adj", "f"),
    ]
    result = find_agreement_target(3, "adj", "f", tokens)
    assert result.resolved and result.target.token == "خبرة"


def test_gender_disagreement_blocks_attachment():
    """A non-agreeing nominal stands between the adjective and any earlier head.

    Arabic agreement does not reach past it, so this abstains rather than
    searching further back and inventing an attachment.
    """
    tokens = [
        tok(0, "خبرة", "noun", "f"),
        tok(1, "مهندس", "noun", "m"),
        tok(2, "واسعة", "adj", "f"),
    ]
    result = find_agreement_target(2, "adj", "f", tokens)
    assert not result.resolved
    assert result.abstain_reason is AbstainTrigger.AB2
    assert "does not agree in gender" in result.reason


def test_sentence_initial_adjective_abstains():
    """MSA attributive adjectives follow their head; there is nothing before."""
    result = find_agreement_target(0, "adj", "f", [tok(0, "ممتازة", "adj", "f")])
    assert result.abstain_reason is AbstainTrigger.AB2
    assert "sentence-initial" in result.reason


def test_non_skippable_token_blocks_the_search():
    """Only conjunctions, adjectives and punctuation may be looked past."""
    tokens = [
        tok(0, "خبرة", "noun", "f"),
        tok(1, "في", "prep", None),
        tok(2, "واسعة", "adj", "f"),
    ]
    result = find_agreement_target(2, "adj", "f", tokens)
    assert not result.resolved
    assert "search blocked" in result.reason


# ---------------------------------------------------------------------------
# The verb branch is deliberately absent — register D8
# ---------------------------------------------------------------------------


def test_verb_branch_raises_naming_d8():
    """Spec §5.2 — pro-drop. `تخرجت من جامعة القاهرة` has no overt subject.

    Fixtures C05, C06 and C07 all depend on the default and are all REVIEW.
    """
    with pytest.raises(VerbBranchNotImplemented) as exc:
        find_agreement_target(0, "verb", "f", [tok(0, "تخرجت", "verb", "f")])
    assert "D8" in str(exc.value)
    assert "pro-dropped" in str(exc.value)


def test_nominal_cue_is_rejected_as_a_category_error():
    """Nominal cues resolve lexically in Tier A/B, not by agreement."""
    with pytest.raises(ValueError, match="adjective branch"):
        find_agreement_target(1, "noun", "f", [tok(0, "خبرة", "noun", "f")])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolution_is_deterministic():
    """Prohibition 6 — same tokens, same target, every time."""
    tokens = [tok(0, "شركة", "noun", "f"), tok(1, "كبيرة", "adj", "f")]
    a = find_agreement_target(1, "adj", "f", tokens)
    b = find_agreement_target(1, "adj", "f", tokens)
    assert a.target.token == b.target.token and a.reason == b.reason
