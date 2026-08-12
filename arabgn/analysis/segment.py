"""Sentence segmentation, for cue *display context* only. Spec §8.2.

Pure — enters the freeze manifest, because :attr:`TaggedCue.sentence_context` is
part of the output contract (architecture §4.5) and is what an annotator reads.

What this is not used for
-------------------------
**The disambiguator is not run on these segments.** It runs over the whole
document, so every cue is analysed with the maximum context available. Verified
12 Aug 2026: CAMeL Tools returns one analysed token per input token on an
855-token advertisement with no truncation and no empty candidate lists, so there
is no length ceiling to segment around.

That separation is deliberate. Routing segments through the disambiguator would
make every rationality mass in the study depend on where a full stop was guessed.

**But segmentation is not display-only, and this claim was weakened on 13 August
2026.** When Tier C's adjective branch was wired up, the agreement search was
bounded to the cue's segment — ``punc`` is skippable when looking back for a
head, so an unbounded search lets a sentence-initial adjective attach to the
previous sentence's noun. A boundary in the wrong place therefore changes which
head an adjective can reach, and so changes a Tier C label.

It does not change any rationality mass, and it cannot affect Tiers A or B. But
"cannot move a measurement" is no longer true, and **register D15 is
correspondingly more than a formality** — the boundary set is a stated default,
not a settled decision.

Boundary rule
-------------
A boundary falls at a line break, and after a run of terminal punctuation. Runs
are consumed together so ``!!!`` is one boundary rather than three empty
segments. Terminal punctuation stays with the sentence it ends, because an
annotator judging whether a cue refers to the applicant benefits from seeing that
the sentence was a question.

The Arabic comma ``،`` is deliberately **not** a boundary. It is a comma, and job
advertisements use it inside lists of requirements that belong to one sentence.

Offsets index the string passed in, so a cue's ``char_span`` can be mapped to its
segment without re-tokenising (:func:`segment_for_span`).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Segment", "TERMINATORS", "LINE_BREAKS", "segment", "segment_for_span"]

#: Sentence-final punctuation. ``؟`` is the Arabic question mark and ``؛`` the
#: Arabic semicolon; both are ASCII-distinct code points and both end a clause in
#: recruitment text. ``،`` (Arabic comma) is excluded — see the module docstring.
TERMINATORS = frozenset(".!?؟؛…•")

#: Advertisements are heavily line-broken, and a line break is a stronger
#: boundary than any punctuation in this register — bullet lists frequently carry
#: no terminal punctuation at all.
#:
#: Written as escapes rather than literal characters, because U+2028 and U+2029
#: are invisible in most editors and an ordinary space pasted in here by accident
#: would make every word its own segment — silently, since each "sentence" would
#: still be a valid slice of the source. Asserted by ``test_segment.py``.
LINE_BREAKS = frozenset("\n\r\u2028\u2029")


@dataclass(frozen=True, slots=True)
class Segment:
    """One display sentence and its offsets into the source string."""

    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end - self.start != len(self.text):
            raise ValueError(
                f"segment offsets {(self.start, self.end)} do not match text of "
                f"length {len(self.text)} — offsets must index the source string"
            )


def _emit(out: list[Segment], text: str, start: int, end: int) -> None:
    """Append ``text[start:end]`` stripped of surrounding whitespace.

    Offsets are advanced to match the strip, so :attr:`Segment.text` always
    equals ``source[start:end]``. Whitespace-only spans produce nothing.
    """
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        out.append(Segment(text=text[start:end], start=start, end=end))


def segment(text: str) -> tuple[Segment, ...]:
    """Split ``text`` into display sentences.

    Deterministic and total: a pure scan with no regular expressions, no locale
    dependence and no randomness (prohibition 6).

    Characters are never altered — every segment is a literal slice of the input,
    so ta-marbuta and diacritics pass through untouched (prohibition 1). Only
    whitespace and line breaks are dropped, and only from between segments.

    Examples
    --------
    >>> [s.text for s in segment("مطلوب مهندس. خبرة واسعة")]
    ['مطلوب مهندس.', 'خبرة واسعة']
    >>> [s.text for s in segment("مطلوبة مهندسة\\n- خبرة سنتين")]
    ['مطلوبة مهندسة', '- خبرة سنتين']
    """
    out: list[Segment] = []
    start = 0
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        if char in TERMINATORS:
            end = index + 1
            while end < length and text[end] in TERMINATORS:
                end += 1
            _emit(out, text, start, end)
            index = start = end
        elif char in LINE_BREAKS:
            _emit(out, text, start, index)
            index += 1
            start = index
        else:
            index += 1

    _emit(out, text, start, length)
    return tuple(out)


def segment_for_span(
    segments: tuple[Segment, ...], start: int, end: int
) -> Segment | None:
    """The segment wholly containing ``[start, end)``, or ``None``.

    ``None`` is returned rather than a best-effort match when a span straddles a
    boundary — which happens when a token contains terminal punctuation, as in an
    abbreviation. Callers count those and report the count; guessing a segment
    would show an annotator a sentence the cue is not in.
    """
    for candidate in segments:
        if candidate.start <= start and end <= candidate.end:
            return candidate
    return None
