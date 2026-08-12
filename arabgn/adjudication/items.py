"""What an annotator sees, and what they answer. Spec §8.1, §8.2.

:class:`AnnotationItem` is deliberately minimal. It carries the sentence, the cue
span and the document type — and **nothing else**. There is no field for the
tagger's prediction, its tier, or its abstain status, so no display path can leak
them (spec §8.2).

:func:`blind` builds an item from a ``TaggedCue`` and drops everything else on the
floor.
"""

from __future__ import annotations

from dataclasses import dataclass

from arabgn.contracts import DocType, TaggedCue

__all__ = [
    "AnnotationItem",
    "AnnotationResponse",
    "VALID_ANSWERS",
    "blind",
    "FORBIDDEN_FIELDS",
]

#: Spec §8.1. `unclear` is a valid answer, recorded as itself and never coerced.
VALID_ANSWERS = ("applicant", "non_applicant", "unclear")

#: Fields that must never reach an annotator (spec §8.2). Asserted by the test
#: suite against `AnnotationItem`'s actual fields, so adding one to the dataclass
#: fails the build rather than silently contaminating the estimates.
FORBIDDEN_FIELDS = (
    "referent",
    "tier",
    "abstain_reason",
    "rat_candidates",
    "morph_class",
    "pos",
    "gen",
    "form_gen",
    "head_token",
)


@dataclass(frozen=True, slots=True)
class AnnotationItem:
    """One cue presented for blind annotation.

    Exactly what spec §8.2 permits: "The full sentence, the cue highlighted, and
    the document type."
    """

    #: Opaque handle. Deliberately not the `cue_id` — see :func:`blind`.
    item_id: str
    sentence: str
    cue_start: int
    cue_end: int
    doc_type: DocType

    @property
    def cue(self) -> str:
        return self.sentence[self.cue_start : self.cue_end]

    def render(self, marker: str = "«»") -> str:
        """The sentence with the cue delimited, for display.

        Uses guillemets by default because they do not occur in Arabic
        recruitment text and so cannot be confused with source punctuation.
        """
        open_mark, close_mark = marker[0], marker[1]
        return (
            self.sentence[: self.cue_start]
            + open_mark
            + self.cue
            + close_mark
            + self.sentence[self.cue_end :]
        )


@dataclass(frozen=True, slots=True)
class AnnotationResponse:
    """One recorded answer. Append-only; never updated in place.

    ``annotator_id`` is stable across sessions so κ can be computed per pair.
    ``timestamp`` is ISO-8601 UTC.

    Prohibition 6 note: the timestamp is provenance only. It must never enter a
    derived value that feeds the freeze hash — it is recorded *about* the
    annotation, not used *in* any computation.
    """

    item_id: str
    annotator_id: str
    answer: str
    timestamp: str
    #: Free-text, optional. Never parsed into a label.
    comment: str | None = None

    def __post_init__(self) -> None:
        if self.answer not in VALID_ANSWERS:
            raise ValueError(
                f"answer {self.answer!r} is not one of {VALID_ANSWERS}. "
                f"`unclear` is a valid answer and must be recorded as itself, "
                f"never coerced to a label (spec §8.1)."
            )
        if not self.annotator_id:
            raise ValueError("annotator_id is required and must be stable")


def blind(cue: TaggedCue, item_id: str, doc_type: DocType) -> AnnotationItem:
    """Build a blind annotation item from a tagged cue.

    Everything the tagger decided — tier, referent, abstain trigger,
    ``rat_candidates``, ``morph_class``, POS — is discarded here and cannot be
    recovered from the returned item. The ``item_id`` is supplied by the caller
    rather than taken from ``cue.cue_id``, so that a leak through an
    id-to-prediction lookup requires a deliberate join against the sampling
    manifest rather than happening by default.

    ``doc_type`` is a required argument, not read from the cue: ``TaggedCue``
    carries ``doc_id``, not ``doc_type``, so the caller must resolve it from the
    corresponding :class:`~arabgn.contracts.DocRecord`. Spec §8.2 permits showing
    it, and Tier C pro-drop makes it meaningful to the annotator.
    """
    return AnnotationItem(
        item_id=item_id,
        sentence=cue.sentence_context,
        cue_start=cue.char_span[0],
        cue_end=cue.char_span[1],
        doc_type=doc_type,
    )
