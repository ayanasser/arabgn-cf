"""Orthographic integrity — the load-bearing test.

CLAUDE.md prohibition 1: "Unicode NFC is the only permitted normalisation.
``tests/test_normalisation.py`` asserts this; do not weaken or skip that test."

Every assertion below traces to a fixture id in
``tests/fixtures/tagger_fixtures.yaml`` group 8, or to a rule in
``docs/linguistic-spec.md`` / ``docs/architecture.md`` §3.2. None asserts current
behaviour.

If O01 fails, ``ة`` is being folded and the entire study is invalid.
"""

from __future__ import annotations

import unicodedata

import pytest

from arabgn.analysis.text import normalise
from conftest import of_type, skip_if_review

# Group 8, driven from the data rather than hardcoded, so a fixture the author
# adds is picked up without touching this file.
NORMALISATION_FIXTURES = of_type("normalisation")

TA_MARBUTA = "ة"  # ة
HEH = "ه"  # ه
ALEF = "ا"  # ا
YA = "ي"  # ي
ALEF_MAQSURA = "ى"  # ى


def _ids(fixtures):
    return [f["id"] for f in fixtures]


@pytest.mark.parametrize(
    "fixture", NORMALISATION_FIXTURES, ids=_ids(NORMALISATION_FIXTURES)
)
def test_normalisation_fixture(fixture):
    """Every group-8 fixture: ``text`` normalises to ``expected_text_norm``.

    Covers O01 (ta-marbuta), O02 (hamza forms), O03 (harakat).
    """
    skip_if_review(fixture)
    assert normalise(fixture["text"]) == fixture["expected_text_norm"], (
        f"fixture {fixture['id']} — {fixture['note'].strip().splitlines()[0]}"
    )


def test_o01_ta_marbuta_is_not_folded_to_heh(get_fixture):
    """O01 — ``ة`` must survive. Prohibition 1; the signal the study measures.

    ``حاصلة على بكالوريوس هندسة`` carries two ta-marbutas. A pipeline that maps
    ``ة`` -> ``ه`` would erase the primary feminine marker and make ``حاصلة``
    indistinguishable from a masculine form.
    """
    fixture = get_fixture("O01")
    result = normalise(fixture["text"])

    assert result.count(TA_MARBUTA) == fixture["text"].count(TA_MARBUTA)
    assert TA_MARBUTA in result
    assert result.count(HEH) == fixture["text"].count(HEH), (
        "heh count changed — ة was folded to ه"
    )


def test_o02_hamza_forms_are_not_folded_to_bare_alef(get_fixture):
    """O02 — ``أ إ آ`` must not collapse to ``ا``. Prohibition 1.

    ``أحمد إبراهيم آدم`` — one of each hamza form.
    """
    fixture = get_fixture("O02")
    source = fixture["text"]
    result = normalise(source)

    for hamza in ("أ", "إ", "آ"):  # أ إ آ
        assert result.count(hamza) == source.count(hamza), (
            f"{unicodedata.name(hamza)} count changed under normalisation"
        )
    assert result.count(ALEF) == source.count(ALEF), (
        "bare alef count changed — a hamza form was folded to ا"
    )


def test_o03_diacritics_are_preserved(get_fixture):
    """O03 — harakat must survive. Architecture §3.2, ADR 005.

    O01 and O02 guard only ``ة`` and hamza; a step that stripped every vowel mark
    while leaving those intact would pass both. ``مُهَنْدِسَة`` carries one mark
    per base letter, so NFC is the identity function on it.
    """
    fixture = get_fixture("O03")
    source = fixture["text"]
    result = normalise(source)

    marks_before = [c for c in source if unicodedata.combining(c)]
    marks_after = [c for c in result if unicodedata.combining(c)]

    assert marks_before, "O03 must contain diacritics or it guards nothing"
    assert marks_after == marks_before, "diacritics were altered or stripped"
    assert result == source


def test_alef_maqsura_is_not_folded_to_ya():
    """Prohibition 1 names ``ى`` -> ``ي`` alongside the other two folds.

    No fixture covers it — asserted directly from the prohibition. ``مستشفى``
    (hospital) must not become ``مستشفي``.
    """
    source = "مستشفى"
    result = normalise(source)

    assert result.count(ALEF_MAQSURA) == source.count(ALEF_MAQSURA)
    assert result.count(YA) == source.count(YA)
    assert result == source


def test_normalise_is_idempotent():
    """NFC applied twice equals NFC applied once.

    Required by prohibition 6: a document normalised on ingest and again on
    re-read must produce a byte-identical ``text_norm``, or the ``source_checksum``
    in ``DocRecord`` is not stable.
    """
    for fixture in NORMALISATION_FIXTURES:
        once = normalise(fixture["text"])
        assert normalise(once) == once, f"{fixture['id']} is not idempotent"


def test_normalise_applies_nfc():
    """The transformation is NFC — not NFD, NFKC or NFKD.

    NFKC would be actively harmful here: it maps Arabic presentation forms and
    ligatures onto their canonical letters, which is a form of orthographic
    normalisation. Asserted with a decomposed sequence that NFC composes.
    """
    decomposed = "أ"  # bare alef + combining hamza above
    composed = "أ"  # أ

    assert normalise(decomposed) == composed
    assert normalise(decomposed) == unicodedata.normalize("NFC", decomposed)
