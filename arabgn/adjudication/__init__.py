"""Adjudication tooling. I/O layer — does **not** enter the freeze.

Pure logic used by this package lives under ``arabgn/analysis/``:
:mod:`arabgn.analysis.sampling`, :mod:`arabgn.analysis.agreement`,
:mod:`arabgn.analysis.thresholds` (ADR 007).

Blindness is structural, not procedural
---------------------------------------
Spec §8.2: annotators see the sentence, the highlighted cue and the document type,
and **not** the tagger's prediction, tier, or abstain status. "Blind annotation is
required or precision estimates are contaminated."

That is enforced by :class:`~arabgn.adjudication.items.AnnotationItem` simply not
having fields for prediction, tier or abstain status — so there is no code path
that could show them, accidental or otherwise. A convention that says "don't
display these" is one careless template away from breaking; a type that cannot
carry them is not.
"""
