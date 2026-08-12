"""Phase 2A — adjudication tooling.

Every assertion names the spec section or ADR it derives from. None asserts
current behaviour.
"""

from __future__ import annotations

import dataclasses

import pytest

from arabgn.adjudication.items import (
    FORBIDDEN_FIELDS,
    VALID_ANSWERS,
    AnnotationItem,
    AnnotationResponse,
    blind,
)
from arabgn.adjudication.store import AnnotationStore, utc_timestamp
from arabgn.analysis.agreement import (
    KAPPA_FLOOR,
    GoldSetUnusable,
    adjudicate,
    assert_gold_set_usable,
    cohens_kappa,
)
from arabgn.analysis.sampling import stratified_sample, stratify
from arabgn.contracts import (
    AbstainTrigger,
    DocType,
    Gender,
    Rationality,
    Referent,
    TaggedCue,
    Tier,
)


def _cue(**over):
    base = dict(
        cue_id="c1", doc_id="d1", token="حاصلة", char_span=(0, 5),
        sentence_context="حاصلة على بكالوريوس هندسة",
        pos="noun", morph_class="N/ap", gen=Gender.F, form_gen=Gender.F,
        rat_candidates=frozenset({Rationality.I, Rationality.R}),
        tier=Tier.B, referent=Referent.ABSTAIN,
        abstain_reason=AbstainTrigger.AB1, head_token=None,
        toolkit_version="1.6.0", db_version="calima-msa-r13",
    )
    base.update(over)
    return TaggedCue(**base)


# ---------------------------------------------------------------------------
# Spec §8.2 — blindness
# ---------------------------------------------------------------------------


def test_annotation_item_cannot_carry_any_prediction_field():
    """Spec §8.2 — annotators must not see prediction, tier or abstain status.

    Enforced structurally: the dataclass has no such fields, so no display path
    can leak them. Adding one fails this test rather than silently contaminating
    the precision estimates.
    """
    fields = {f.name for f in dataclasses.fields(AnnotationItem)}
    leaked = fields & set(FORBIDDEN_FIELDS)
    assert not leaked, f"AnnotationItem leaks tagger state to annotators: {leaked}"


def test_annotation_item_carries_exactly_what_spec_permits():
    """Spec §8.2 — "the full sentence, the cue highlighted, and the document type"."""
    fields = {f.name for f in dataclasses.fields(AnnotationItem)}
    assert fields == {"item_id", "sentence", "cue_start", "cue_end", "doc_type"}


def test_blind_discards_everything_the_tagger_decided():
    """A blinded item must not be joinable back to the prediction by itself."""
    cue = _cue()
    item = blind(cue, item_id="i-001", doc_type=DocType.CV)

    serialised = repr(dataclasses.asdict(item))
    for forbidden in ("ABSTAIN", "AB1", "N/ap", "noun", Tier.B.value):
        assert forbidden not in serialised, (
            f"blinded item leaks {forbidden!r} (spec §8.2)"
        )
    assert item.item_id != cue.cue_id, (
        "item_id must not be the cue_id — that is a direct join to the prediction"
    )


def test_blind_requires_doc_type_explicitly():
    """TaggedCue carries doc_id, not doc_type — the caller must resolve it.

    Spec §8.2 permits showing document type, and Tier C pro-drop (§5.2) makes it
    meaningful to the annotator.
    """
    item = blind(_cue(), item_id="i-1", doc_type=DocType.CV)
    assert item.doc_type is DocType.CV


def test_render_delimits_the_cue():
    item = AnnotationItem(
        item_id="i-1",
        sentence="حاصلة على بكالوريوس هندسة",
        cue_start=0,
        cue_end=5,
        doc_type=DocType.CV,
    )
    assert item.cue == "حاصلة"
    assert item.render() == "«حاصلة» على بكالوريوس هندسة"


# ---------------------------------------------------------------------------
# Spec §8.1 — `unclear` is recorded, never coerced
# ---------------------------------------------------------------------------


