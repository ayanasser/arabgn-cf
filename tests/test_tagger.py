"""Tagger integration — requires model data.

Marked ``needs_camel_data`` so a clean checkout fails legibly rather than
confusingly (CLAUDE.md). Run ``camel_data -i morphology-db-msa-r13`` and
``camel_data -i disambig-bert-unfactored-msa`` first.

The pure classification layer is tested in ``test_cues.py`` with no model at all —
that separation is ADR 007's point.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.cues import rationality_mass
from arabgn.contracts import Rationality

pytestmark = pytest.mark.needs_camel_data


@pytest.fixture(scope="module")
def disambiguator():
    try:
        from arabgn.tagger.analyzer import load_disambiguator

        return load_disambiguator()
    except FileNotFoundError as exc:
        pytest.skip(f"camel_data not installed: {exc}")


def _mass(disambiguator, sentence, token):
    analysed = disambiguator.analyse(sentence)
    match = [t for t in analysed if t.token == token]
    assert match, f"{token!r} not found in {sentence!r}"
    return rationality_mass(match[0].candidates), match[0]


# ---------------------------------------------------------------------------
# CLAUDE.md — top=100 is load-bearing
# ---------------------------------------------------------------------------


def test_top_must_be_100():
    """CLAUDE.md — the default (top-1) destroys the Tier B abstain mechanism."""
    from arabgn.tagger.analyzer import Disambiguator

    with pytest.raises(ValueError, match="destroys the Tier B abstain"):
        Disambiguator(model=object(), top=1)


def test_top_100_returns_many_candidates(disambiguator):
    """Spec §4.1 — with one candidate, rationality can never disagree with itself.

    `حاصلة` must return multiple analyses spanning rat ∈ {i, r}, or AB1 is
    unreachable and B01 could never abstain.
    """
    _, token = _mass(
        disambiguator,
        "مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة",
        "حاصلة",
    )
    assert len(token.candidates) > 1
    assert {c.rat for c in token.candidates} >= {"i", "r"}


# ---------------------------------------------------------------------------
# ADR 001 — the calibration evidence must reproduce
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence,token,rat,expected",
    [
        (
            "مطلوب مهندس برمجيات لديه خبرة واسعة في تطوير التطبيقات",
            "خبرة", Rationality.I, 0.904,
        ),
        (
            "المرشحة المثالية تتمتع بمهارات تواصل ممتازة",
            "المرشحة", Rationality.R, 0.747,
        ),
        (
            "مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة",
            "حاصلة", Rationality.I, 0.676,
        ),
    ],
)
def test_adr_001_masses_reproduce(disambiguator, sentence, token, rat, expected):
    """θ is calibrated against these numbers and then frozen.

    If they drift, the pre-registered θ no longer means what ADR 001 says it
    means, so this is a regression test on the calibration evidence itself.
    """
    mass, _ = _mass(disambiguator, sentence, token)
    assert mass[rat] == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Register D13 — determinism
# ---------------------------------------------------------------------------


def test_disambiguation_is_deterministic(disambiguator):
    """Prohibition 6 — the freeze claim depends on this.

    Verified on CPU, single process. Re-verify on the hardware doing the real
    sweep: GPU kernel nondeterminism is the usual failure mode.
    """
    sentence = "مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة"
    runs = [_mass(disambiguator, sentence, "حاصلة")[0] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# ---------------------------------------------------------------------------
# Spec §3.1 — POS filtering. Fixtures N01, N02.
# ---------------------------------------------------------------------------


def test_n01_preposition_emits_no_cue(disambiguator):
    """N01 `على` in `حاصلة على بكالوريوس هندسة` — must emit no cue."""
    analysed = disambiguator.analyse("حاصلة على بكالوريوس هندسة")
    on = [t for t in analysed if t.token == "على"]
    assert on, "tokeniser lost على"
    assert not on[0].is_cue(), (
        "على emitted a cue — POS filtering (spec §3.1) is not applied. "
        "It returns rat={n, na, r} and would flood the abstain queue."
    )


def test_n02_digit_emits_no_cue(disambiguator):
    """N02 `2018` in `تخرجت من جامعة القاهرة عام 2018` — no gender."""
    analysed = disambiguator.analyse("تخرجت من جامعة القاهرة عام 2018")
    digits = [t for t in analysed if t.token == "2018"]
    assert digits, "tokeniser lost 2018"
    assert not digits[0].is_cue()


# ---------------------------------------------------------------------------
# Prohibition 1 — spans index the original string
# ---------------------------------------------------------------------------


def test_char_spans_index_the_original_text(disambiguator):
    """`TaggedCue.char_span` must slice the source, not a tokenised copy.

    A span that indexes a normalised or retokenised string would silently
    misalign every cue the annotators see (spec §8.2).
    """
    text = "حاصلة على بكالوريوس هندسة"
    for token in disambiguator.analyse(text):
        assert text[token.char_start : token.char_end] == token.token


def test_ta_marbuta_survives_the_tokeniser(disambiguator):
    """Prohibition 1 — the pipeline must not fold ة anywhere."""
    text = "المرشحة المثالية تتمتع بمهارات تواصل ممتازة"
    tokens = [t.token for t in disambiguator.analyse(text)]
    assert "المرشحة" in tokens
    assert sum(t.count("ة") for t in tokens) == text.count("ة")


# ---------------------------------------------------------------------------
# Provenance — architecture §4.5
# ---------------------------------------------------------------------------


def test_versions_are_recorded(disambiguator):
    """ADR 007 — model identity travels with the data, not only a source hash."""
    assert disambiguator.toolkit_version.startswith("1.6")
    assert disambiguator.db_version == "calima-msa-r13"


# ---------------------------------------------------------------------------
# Phase 3 — twin symmetry, end to end through the real model (fixture T01)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "FINDING (register D14, 12 Aug 2026): AB4 is gender-asymmetric. "
        "حاصلة returns 34 candidates (21 gen=f, 12 gen=m) so AB4 fires; حاصل "
        "returns 19 (18 gen=m, 0 gen=f) so it does not. The twins abstain for "
        "DIFFERENT reasons — AB4 (f) vs AB1 (m) — and therefore land in "
        "different adjudication strata (spec §8.3). Structural, not a code bug: "
        "architecture §4.2 records that feminine surface forms admit masculine "
        "analyses while the converse is rare. strict=True so this test reports a "
        "failure the moment the author resolves D14 and it starts passing."
    ),
)
def test_t01_twin_symmetry_end_to_end(disambiguator):
    """T01 — `حاصلة`/`حاصل` twins, through the actual disambiguator.

    "THE MOST IMPORTANT INVARIANT IN THE SUITE" (fixture T01). The pure-layer
    test in `test_symmetry.py` uses recorded masses; this one re-measures both
    twins from text and classifies them, so a gender asymmetry introduced
    anywhere in tokenisation, analysis or scoring is caught.

    Still Tiers A/B only — Tier C is Phase 5, and Phase 6 is the binding run.
    """
    from arabgn.analysis.symmetry import check_twin_symmetry
    from arabgn.analysis.thresholds import ThresholdConfig
    from arabgn.analysis.tiers import classify
    from arabgn.contracts import Tier

    # Most robust point over the 9 measured fixtures — docs/theta-sweep.md §3.
    cfg = ThresholdConfig(theta_high=0.495, theta_low=0.285)

    text_f = "حاصلة على بكالوريوس هندسة من جامعة القاهرة"
    text_m = "حاصل على بكالوريوس هندسة من جامعة القاهرة"

    def classify_cue(text, token):
        analysed = disambiguator.analyse(text)
        match = [t for t in analysed if t.token == token]
        assert match, f"{token!r} not found in {text!r}"
        return classify(token, match[0].top_pos, match[0].candidates, cfg)

    result_f = classify_cue(text_f, "حاصلة")
    result_m = classify_cue(text_m, "حاصل")

    report = check_twin_symmetry([result_f], [result_m], label="T01")
    assert report.symmetric, report.describe()
    assert result_f.tier is Tier.B, (
        "T01's feminine twin must reach Tier B — if it resolved while the "
        "masculine abstained the instrument would be gender-asymmetric"
    )


def test_t01_full_sentence_symmetry(disambiguator):
    """Every cue in the T01 pair, not just the target token.

    A per-token check could pass while the tagger emitted a different number of
    cues overall — which is itself an asymmetry (architecture §8.2).
    """
    text_f = "حاصلة على بكالوريوس هندسة من جامعة القاهرة"
    text_m = "حاصل على بكالوريوس هندسة من جامعة القاهرة"

    cues_f = [t for t in disambiguator.analyse(text_f) if t.is_cue()]
    cues_m = [t for t in disambiguator.analyse(text_m) if t.is_cue()]

    assert len(cues_f) == len(cues_m), (
        f"cue count differs: {len(cues_f)} (f) vs {len(cues_m)} (m) — "
        f"f={[t.token for t in cues_f]} m={[t.token for t in cues_m]}"
    )
