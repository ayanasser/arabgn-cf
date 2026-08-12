"""Segmentation invariants. Spec §8.2 (what an annotator sees).

These assert declared properties — offsets index the source, characters are never
altered, the boundary set is what the module says it is — rather than a recorded
output. A test of the form ``assert segment(x) == <whatever it returns today>``
would lock in a bug as ground truth (CLAUDE.md, Testing).
"""

from __future__ import annotations

import unicodedata

import pytest

from arabgn.analysis.segment import (
    LINE_BREAKS,
    TERMINATORS,
    Segment,
    segment,
    segment_for_span,
)

# Real recruitment text, deliberately including the constructions the boundary
# rule has to get right: a bullet list with no terminal punctuation, an Arabic
# comma inside one requirement, and a ta-marbuta cue.
AD = (
    "مطلوبة مهندسة برمجيات لشركة كبرى.\n"
    "- خبرة واسعة في التطوير، والعمل ضمن فريق\n"
    "- حاصلة على بكالوريوس هندسة؟"
)


def test_every_segment_is_a_literal_slice_of_the_source():
    """Prohibition 1: segmentation must not alter a single character.

    This is the ta-marbuta guarantee at the segmentation layer. If a future edit
    ever strips or folds anything, ``text != source[start:end]`` catches it at the
    point of damage.
    """
    for piece in segment(AD):
        assert piece.text == AD[piece.start : piece.end]


def test_ta_marbuta_and_diacritics_survive_segmentation():
    """The signal the project measures must reach the annotator intact."""
    text = "مطلوبة مُهَنْدِسَة. حاصلة على شهادة"
    rejoined = "".join(piece.text for piece in segment(text))
    assert rejoined.count("ة") == text.count("ة")
    marks = [c for c in text if unicodedata.combining(c)]
    assert [c for c in rejoined if unicodedata.combining(c)] == marks


def test_arabic_comma_is_not_a_boundary():
    """``،`` is a comma. Job ads use it inside a single list of requirements.

    Splitting on it would hand the annotator a fragment instead of the sentence
    spec §8.2 requires.
    """
    assert "،" not in TERMINATORS
    text = "خبرة واسعة في التطوير، والعمل ضمن فريق"
    assert len(segment(text)) == 1


def test_space_is_not_a_line_break():
    """Guards the failure mode that would be silent.

    A plain space in ``LINE_BREAKS`` makes every word its own segment, and every
    "sentence" is still a valid slice of the source — so nothing else in this file
    would catch it.
    """
    assert " " not in LINE_BREAKS
    assert "\t" not in LINE_BREAKS
    assert LINE_BREAKS == frozenset("\n\r\u2028\u2029")


def test_line_break_separates_bullet_items_carrying_no_punctuation():
    """Advertisements are line-broken lists; the line break is the only boundary."""
    assert len(segment(AD)) == 3


def test_terminal_punctuation_stays_with_its_sentence():
    """An annotator judging reference benefits from seeing the sentence was a
    question (spec §8.2 shows the full sentence, not a stripped one)."""
    pieces = segment(AD)
    assert pieces[0].text.endswith(".")
    assert pieces[-1].text.endswith("؟")


def test_a_run_of_terminators_is_one_boundary():
    assert [p.text for p in segment("مطلوب مهندس!!! خبرة")] == [
        "مطلوب مهندس!!!",
        "خبرة",
    ]


def test_whitespace_only_input_yields_no_segments():
    assert segment("   \n\n  ") == ()
    assert segment("") == ()


def test_segmentation_is_deterministic():
    """Prohibition 6. Pure scan, no regex, no locale, no randomness."""
    assert segment(AD) == segment(AD)


def test_offsets_are_rejected_when_they_disagree_with_the_text():
    with pytest.raises(ValueError, match="offsets"):
        Segment(text="مهندسة", start=0, end=99)


def test_segment_for_span_finds_the_containing_sentence():
    pieces = segment(AD)
    cue_start = AD.index("حاصلة")
    host = segment_for_span(pieces, cue_start, cue_start + len("حاصلة"))
    assert host is not None
    assert "حاصلة" in host.text
    assert host is pieces[-1]


def test_segment_for_span_returns_none_rather_than_guessing():
    """A span straddling a boundary has no containing sentence.

    Returning a best-effort match would show an annotator a sentence the cue is
    not in, which contaminates the label rather than losing it.
    """
    pieces = segment(AD)
    assert segment_for_span(pieces, 0, len(AD)) is None
