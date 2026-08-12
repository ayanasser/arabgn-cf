"""Annotation pool construction. Spec §8.2 (blindness), §8.3 (stratification).

Runs on a synthetic disambiguator, so no model download and no corpus — the
boundary object :class:`AnalysedToken` is plain data by design (ADR 007), which
is what makes this possible.
"""

from __future__ import annotations

import json

import pytest

from arabgn.adjudication.items import FORBIDDEN_FIELDS
from arabgn.adjudication.pool import build_pool, extract_cues, write_pool
from arabgn.analysis.cues import CandidateAnalysis
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.contracts import (
    AbstainTrigger,
    Country,
    DocRecord,
    DocType,
    Referent,
    Seniority,
    Tier,
)  # noqa: F401 — Tier and AbstainTrigger are used by the Tier C assertions
from arabgn.tagger.analyzer import AnalysedToken

# Provisional θ from docs/theta-sweep.md §3 — the most robust point over the nine
# fixtures. Provisional by design: the calibrated value comes from the gold set
# this pool exists to build.
THETA = ThresholdConfig(theta_high=0.495, theta_low=0.285)


def cand(score, pos, rat, gen="f", form_gen="f", stemcat="N/ap"):
    return CandidateAnalysis(
        score=score, pos=pos, rat=rat, gen=gen, form_gen=form_gen, stemcat=stemcat
    )


def token(text, start, candidates, index=0):
    return AnalysedToken(
        token=text,
        index=index,
        char_start=start,
        char_end=start + len(text),
        candidates=tuple(candidates),
    )


class FakeDisambiguator:
    """Returns pre-built analyses. Mirrors the real wrapper's two version fields."""

    toolkit_version = "1.6.0"
    db_version = "calima-msa-r13"

    def __init__(self, by_doc):
        self._by_doc = by_doc

    def analyse(self, text):
        return self._by_doc[text]


def record(text, doc_id="aj-test", country=Country.EG):
    return DocRecord(
        doc_id=doc_id,
        doc_type=DocType.AD,
        text_raw=text,
        text_norm=text,
        country=country,
        occupation="تكنولوجيا المعلومات",
        seniority=Seniority.UNSPECIFIED,
        source_checksum="deadbeef",
    )


# `خبرة` — rat=i unambiguous. Spec §5 Tier A, not applicant-referring.
KHIBRA = [cand(0.95, "noun", "i"), cand(0.05, "noun", "i")]
# `المرشحة` — rat=r dominant. Rational, so the role test applies (spec §5.1).
MURASHAHA = [cand(0.90, "noun", "r"), cand(0.10, "noun", "i")]
# `واسعة` — an adjective, i.e. Tier C (spec §5). Carries gender by agreement, so
# `rat = n` and its own mass says nothing about reference.
WASIA = [cand(0.99, "adj", "n")]
# `تخرجت` — a verb. Tier C via the branch D8 still blocks.
VERB = [cand(0.99, "verb", "n")]


def test_tier_c_adjectives_resolve_by_inheritance():
    """Spec §5 Tier C, adjective branch — fixture C01's construction.

    ``واسعة`` inherits ``non_applicant`` from ``خبرة`` (rat=i). No author
    decision is involved: the role test governs *rational* targets only, so an
    irrational one resolves outright.
    """
    text = "خبرة واسعة"
    doc = record(text)
    analysed = (
        token("خبرة", 0, KHIBRA),
        token("واسعة", 5, WASIA, index=1),
    )
    cues, skipped = extract_cues(
        doc, analysed, THETA, toolkit_version="1.6.0", db_version="calima-msa-r13"
    )
    assert skipped["tier_c"] == 0
    assert [c.token for c in cues] == ["خبرة", "واسعة"]

    adjective = cues[1]
    assert adjective.tier is Tier.C
    assert adjective.referent is Referent.NON_APPLICANT
    assert adjective.head_token == "خبرة"


