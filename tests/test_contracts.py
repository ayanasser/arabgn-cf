"""Data-contract invariants.

Every assertion traces to ``docs/architecture.md`` §3.2 / §4.5,
``docs/linguistic-spec.md`` §6, or a CLAUDE.md prohibition — named in each
docstring. None asserts current behaviour.
"""

from __future__ import annotations

import pytest

from arabgn.contracts import (
    AbstainTrigger,
    Country,
    DocRecord,
    DocType,
    Gender,
    Rationality,
    Referent,
    Seniority,
    TaggedCue,
    Tier,
)


def _cue(**overrides):
    """A minimal valid Tier A cue; override one field per test.

    Modelled on fixture A01 — ``المرشحة`` in ``المرشحة المثالية تتمتع بمهارات
    تواصل ممتازة``, rat=r unambiguous, the cleanest positive in the suite.
    """
    base = dict(
        cue_id="c1",
        doc_id="d1",
        token="المرشحة",
        char_span=(0, 8),
        sentence_context="المرشحة المثالية تتمتع بمهارات تواصل ممتازة",
        pos="noun",
        morph_class="Nall",
        gen=Gender.F,
        form_gen=Gender.F,
        rat_candidates=frozenset({Rationality.R}),
        tier=Tier.A,
        referent=Referent.APPLICANT,
        abstain_reason=None,
        head_token=None,
        toolkit_version="1.6.0",
        db_version="calima-msa-r13",
    )
    base.update(overrides)
    return TaggedCue(**base)


# ---------------------------------------------------------------------------
# Prohibition 6 — determinism
# ---------------------------------------------------------------------------


def test_rat_candidates_serialise_identically_regardless_of_insertion_order():
    """Prohibition 6 forbids relying on set iteration for output.

    Architecture §4.5 types ``rat_candidates`` as a ``set``. Two cues built from
    the same candidates in different insertion order must serialise identically,
    or the freeze hash is not reproducible across runs.
    """
    order_a = frozenset([Rationality.I, Rationality.R])
    order_b = frozenset([Rationality.R, Rationality.I])

    assert _cue(rat_candidates=order_a).rat_candidates_sorted() == (
        _cue(rat_candidates=order_b).rat_candidates_sorted()
    )


def test_rat_candidates_use_the_declared_canonical_order():
    """Serialisation order is (r, i, n) — declared, not derived from sorting.

    B01 ``حاصلة`` has ``rat_cands = {i, r}`` (spec §4.1); it must always emit in
    the same order.
    """
    cue = _cue(rat_candidates=frozenset({Rationality.N, Rationality.I, Rationality.R}))
    assert cue.rat_candidates_sorted() == ("r", "i", "n")

    b01_like = _cue(rat_candidates=frozenset({Rationality.I, Rationality.R}))
    assert b01_like.rat_candidates_sorted() == ("r", "i")


# ---------------------------------------------------------------------------
# Prohibition 3 — abstentions are self-describing
# ---------------------------------------------------------------------------


def test_abstained_cue_must_record_a_trigger():
    """Spec §6/§8.3 — adjudication is stratified by trigger.

    An abstained cue with no trigger cannot be routed to a stratum and would
    silently vanish from the sample, which prohibition 3 forbids.
    """
    with pytest.raises(ValueError, match="requires an abstain_reason"):
        _cue(referent=Referent.ABSTAIN, abstain_reason=None, tier=Tier.B)


def test_non_abstained_cue_must_not_record_a_trigger():
    """A trigger on a resolved cue would corrupt the stratified counts."""
    with pytest.raises(ValueError, match="non-abstained cue"):
        _cue(referent=Referent.APPLICANT, abstain_reason=AbstainTrigger.AB1)


def test_b01_shaped_abstention_is_constructible():
    """B01 ``حاصلة`` — Tier B, AB1. The canonical abstain case (spec §5)."""
    cue = _cue(
        token="حاصلة",
        tier=Tier.B,
        referent=Referent.ABSTAIN,
        abstain_reason=AbstainTrigger.AB1,
        rat_candidates=frozenset({Rationality.I, Rationality.R}),
        morph_class="N/ap",
    )
    assert cue.referent is Referent.ABSTAIN
    assert cue.abstain_reason is AbstainTrigger.AB1
    assert cue.tier is Tier.B


# ---------------------------------------------------------------------------
# Architecture §4.5 — field constraints
# ---------------------------------------------------------------------------


