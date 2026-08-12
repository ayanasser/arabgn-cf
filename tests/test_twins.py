"""Twin CV pair invariants. Architecture §5.2.

Every assertion here is derived from §5.2's bullet list, not from what the code
returns today. The load-bearing one is
``test_tokenization_delta_is_not_a_pass_condition``: the proposal promised a
guarantee §5.2 withdraws as unsatisfiable, and this is where that withdrawal is
enforced rather than merely documented.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.twins import (
    TwinCV,
    TwinPair,
    TwinToken,
    check_twin_pair,
    tokenization_deltas,
)

# حاصلة على بكالوريوس هندسة من جامعة القاهرة
# حاصل  على بكالوريوس هندسة من جامعة القاهرة
#
# The pair differs in exactly one token, the active participle, which is the
# alternation the generator declares. Everything else is identical.
FEMALE_TOKENS = ("حاصلة", "على", "بكالوريوس", "هندسة", "من", "جامعة", "القاهرة")
MALE_TOKENS = ("حاصل", "على", "بكالوريوس", "هندسة", "من", "جامعة", "القاهرة")

POS = ("noun", "prep", "noun", "noun", "prep", "noun", "noun_prop")

SLOTS = {
    "degree": "بكالوريوس",
    "field": "هندسة",
    "institution": "جامعة القاهرة",
    "years": "5",
}

PARTICIPLE = ("حاصل", "حاصلة")


def cv(tokens, slots=None, text=None):
    return TwinCV(
        text=text if text is not None else " ".join(tokens),
        tokens=tuple(
            TwinToken(surface=s, pos=p) for s, p in zip(tokens, POS)
        ),
        slots=dict(SLOTS if slots is None else slots),
    )


def pair(female_tokens=FEMALE_TOKENS, male_tokens=MALE_TOKENS, **over):
    return TwinPair(
        female=over.pop("female", cv(female_tokens, over.pop("female_slots", None))),
        male=over.pop("male", cv(male_tokens, over.pop("male_slots", None))),
        declared_alternations=over.pop(
            "declared", frozenset({PARTICIPLE})
        ),
    )


# ---------------------------------------------------------------------------
# The four enforced invariants (architecture §5.2)
# ---------------------------------------------------------------------------


def test_a_well_formed_pair_satisfies_every_invariant():
    report = check_twin_pair(pair(), char_tolerance=2)
    assert report.satisfied, report.explain()


def test_identical_content_word_count_is_required():
    """§5.2 bullet 1. An extra content word is extra information, not gender."""
    longer = FEMALE_TOKENS + ("ممتازة",)
    female = TwinCV(
        text=" ".join(longer),
        tokens=tuple(
            TwinToken(s, p) for s, p in zip(longer, POS + ("adj",))
        ),
        slots=dict(SLOTS),
    )
    report = check_twin_pair(
        TwinPair(female=female, male=cv(MALE_TOKENS),
                 declared_alternations=frozenset({PARTICIPLE})),
        char_tolerance=100,
    )
    assert not report.content_word_count_equal
    assert not report.satisfied
    assert "content-word count" in report.explain()


def test_identical_qualification_slots_are_required():
    """§5.2 bullet 2. A pair that also varies the degree is not a gender contrast."""
    report = check_twin_pair(
        pair(male_slots={**SLOTS, "degree": "ماجستير"}), char_tolerance=2
    )
    assert not report.slots_identical
    assert report.differing_slots == ("degree",)
    assert not report.satisfied


def test_character_length_tolerance_must_be_declared():
    """§5.2 bullet 3 says "within a **declared** tolerance".

    No default, for the same reason θ has none: a default is an undeclared
    parameter that still ends up in the freeze.
    """
    with pytest.raises(TypeError):
        check_twin_pair(pair())  # type: ignore[call-arg]


def test_character_length_delta_outside_the_tolerance_fails():
    report = check_twin_pair(pair(), char_tolerance=0)
    assert report.char_delta == 1  # حاصلة is one character longer than حاصل
    assert not report.within_char_tolerance
    assert not report.satisfied


def test_a_negative_tolerance_is_refused():
    with pytest.raises(ValueError, match="char_tolerance"):
        check_twin_pair(pair(), char_tolerance=-1)


def test_undeclared_lexical_difference_fails_the_pair():
    """§5.2 bullet 5 — "zero difference in any non-gender lexical item".

    The institution is swapped between twins. Because that alternation was never
    declared, it must surface rather than hide behind the participle change that
    *was* declared.
    """
    swapped = MALE_TOKENS[:-1] + ("الإسكندرية",)
    report = check_twin_pair(
        pair(male_tokens=swapped), char_tolerance=100
    )
    assert not report.satisfied
    assert [d[1:] for d in report.undeclared_differences] == [
        ("الإسكندرية", "القاهرة")
    ]


def test_a_declared_alternation_is_not_a_violation():
    """The whole point: the pair *must* differ in gender morphology."""
    report = check_twin_pair(pair(), char_tolerance=2)
    assert report.undeclared_differences == ()


def test_an_undeclared_gender_alternation_still_fails():
    """Declaring one alternation does not license another.

    A generator that also varied a verb without declaring it has changed the
    text in a way nobody reviewed, even though the change is gender morphology.
    """
    report = check_twin_pair(pair(declared=frozenset()), char_tolerance=2)
    assert not report.satisfied
    assert report.undeclared_differences[0][1:] == ("حاصل", "حاصلة")


def test_unalignable_pairs_are_reported_rather_than_diffed():
    """Different token counts make a positional diff meaningless.

    Reporting an empty diff would read as "no lexical leakage" on a pair nobody
    checked.
    """
    report = check_twin_pair(
        pair(male_tokens=MALE_TOKENS[:-1]), char_tolerance=100
    )
    assert not report.alignable
    assert not report.satisfied
    assert "no position-by-position diff" in report.explain()


# ---------------------------------------------------------------------------
# The withdrawn guarantee (architecture §5.2)
# ---------------------------------------------------------------------------


def test_tokenization_delta_is_not_a_pass_condition():
    """The proposal's "refuses to emit a pair differing in token count" is
    withdrawn by §5.2 as unsatisfiable — حاصل/حاصلة differ under every subword
    tokenizer in the audit set.

    A non-zero delta must therefore leave a valid pair valid. Forcing it to zero
    would mean padding, which is itself a confound.
    """
    twins = pair()
    deltas = tokenization_deltas(
        twins, {"e5-large": lambda text: text.split()}
    )
    report = check_twin_pair(twins, char_tolerance=2)
    assert report.satisfied
    assert "tokeniz" not in report.explain()
    assert deltas == {"e5-large": 0}


def test_tokenization_delta_is_measured_per_audit_subject():
    """§5.2 — "per audit subject". Subjects tokenize differently, so one number
    for a pair would be a fiction."""
    deltas = tokenization_deltas(
        pair(),
        {
            "subword": lambda text: list(text),          # characters
            "whitespace": lambda text: text.split(),
        },
    )
    assert deltas["subword"] == 1  # حاصلة carries one more character
    assert deltas["whitespace"] == 0


def test_tokenization_delta_is_signed():
    """The sign is the finding.

    A subject that consistently makes feminine CVs longer is one where length and
    gender are confounded; an absolute value would hide the direction.
    """
    deltas = tokenization_deltas(pair(), {"chars": lambda text: list(text)})
    assert deltas["chars"] > 0

    reversed_pair = TwinPair(
        female=cv(MALE_TOKENS), male=cv(FEMALE_TOKENS),
        declared_alternations=frozenset({PARTICIPLE}),
    )
    assert tokenization_deltas(reversed_pair, {"chars": lambda t: list(t)})[
        "chars"
    ] < 0


def test_deltas_are_returned_in_sorted_subject_order():
    """Prohibition 6 — output order must not depend on dict insertion order."""
    deltas = tokenization_deltas(
        pair(),
        {
            "zebra": lambda text: text.split(),
            "alpha": lambda text: text.split(),
            "middle": lambda text: text.split(),
        },
    )
    assert list(deltas) == ["alpha", "middle", "zebra"]


# ---------------------------------------------------------------------------
# Prohibition 1
# ---------------------------------------------------------------------------


def test_the_checker_never_alters_arabic():
    """Ta-marbuta is the signal. Nothing here may fold it.

    The check is over surfaces the caller supplied, so a report that quotes an
    altered form would mean this module rewrote the text.
    """
    report = check_twin_pair(pair(declared=frozenset()), char_tolerance=2)
    _, male_surface, female_surface = report.undeclared_differences[0]
    assert female_surface == "حاصلة"
    assert female_surface.count("ة") == 1
    assert male_surface == "حاصل"