def test_tier_c_verbs_are_skipped_and_counted():
    """The verb branch stays blocked on D8 (pro-drop), and that must be visible.

    Skipping silently would let the pool read as covering the corpus when it
    omits تخرجت / عملت — the markings the paper is centrally about.
    """
    text = "تخرجت من الجامعة"
    doc = record(text)
    analysed = (
        token("تخرجت", 0, VERB, index=0),
        token("من", 6, [cand(1.0, "prep", "n")], index=1),
        token("الجامعة", 9, KHIBRA, index=2),
    )
    cues, skipped = extract_cues(
        doc, analysed, THETA, toolkit_version="1.6.0", db_version="calima-msa-r13"
    )
    assert skipped["tier_c"] == 1
    assert "تخرجت" not in [c.token for c in cues]


def test_the_agreement_search_cannot_cross_a_sentence_boundary():
    """Punctuation is skippable when looking back for a head, so an unbounded
    search would let a sentence-initial adjective attach to the previous
    sentence's noun.

    Tokens are grouped by host segment so the resolver cannot reach past what it
    is handed. ``واسعة`` here opens its own sentence and must abstain under AB2,
    not inherit from ``خبرة``.
    """
    text = "خبرة كبيرة.\nواسعة جدا"
    doc = record(text)
    analysed = (
        token("خبرة", 0, KHIBRA, index=0),
        token("كبيرة", 5, WASIA, index=1),
        token("واسعة", text.index("واسعة"), WASIA, index=2),
    )
    cues, _ = extract_cues(
        doc, analysed, THETA, toolkit_version="1.6.0", db_version="calima-msa-r13"
    )
    second_sentence = [c for c in cues if c.sentence_context == "واسعة جدا"]
    assert second_sentence, [c.sentence_context for c in cues]
    assert second_sentence[0].referent is Referent.ABSTAIN
    assert second_sentence[0].abstain_reason is AbstainTrigger.AB2
    assert second_sentence[0].head_token is None


def test_rational_cues_abstain_under_ab6_while_d7_is_open():
    """Spec §5.1: rational ≠ applicant, and the role test is unsettled.

    No cue in this pool may carry ``applicant`` — that is what an open D7 means.
    """
    text = "المرشحة المثالية"
    doc = record(text)
    analysed = (token("المرشحة", 0, MURASHAHA),)
    cues, _ = extract_cues(
        doc, analysed, THETA, toolkit_version="1.6.0", db_version="calima-msa-r13"
    )
    assert cues[0].referent is Referent.ABSTAIN
    assert cues[0].abstain_reason is AbstainTrigger.AB6
    assert cues[0].tier is Tier.A


def test_irrational_cues_resolve_to_non_applicant():
    """Spec §5 Tier A: ``خبرة واسعة`` is feminine twice over and refers to a thing."""
    text = "خبرة واسعة"
    doc = record(text)
    cues, _ = extract_cues(
        doc,
        (token("خبرة", 0, KHIBRA),),
        THETA,
        toolkit_version="1.6.0",
        db_version="calima-msa-r13",
    )
    assert cues[0].referent is Referent.NON_APPLICANT
    assert cues[0].tier is Tier.A


def test_sentence_context_is_the_sentence_not_the_document():
    """Spec §8.2 — the annotator sees the full sentence, not the whole ad."""
    text = "مطلوبة مهندسة.\nخبرة واسعة في التطوير"
    doc = record(text)
    start = text.index("خبرة")
    cues, _ = extract_cues(
        doc,
        (token("خبرة", start, KHIBRA),),
        THETA,
        toolkit_version="1.6.0",
        db_version="calima-msa-r13",
    )
    assert cues[0].sentence_context == "خبرة واسعة في التطوير"


def test_cue_span_indexes_the_sentence_the_annotator_is_shown(tmp_path):
    """The highlight must land on the cue.

    ``blind`` rebases nothing, so a span indexing the document while the sentence
    is a substring would silently highlight the wrong word.
    """
    text = "مطلوبة مهندسة.\nخبرة واسعة في التطوير"
    doc = record(text)
    start = text.index("خبرة")
    analysed = (token("خبرة", start, KHIBRA),)
    result = build_pool(
        [doc],
        FakeDisambiguator({text: analysed}),
        n=1,
        seed=7,
        config=THETA,
    )
    paths = write_pool(result, tmp_path)
    item = json.loads(paths["items"].read_text(encoding="utf-8").splitlines()[0])
    assert item["sentence"][item["cue_start"] : item["cue_end"]] == "خبرة"