def test_head_token_is_tier_c_only():
    """Architecture §4.5 marks ``head_token`` "Tier C only".

    It names the agreement target whose rationality was inherited; Tiers A and B
    resolve lexically and have no target.
    """
    with pytest.raises(ValueError, match="Tier C only"):
        _cue(tier=Tier.A, head_token="خبرة")

    c01_like = _cue(
        token="واسعة", tier=Tier.C, head_token="خبرة",
        referent=Referent.NON_APPLICANT, morph_class="N-ap",
    )
    assert c01_like.head_token == "خبرة"


def test_morph_class_is_nullable():
    """ADR 002 appendix — ``stemcat`` does not separate every case.

    ``مسؤول`` carries both an ``adj``/rat=n and a ``noun``/rat=r reading inside
    ``Nall``. Where the class cannot be determined the field is ``None``, never a
    guess.
    """
    assert _cue(morph_class=None).morph_class is None


def test_tier_is_recorded_not_inferred():
    """Architecture §8.1 requires tier-wise metrics.

    The tier must be carried on every emitted cue. Tier B here is *not* derivable
    from the other fields — a Tier C cue can also abstain (AB3) — so it cannot be
    reconstructed after the fact.
    """
    cue = _cue(
        tier=Tier.B, referent=Referent.ABSTAIN, abstain_reason=AbstainTrigger.AB1
    )
    assert cue.tier is Tier.B
    assert "tier" in TaggedCue.__dataclass_fields__


# ---------------------------------------------------------------------------
# Spec §6 — the trigger list is complete
# ---------------------------------------------------------------------------


def test_all_six_abstain_triggers_exist():
    """Spec §6 enumerates AB1-AB6.

    Architecture §4.4 listed only four until 12 Aug 2026 (register D12); the spec
    is authoritative.
    """
    assert [t.value for t in AbstainTrigger] == [
        "AB1", "AB2", "AB3", "AB4", "AB5", "AB6"
    ]


def test_abstain_is_a_first_class_referent_value():
    """Prohibition 3 — abstention is its own category, not a missing value."""
    assert Referent.ABSTAIN.value == "ABSTAIN"
    assert len(Referent) == 3


# ---------------------------------------------------------------------------
# Architecture §3.2 — DocRecord
# ---------------------------------------------------------------------------


def test_docrecord_carries_doc_type():
    """ADR 003 / spec §5.2 — pro-drop defaults differ by document type.

    Architecture §3.2 originally omitted this field; Tier C is undefined without
    it and every fixture carries one.
    """
    record = DocRecord(
        doc_id="d1",
        doc_type=DocType.CV,
        text_raw="تخرجت من جامعة القاهرة عام 2018",
        text_norm="تخرجت من جامعة القاهرة عام 2018",
        country=Country.EG,
        occupation="software engineer",
        seniority=Seniority.MID,
        source_checksum="abc123",
    )
    assert record.doc_type is DocType.CV
    assert "doc_type" in DocRecord.__dataclass_fields__


def test_doc_type_covers_both_registers():
    """Spec §5.2 distinguishes ad context from CV context, and only those."""
    assert {d.value for d in DocType} == {"ad", "cv"}


# ---------------------------------------------------------------------------
# Fixture coverage
# ---------------------------------------------------------------------------


def test_every_fixture_doc_type_is_a_valid_enum_value(all_fixtures):
    """The contract must accept every ``doc_type`` the ground truth uses."""
    for fixture in all_fixtures:
        if "doc_type" in fixture:
            DocType(fixture["doc_type"])


def test_every_fixture_expected_tier_is_a_valid_enum_value(all_fixtures):
    """Same for ``expected_tier`` — the enum must cover the ground truth."""
    for fixture in all_fixtures:
        if "expected_tier" in fixture:
            Tier(fixture["expected_tier"])


def test_every_fixture_abstain_id_is_a_valid_trigger(all_fixtures):
    """Same for ``abstain_id``. B01/B02 use AB1; E02 uses AB2."""
    for fixture in all_fixtures:
        if "abstain_id" in fixture:
            AbstainTrigger(fixture["abstain_id"])


def test_every_fixture_expected_label_is_a_valid_referent(all_fixtures):
    """Same for ``expected_label``."""
    for fixture in all_fixtures:
        if "expected_label" in fixture:
            Referent(fixture["expected_label"])
