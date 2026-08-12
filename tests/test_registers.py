"""Five-register typology invariants. Architecture §5.1.

Assertions derive from §5.1's invariant table. The load-bearing test is
``test_r3_cannot_be_certified_while_cues_abstain``: R3 is the register whose whole
purpose is certifying an absence, and the naive count-the-applicant-cues reading
would certify anything while register D7 is open.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.registers import (
    Register,
    RegisterDocument,
    check_r1,
    check_r2,
    check_r3,
    check_r4,
    check_r5,
)
from arabgn.analysis.twins import TwinToken
from arabgn.contracts import (
    AbstainTrigger,
    Gender,
    Rationality,
    Referent,
    TaggedCue,
    Tier,
)


def cue(
    token,
    *,
    referent=Referent.APPLICANT,
    gen=Gender.M,
    tier=Tier.A,
    abstain=None,
    sentence=None,
):
    sentence = sentence if sentence is not None else token
    return TaggedCue(
        cue_id=f"c-{token}",
        doc_id="d1",
        token=token,
        char_span=(0, len(token)),
        sentence_context=sentence,
        pos="noun",
        morph_class="N/ap",
        gen=gen,
        form_gen=gen,
        rat_candidates=frozenset({Rationality.R}),
        tier=tier,
        referent=referent,
        abstain_reason=abstain,
        head_token=None,
        toolkit_version="1.6.0",
        db_version="calima-msa-r13",
    )


def document(text, cues=(), tokens=()):
    return RegisterDocument(
        text=text,
        cues=tuple(cues),
        tokens=tuple(TwinToken(surface=s, pos=p) for s, p in tokens),
    )


# ---------------------------------------------------------------------------
# R1 — as-found generic masculine
# ---------------------------------------------------------------------------


def test_r1_requires_an_applicant_referring_masculine_cue():
    """§5.1 — "Contains ≥1 applicant-referring masculine cue"."""
    report = check_r1(document("مطلوب مهندس", [cue("مطلوب", gen=Gender.M)]))
    assert report.satisfied
    assert report.register is Register.R1


def test_r1_fails_when_the_only_applicant_cue_is_feminine():
    report = check_r1(document("مطلوبة مهندسة", [cue("مطلوبة", gen=Gender.F)]))
    assert not report.satisfied
    assert "no applicant-referring masculine cue" in report.explain()


def test_r1_ignores_masculine_cues_that_are_not_applicant_referring():
    """Rational ≠ applicant (spec §5.1). A masculine cue about the hiring manager
    does not make an advertisement generic-masculine *about the applicant*."""
    report = check_r1(
        document(
            "يعمل تحت إشراف المدير التنفيذي",
            [cue("المدير", referent=Referent.NON_APPLICANT, gen=Gender.M)],
        )
    )
    assert not report.satisfied


# ---------------------------------------------------------------------------
# R2 — dual / inclusive
# ---------------------------------------------------------------------------

PAIR = ("مطلوب", "مطلوبة")


def test_r2_holds_when_both_gendered_forms_are_present():
    """§5.1 — "Both gendered forms present for each applicant cue"."""
    report = check_r2(
        document("مطلوب / مطلوبة مهندس برمجيات", [cue("مطلوب", gen=Gender.M)]),
        declared_inclusive_pairs=frozenset({PAIR}),
    )
    assert report.satisfied, report.explain()


def test_r2_fails_when_the_counterpart_is_missing_from_the_text():
    report = check_r2(
        document("مطلوب مهندس برمجيات", [cue("مطلوب", gen=Gender.M)]),
        declared_inclusive_pairs=frozenset({PAIR}),
    )
    assert not report.satisfied
    assert "absent from the text" in report.explain()


def test_r2_fails_on_a_bare_gendered_form():
    """An applicant cue belonging to no declared pair is exactly what R2 forbids."""
    report = check_r2(
        document("مطلوب مهندس حاصل على بكالوريوس", [cue("حاصل", gen=Gender.M)]),
        declared_inclusive_pairs=frozenset({PAIR}),
    )
    assert not report.satisfied
    assert "bare gendered form" in report.explain()


def test_r2_does_not_infer_pairs_morphologically():
    """The generator declares its alternations; this module never guesses.

    An inferred rule would be an unreviewed linguistic decision inside the freeze.
    """
    report = check_r2(
        document("مطلوب / مطلوبة مهندس", [cue("مطلوب", gen=Gender.M)]),
        declared_inclusive_pairs=frozenset(),
    )
    assert not report.satisfied


# ---------------------------------------------------------------------------
# R3 — agreement-free. The register that must not certify vacuously.
# ---------------------------------------------------------------------------


def test_r3_holds_when_no_cue_refers_to_the_applicant_and_none_abstain():
    report = check_r3(
        document(
            "خبرة واسعة في التطوير",
            [cue("خبرة", referent=Referent.NON_APPLICANT, gen=Gender.F)],
        )
    )
    assert report.satisfied
    assert report.certifiable


def test_r3_fails_when_an_applicant_cue_is_present():
    report = check_r3(document("مطلوبة مهندسة", [cue("مطلوبة", gen=Gender.F)]))
    assert not report.satisfied
    assert report.certifiable


def test_r3_cannot_be_certified_while_cues_abstain():
    """An abstention is "unresolved", never "not applicant" (prohibition 3).

    Counting abstentions as absence would let an advertisement full of
    unresolved gender marking be certified agreement-free. Three outcomes are
    needed, not two, and this is the third.
    """
    report = check_r3(
        document(
            "حاصلة على بكالوريوس هندسة",
            [
                cue(
                    "حاصلة",
                    referent=Referent.ABSTAIN,
                    gen=Gender.F,
                    tier=Tier.B,
                    abstain=AbstainTrigger.AB1,
                )
            ],
        )
    )
    assert not report.satisfied
    assert not report.certifiable
    assert "NOT CERTIFIABLE" in report.explain()


def test_r3_is_uncertifiable_for_every_document_while_d7_is_open():
    """The consequence stated in the module docstring, asserted.

    With the role test indeterminate, every rational cue abstains under AB6. So a
    document that would otherwise certify cleanly does not — which is the honest
    outcome, and the reason R3 is not yet usable.
    """
    report = check_r3(
        document(
            "المرشحة المثالية",
            [
                cue(
                    "المرشحة",
                    referent=Referent.ABSTAIN,
                    gen=Gender.F,
                    abstain=AbstainTrigger.AB6,
                )
            ],
        )
    )
    assert not report.certifiable


# ---------------------------------------------------------------------------
# R4 — syntax-matched masculine placebo, checked against its R2 reference
# ---------------------------------------------------------------------------

R2_TOKENS = (("مطلوب", "noun"), ("مطلوبة", "noun"), ("مهندس", "noun"))
PLACEBO_TOKENS = (("مطلوب", "noun"), ("مهندس", "noun"), ("محترف", "adj"))


def test_r4_matches_the_reference_in_length_and_content_words():
    """§5.1 — R4 separates "responds to inclusive framing" from "responds to
    longer text", which it can only do if it actually matches in size."""
    reference = document("مطلوب مطلوبة مهندس", tokens=R2_TOKENS)
    placebo = document("مطلوب مهندس محترف", tokens=PLACEBO_TOKENS)
    report = check_r4(placebo, reference, char_tolerance=2)
    assert report.satisfied, report.explain()
    assert report.register is Register.R4