def test_unclear_is_a_valid_answer():
    """Spec §8.1 — "unclear is a valid answer"."""
    assert "unclear" in VALID_ANSWERS
    response = AnnotationResponse(
        item_id="i-1", annotator_id="A1", answer="unclear",
        timestamp=utc_timestamp(),
    )
    assert response.answer == "unclear"


def test_invalid_answers_are_rejected_not_coerced():
    """An out-of-space answer must fail loudly, never be mapped to a label."""
    with pytest.raises(ValueError, match="never coerced"):
        AnnotationResponse(
            item_id="i-1", annotator_id="A1", answer="probably_applicant",
            timestamp=utc_timestamp(),
        )


def test_annotator_id_is_required():
    """Spec §8 — a stable annotator id is required for per-pair κ."""
    with pytest.raises(ValueError, match="annotator_id"):
        AnnotationResponse(
            item_id="i-1", annotator_id="", answer="applicant",
            timestamp=utc_timestamp(),
        )


# ---------------------------------------------------------------------------
# Spec §8 — append-only store
# ---------------------------------------------------------------------------


def test_store_is_append_only(tmp_path):
    """Appending twice keeps both records; nothing is overwritten."""
    store = AnnotationStore(tmp_path / "a.jsonl")
    for i in range(3):
        store.append(
            AnnotationResponse(
                item_id=f"i-{i}", annotator_id="A1", answer="applicant",
                timestamp=utc_timestamp(),
            )
        )
    assert len(list(store.responses())) == 3

    store.append(
        AnnotationResponse(
            item_id="i-0", annotator_id="A1", answer="unclear",
            timestamp=utc_timestamp(),
        )
    )
    responses = list(store.responses())
    assert len(responses) == 4, "a re-answer must append, not replace"
    assert [r.answer for r in responses][-1] == "unclear"


def test_store_has_no_update_or_delete_path():
    """An annotation revisable in place makes κ silently unstable."""
    for forbidden in ("update", "delete", "remove", "overwrite", "replace"):
        assert not hasattr(AnnotationStore, forbidden)


def test_store_roundtrips_arabic_unchanged(tmp_path):
    """Prohibition 1 — the store must not mangle Arabic. `ة` survives JSON."""
    store = AnnotationStore(tmp_path / "a.jsonl")
    store.append(
        AnnotationResponse(
            item_id="حاصلة-1", annotator_id="A1", answer="applicant",
            timestamp=utc_timestamp(), comment="ta-marbuta: ة",
        )
    )
    back = list(store.responses())[0]
    assert back.item_id == "حاصلة-1"
    assert "ة" in back.comment


def test_double_annotated_finds_the_kappa_subset(tmp_path):
    """Spec §8.3 — κ is computed over the doubly-annotated subset."""
    store = AnnotationStore(tmp_path / "a.jsonl")
    for annotator, item in (("A1", "i-1"), ("A2", "i-1"), ("A1", "i-2")):
        store.append(
            AnnotationResponse(
                item_id=item, annotator_id=annotator, answer="applicant",
                timestamp=utc_timestamp(),
            )
        )
    assert store.double_annotated() == ("i-1",)


def test_unclear_rate_is_reported(tmp_path):
    """Spec §8.1 — "the rate of unclear is itself reported"."""
    store = AnnotationStore(tmp_path / "a.jsonl")
    # enumerate, not id(): id() is a memory address and would make the test
    # inputs nondeterministic across runs (prohibition 6).
    for i, answer in enumerate(("applicant", "unclear", "non_applicant", "unclear")):
        store.append(
            AnnotationResponse(
                item_id=f"i-{i}", annotator_id="A1",
                answer=answer, timestamp=utc_timestamp(),
            )
        )
    assert store.unclear_rate() == 0.5


# ---------------------------------------------------------------------------
# Architecture §8.1 — Cohen's κ and the gate
# ---------------------------------------------------------------------------


