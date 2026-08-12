"""Disambiguator wrapper. I/O — not frozen (ADR 007).

Configuration is settled in CLAUDE.md and must not be revisited:

======================  ==========================================
Disambiguator           ``BERTUnfactoredDisambiguator``, **not** MLE
Morphology DB           ``calima-msa-r13``
Candidate retention     ``top=100``, **never** the default
======================  ==========================================

Why ``top=100`` is load-bearing
-------------------------------
The default returns top-1. With a single candidate analysis, "candidates disagree
on rationality" can never fire, so the Tier B abstain mechanism is destroyed
entirely and every ambiguous cue is silently resolved. Verified: ``حاصلة``
returns **34** scored analyses at ``top=100`` in ``مطلوبة مهندسة برمجيات حاصلة
على بكالوريوس هندسة``, spanning ``rat ∈ {i, r}``. At top-1 it returns ``rat=i``,
which is wrong for that sentence (spec §4.1).

Why BERT and not MLE
--------------------
MLE misgenders ``مهندسة`` as masculine and ``تخرج`` as feminine; BERT gets both
right. Fixture C07 is a regression test against switching back.

Dataset naming
--------------
``camel_data -i`` takes ``morphology-db-msa-r13``; the Python API takes
``calima-msa-r13``. Passing the download name to ``MorphologyDB.builtin_db``
raises ``KeyError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from arabgn.analysis.cues import (
    CandidateAnalysis,
    carries_gender,
    dominant_gender,
    is_cue_pos,
)

__all__ = [
    "TOP_N",
    "DB_NAME",
    "DOWNLOAD_NAME",
    "AnalysedToken",
    "Disambiguator",
    "load_disambiguator",
]

#: CLAUDE.md "Toolkit decisions". Load-bearing — see the module docstring.
TOP_N = 100

#: Python API name. Not the same as the download name.
DB_NAME = "calima-msa-r13"

#: ``camel_data -i`` package name.
DOWNLOAD_NAME = "morphology-db-msa-r13"


@dataclass(frozen=True, slots=True)
class AnalysedToken:
    """One token with its candidate analyses, reduced to pure data.

    This is the boundary object: everything downstream of it is pure and
    model-free (ADR 007).
    """

    token: str
    index: int
    char_start: int
    char_end: int
    candidates: tuple[CandidateAnalysis, ...]

    @property
    def top_pos(self) -> str | None:
        return self.candidates[0].pos if self.candidates else None

    @property
    def top_stemcat(self) -> str | None:
        return self.candidates[0].stemcat if self.candidates else None

    def is_cue(self) -> bool:
        """Spec §2 — a content-POS token whose analysis carries ``gen ∈ {m,f}``.

        Guarded by N01 (``على``, a preposition) and N02 (``2018``, a digit).
        """
        if not is_cue_pos(self.top_pos):
            return False
        return any(carries_gender(c.gen) for c in self.candidates)

    def gender(self):
        return dominant_gender(self.candidates)


class Disambiguator:
    """Thin wrapper over ``BERTUnfactoredDisambiguator``.

    Deterministic: verified byte-identical rationality mass across three runs
    including model reload, on CPU, single process (register D13). Re-verify on
    the hardware doing the real sweep — GPU kernel nondeterminism is the usual
    failure mode.
    """

    def __init__(self, model=None, top: int = TOP_N) -> None:
        if top != TOP_N:
            raise ValueError(
                f"top={top} but CLAUDE.md settles top={TOP_N}. The default "
                f"(top-1) destroys the Tier B abstain mechanism: with one "
                f"candidate, rationality can never disagree with itself."
            )
        self._model = model if model is not None else _load_model(top)
        self.top = top

    @property
    def toolkit_version(self) -> str:
        import camel_tools

        return camel_tools.__version__

    @property
    def db_version(self) -> str:
        return DB_NAME

    def analyse(self, text: str) -> tuple[AnalysedToken, ...]:
        """Disambiguate ``text`` over the **full sentence**.

        Out-of-context analysis is insufficient — architecture §4.2: "feminine
        surface forms frequently return both masculine and feminine analyses out
        of context... the disambiguator must run over full sentences."

        Character spans are recovered by scanning forward through ``text``, so
        ``TaggedCue.char_span`` indexes the original string rather than a
        tokenised copy.
        """
        from camel_tools.tokenizers.word import simple_word_tokenize

        tokens = simple_word_tokenize(text)
        disambiguated = self._model.disambiguate(tokens)

        out: list[AnalysedToken] = []
        cursor = 0
        for index, word in enumerate(disambiguated):
            start = text.find(word.word, cursor)
            if start < 0:  # tokeniser altered the surface form
                start = cursor
            end = start + len(word.word)
            cursor = end
            out.append(
                AnalysedToken(
                    token=word.word,
                    index=index,
                    char_start=start,
                    char_end=end,
                    candidates=tuple(
                        CandidateAnalysis(
                            score=float(scored.score),
                            pos=scored.analysis.get("pos"),
                            rat=scored.analysis.get("rat"),
                            gen=scored.analysis.get("gen"),
                            form_gen=scored.analysis.get("form_gen"),
                            stemcat=scored.analysis.get("stemcat"),
                        )
                        for scored in word.analyses
                    ),
                )
            )
        return tuple(out)


@lru_cache(maxsize=1)
def _load_model(top: int):
    """Load once per process. Cached because loading is seconds, not milliseconds.

    The cache is keyed on ``top`` and holds a read-only model, so it introduces no
    cross-run state — prohibition 6 is about output varying, and this cannot
    change any output.
    """
    from camel_tools.disambig.bert import BERTUnfactoredDisambiguator

    return BERTUnfactoredDisambiguator.pretrained("msa", top=top)


def load_disambiguator(top: int = TOP_N) -> Disambiguator:
    """Load the settled configuration.

    Raises ``FileNotFoundError`` under ``~/.camel_tools/data/`` if the
    ``camel_data`` step was skipped. Run it — do not switch toolkits to work
    around it (CLAUDE.md).
    """
    return Disambiguator(top=top)