def test_items_file_leaks_no_tagger_field(tmp_path):
    """Spec §8.2. Blind annotation is required or precision is contaminated."""
    text = "خبرة واسعة في التطوير"
    doc = record(text)
    analysed = (token("خبرة", 0, KHIBRA),)
    result = build_pool(
        [doc], FakeDisambiguator({text: analysed}), n=1, seed=7, config=THETA
    )
    paths = write_pool(result, tmp_path)
    for line in paths["items"].read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        for forbidden in FORBIDDEN_FIELDS:
            assert forbidden not in item
        assert "cue_id" not in item, "cue_id joins straight back to the prediction"


def test_manifest_carries_the_join_and_flags_theta_as_provisional(tmp_path):
    text = "خبرة واسعة في التطوير"
    doc = record(text)
    result = build_pool(
        [doc],
        FakeDisambiguator({text: (token("خبرة", 0, KHIBRA),)}),
        n=1,
        seed=7,
        config=THETA,
    )
    paths = write_pool(result, tmp_path)
    row = json.loads(paths["manifest"].read_text(encoding="utf-8").splitlines()[0])
    assert row["item_id"] and row["cue_id"]
    assert row["theta_high"] == THETA.theta_high
    assert "PROVISIONAL" in row


def test_verbatim_repeated_advertisements_collapse_and_are_counted():
    """ArabJobs repeats 849 advertisements verbatim, and ``doc_id`` is a content
    hash — so their cues share a ``cue_id``.

    Collapsing is right for annotation: the cues are byte-identical, and nobody
    should label the same sentence twice. But it must be *counted*, because
    §8.5's denominator is postings rather than distinct texts, and a silent
    collapse would understate it.
    """
    text = "خبرة واسعة في التطوير"
    analysed = (token("خبرة", 0, KHIBRA),)
    twins = [record(text, doc_id="aj-same"), record(text, doc_id="aj-same")]
    result = build_pool(
        twins, FakeDisambiguator({text: analysed}), n=1, seed=7, config=THETA
    )
    assert result.counts.cues_duplicate_documents == 1
    assert result.counts.cues_tier_ab == 1
    assert len({cue.cue_id for cue in result.cues}) == len(result.cues)


def test_pool_build_is_deterministic():
    """Prohibition 6 — same seed, same corpus, byte-identical draw."""
    text = "خبرة واسعة في التطوير"
    doc = record(text)
    analysed = (token("خبرة", 0, KHIBRA),)

    def run():
        return build_pool(
            [doc], FakeDisambiguator({text: analysed}), n=1, seed=7, config=THETA
        )

    first, second = run(), run()
    assert first.plan.cue_ids == second.plan.cue_ids
    assert first.item_ids == second.item_ids


def test_presentation_order_does_not_follow_draw_order():
    """Spec §8.3 strata are drawn in sorted key order.

    Unshuffled, an annotator would meet a whole stratum consecutively and
    calibrate to it. The shuffle must therefore actually reorder.
    """
    text = " ".join(["خبرة"] * 40)
    doc = record(text)
    analysed = tuple(
        token("خبرة", index * 5, KHIBRA, index=index) for index in range(40)
    )
    result = build_pool(
        [doc], FakeDisambiguator({text: analysed}), n=40, seed=7, config=THETA
    )
    drawn_in_sorted_order = tuple(sorted(result.plan.cue_ids))
    presented = tuple(cue_id for _, cue_id in result.item_ids)
    assert sorted(presented) == list(drawn_in_sorted_order)
    assert presented != drawn_in_sorted_order


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_drawn_cue_reaches_the_items_file(tmp_path, seed):
    """Nothing may be lost between the draw and the annotator."""
    text = " ".join(["خبرة"] * 20)
    doc = record(text)
    analysed = tuple(
        token("خبرة", index * 5, KHIBRA, index=index) for index in range(20)
    )
    result = build_pool(
        [doc], FakeDisambiguator({text: analysed}), n=10, seed=seed, config=THETA
    )
    paths = write_pool(result, tmp_path / str(seed))
    lines = paths["items"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(result.plan.cue_ids)