def test_perfect_agreement_is_kappa_one():
    labels = ["applicant", "non_applicant", "unclear", "applicant"]
    assert cohens_kappa(labels, labels).kappa == 1.0


def test_kappa_counts_unclear_as_a_category():
    """Spec §8.1 — `unclear` is a valid answer, so it participates in κ.

    Dropping it would inflate κ by discarding exactly the items annotators found
    hardest — the same failure mode prohibition 3 forbids for abstentions.
    """
    a = ["applicant", "unclear", "unclear"]
    b = ["applicant", "unclear", "non_applicant"]
    result = cohens_kappa(a, b)
    assert result.n_items == 3, "no item was dropped for being unclear"
    assert result.unclear_rate > 0


def test_kappa_is_undefined_not_zero_when_expected_agreement_is_one():
    """κ = (po-pe)/(1-pe) is 0/0 when both annotators used one label throughout.

    Returning 0.0 or 1.0 would put a fabricated number in a reported table.
    """
    result = cohens_kappa(["applicant"] * 4, ["applicant"] * 4)
    assert result.kappa is None
    assert "undefined" in result.undefined_reason


def test_kappa_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="differ in length"):
        cohens_kappa(["applicant"], ["applicant", "unclear"])


def test_kappa_rejects_labels_outside_the_permitted_space():
    """An answer outside §8.1's three must not be silently admitted to κ."""
    with pytest.raises(ValueError, match="outside the permitted space"):
        cohens_kappa(["applicant", "maybe"], ["applicant", "applicant"])


def test_gate_raises_below_the_floor():
    """Architecture §8.1 — κ ≥ 0.7 or the gold set is not usable.

    A hard gate, not a warning: below the floor every downstream
    precision/recall figure is uninterpretable.
    """
    a = ["applicant", "non_applicant", "applicant", "unclear"]
    b = ["non_applicant", "applicant", "unclear", "applicant"]
    result = cohens_kappa(a, b)
    assert result.kappa < KAPPA_FLOOR
    with pytest.raises(GoldSetUnusable, match="not usable"):
        assert_gold_set_usable(result)


def test_gate_passes_at_or_above_the_floor():
    labels = ["applicant"] * 8 + ["non_applicant"] * 8
    result = cohens_kappa(labels, labels)
    assert result.kappa >= KAPPA_FLOOR
    assert_gold_set_usable(result)


def test_undefined_kappa_fails_the_gate():
    """Undefined is not "passed" — it cannot license a usable gold set."""
    with pytest.raises(GoldSetUnusable, match="undefined"):
        assert_gold_set_usable(cohens_kappa(["applicant"] * 3, ["applicant"] * 3))


# ---------------------------------------------------------------------------
# Spec §8.4 — adjudication
# ---------------------------------------------------------------------------


def test_agreement_stands():
    assert adjudicate("applicant", "applicant") == "applicant"


def test_third_annotator_breaks_a_tie():
    assert adjudicate("applicant", "non_applicant", third="applicant") == "applicant"


def test_persistent_disagreement_is_recorded_unclear_not_forced():
    """Spec §8.4 — "recorded as unclear and reported, not forced to a label"."""
    assert adjudicate("applicant", "non_applicant", third="unclear") == "unclear"


def test_disagreement_without_a_third_annotator_is_an_error():
    """Spec §8.4 routes disagreements to a person, not to a rule."""
    with pytest.raises(ValueError, match="third annotator"):
        adjudicate("applicant", "non_applicant")


# ---------------------------------------------------------------------------
# Spec §8.3 — stratified sampling, and prohibition 6
# ---------------------------------------------------------------------------