def test_r4_fails_when_content_word_counts_diverge():
    reference = document("مطلوب مطلوبة مهندس", tokens=R2_TOKENS)
    placebo = document("مطلوب مهندس", tokens=PLACEBO_TOKENS[:2])
    report = check_r4(placebo, reference, char_tolerance=100)
    assert not report.satisfied
    assert "content-word count" in report.explain()


def test_r4_fails_outside_the_declared_character_tolerance():
    reference = document("مطلوب مطلوبة مهندس", tokens=R2_TOKENS)
    placebo = document("مطلوب مهندس محترف جدا وممتاز", tokens=PLACEBO_TOKENS)
    report = check_r4(placebo, reference, char_tolerance=1)
    assert not report.satisfied
    assert "tolerance" in report.explain()


def test_r4_rejects_a_feminine_applicant_cue():
    """A masculine placebo that refers to the applicant in the feminine is not a
    placebo — it is a second inclusive register."""
    reference = document("مطلوب مطلوبة مهندس", tokens=R2_TOKENS)
    placebo = document(
        "مطلوبة مهندس محترف",
        [cue("مطلوبة", gen=Gender.F)],
        tokens=PLACEBO_TOKENS,
    )
    report = check_r4(placebo, reference, char_tolerance=2)
    assert not report.satisfied
    assert "feminine applicant-referring" in report.explain()


def test_r4_tolerance_must_be_declared_and_non_negative():
    reference = document("مطلوب مطلوبة مهندس", tokens=R2_TOKENS)
    placebo = document("مطلوب مهندس محترف", tokens=PLACEBO_TOKENS)
    with pytest.raises(TypeError):
        check_r4(placebo, reference)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="char_tolerance"):
        check_r4(placebo, reference, char_tolerance=-1)


# ---------------------------------------------------------------------------
# R5 — cross-lingual English
# ---------------------------------------------------------------------------


def test_r5_holds_when_no_gender_cue_is_present():
    """§5.1 — "No grammatical gender agreement". English carries none."""
    report = check_r5(document("Software engineer wanted, BSc required"))
    assert report.satisfied


def test_r5_fails_when_arabic_leaks_in():
    """A generated English ad may legitimately contain an Arabic proper noun, and
    that is exactly the leak worth catching."""
    report = check_r5(
        document(
            "Software engineer wanted at جامعة القاهرة",
            [cue("القاهرة", referent=Referent.NON_APPLICANT)],
        )
    )
    assert not report.satisfied
    assert "leaked in" in report.explain()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_counts_are_reported_whether_or_not_the_invariant_holds():
    """A boolean alone tells a reviewer the register failed, not which guarantee
    broke — and the guarantees are the contribution."""
    report = check_r1(document("مطلوبة", [cue("مطلوبة", gen=Gender.F)]))
    assert report.counts["applicant"] == 1
    assert report.counts["applicant_feminine"] == 1
    assert report.counts["applicant_masculine"] == 0
    assert report.counts["abstained"] == 0