def _cues(n=60):
    out = []
    for i in range(n):
        out.append(
            {
                "cue_id": f"c{i:03d}",
                "token": "مطلوبة" if i % 10 == 0 else "خبرة",
                "country": ["EG", "JO", "SA", "AE"][i % 4],
                "seniority": ["entry", "mid", "senior"][i % 3],
                "pos": "noun",
                "tier": ["A", "B", "C"][i % 3],
                "abstain_reason": None if i % 2 else "AB1",
            }
        )
    return out


def test_sampling_is_deterministic_given_a_seed():
    """Prohibition 6 forbids unseeded sampling."""
    a = stratified_sample(_cues(), n=20, seed=42)
    b = stratified_sample(_cues(), n=20, seed=42)
    assert a.cue_ids == b.cue_ids


def test_sampling_is_independent_of_input_order():
    """Prohibition 6 — output must not depend on iteration order of the input."""
    cues = _cues()
    forward = stratified_sample(cues, n=20, seed=7)
    backward = stratified_sample(list(reversed(cues)), n=20, seed=7)
    assert forward.cue_ids == backward.cue_ids


def test_different_seeds_give_different_samples():
    """Otherwise the seed is not doing anything and reproducibility is illusory."""
    a = stratified_sample(_cues(), n=20, seed=1)
    b = stratified_sample(_cues(), n=20, seed=2)
    assert a.cue_ids != b.cue_ids


def test_sampling_requires_a_seed():
    """No default seed — prohibition 6."""
    with pytest.raises(TypeError):
        stratified_sample(_cues(), n=10)  # type: ignore[call-arg]


def test_strata_are_the_five_spec_variables():
    """Spec §8.3 — country, seniority, POS class, tier, abstain trigger."""
    plan = stratified_sample(_cues(), n=20, seed=3)
    assert plan.strata_fields[:5] == (
        "country", "seniority", "pos", "tier", "abstain_reason",
    )


def test_strata_fields_align_positionally_with_the_keys():
    """A declared field list shorter than the key makes keys unreadable.

    `error_class` is part of the key (so §7.1/§7.2 cues form their own strata),
    so it must appear in `strata_fields` too.
    """
    plan = stratified_sample(_cues(), n=20, seed=3)
    assert plan.strata_fields[-1] == "error_class"
    for key in plan.per_stratum:
        assert len(key) == len(plan.strata_fields)


def test_known_error_classes_are_oversampled():
    """Spec §8.3 / architecture §8.1 — over-sample the مطلوبة error class (§7.1).

    Its stratum is weighted 3x, so it must be drawn at above its base rate.
    """
    cues = _cues(120)
    base_rate = sum(1 for c in cues if c["token"] == "مطلوبة") / len(cues)
    plan = stratified_sample(cues, n=60, seed=11)
    ids = set(plan.cue_ids)
    drawn = [c for c in cues if c["cue_id"] in ids]
    drawn_rate = sum(1 for c in drawn if c["token"] == "مطلوبة") / len(drawn)
    assert drawn_rate > base_rate, (
        f"مطلوبة drawn at {drawn_rate:.3f} vs base {base_rate:.3f} — "
        f"§7.1 error class is not being over-sampled"
    )


def test_shortfalls_are_reported_not_absorbed():
    """A stratum smaller than its quota must be visible.

    Silently short-drawing reads as "covered" when it is not — the same class of
    error prohibition 3 forbids for abstentions.
    """
    tiny = [
        {"cue_id": "c1", "token": "خبرة", "country": "EG", "seniority": "entry",
         "pos": "noun", "tier": "A", "abstain_reason": None},
        {"cue_id": "c2", "token": "خبرة", "country": "JO", "seniority": "mid",
         "pos": "noun", "tier": "B", "abstain_reason": "AB1"},
    ]
    plan = stratified_sample(tiny, n=50, seed=5)
    assert plan.shortfalls, "short-drawn strata must be reported"
    assert len(plan.cue_ids) <= 2


def test_stratify_partitions_without_loss():
    cues = _cues()
    strata = stratify(cues, ("country", "tier"))
    assert sum(len(v) for v in strata.values()) == len(cues)
