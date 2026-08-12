"""Tier C agreement-target identification — **adjective branch only**.

Pure — enters the freeze manifest.

Spec §5 Tier C: a cue carrying gender by *agreement* (``rat = n``) inherits its
rationality from its agreement target — the modified head noun for an adjective,
the subject for a verb.

Scope, and why it stops here
----------------------------
**Implemented:** the adjective branch. In MSA an attributive adjective *follows*
its head noun and agrees with it in gender, number, definiteness and case, so the
target is recoverable by adjacency plus an agreement check. Fixtures C01, C02 and
C03 are all settled adjective cases.

**Not implemented:** the verb branch. Arabic is pro-drop — ``تخرجت من جامعة
القاهرة`` has no overt subject — and the default is register **D8**, which is an
open author decision. Fixtures C05, C06 and C07 all depend on it and are all
``REVIEW``. :func:`find_agreement_target` raises for verbs rather than guessing.

No parser is used, and none is available
----------------------------------------
CAMeL Tools 1.6 ships morphology, disambiguation, NER, sentiment and dialect ID —
**no dependency parser** (verified 12 Aug 2026). Adding one would be a new
dependency and a project decision (prohibition 5). Adjacency is therefore not a
shortcut around a parser; it is the available method, and its failure modes are
declared below rather than discovered later.

Known limits of adjacency
-------------------------
* **Coordination** — ``خبرة واسعة وعميقة``: the second adjective's head is two
  positions back. Handled by skipping conjunctions.
* **Intervening modifiers** — ``مهارات تواصل ممتازة`` (fixture C04): does
  ``ممتازة`` attach to ``مهارات`` or ``تواصل``? Both are feminine, so agreement
  cannot separate them. C04 is ``REVIEW`` for exactly this reason, and
  :class:`TargetResolution` reports ``ambiguous`` rather than picking one.
* **Predicative adjectives** — the head may precede at a distance, or be a
  pro-dropped subject. Reported as unresolved → **AB2**.

Every unresolved case abstains under AB2 (spec §6). That is the honest outcome:
architecture §8.1 warns "Tier C will be weakest and hiding that is not
defensible."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from arabgn.analysis.cues import CandidateAnalysis
from arabgn.contracts import AbstainTrigger, Gender

__all__ = [
    "TargetCandidate",
    "TargetResolution",
    "find_agreement_target",
    "VerbBranchNotImplemented",
    "NOMINAL_HEAD_POS",
    "SKIPPABLE_POS",
]

#: A head an adjective can modify.
NOMINAL_HEAD_POS = frozenset({"noun", "noun_prop", "noun_quant"})

#: Tokens an adjective may look past when searching backwards for its head.
#: Conjunctions handle coordination (``واسعة وعميقة``); adjectives handle
#: adjective stacking (``المرشحة المثالية الممتازة``).
SKIPPABLE_POS = frozenset({"conj", "adj", "punc"})


class VerbBranchNotImplemented(NotImplementedError):
    """Raised for verb cues. Blocked on register D8 (pro-drop default)."""


@dataclass(frozen=True, slots=True)
class TargetCandidate:
    """One token considered as a possible agreement target."""

    index: int
    token: str
    pos: str | None
    gen: str | None
    candidates: tuple[CandidateAnalysis, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetResolution:
    """The outcome of looking for an agreement target.

    ``target`` is ``None`` whenever the cue must abstain; ``abstain_reason`` then
    says which trigger fired, and ``reason`` says why in words.
    """

    target: TargetCandidate | None
    abstain_reason: AbstainTrigger | None
    reason: str
    ambiguous_between: tuple[TargetCandidate, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.target is not None


def find_agreement_target(
    cue_index: int,
    cue_pos: str | None,
    cue_gen: str | None,
    tokens: Sequence[TargetCandidate],
) -> TargetResolution:
    """Find the head noun an adjective cue agrees with. Spec §5, Tier C step 1.

    Searches **backwards** from the cue, because MSA attributive adjectives follow
    their head. Conjunctions and other adjectives are skipped; the first nominal
    that agrees in gender is the target.

    Raises
    ------
    VerbBranchNotImplemented
        For verb cues — the subject may be pro-dropped and the default is
        register D8, unsettled.

    Examples
    --------
    C01 — ``خبرة واسعة``: ``واسعة`` (f, adj) → ``خبرة`` (f, noun).
    C02 — ``شركة كبيرة``: ``كبيرة`` → ``شركة``.
    C03 — ``المرشحة المثالية``: ``المثالية`` → ``المرشحة``.
    """
    if cue_pos in ("verb",):
        raise VerbBranchNotImplemented(
            f"verb cue at index {cue_index} — the subject may be pro-dropped "
            f"(spec §5.2) and the default by document type is register D8, "
            f"which is unsettled. Fixtures C05/C06/C07 all depend on it and are "
            f"REVIEW. Not implemented; not guessed."
        )
    if cue_pos not in ("adj", "adj_comp"):
        raise ValueError(
            f"find_agreement_target is the Tier C adjective branch; got "
            f"pos={cue_pos!r}. Nominal cues resolve lexically (Tier A/B)."
        )
    if cue_index <= 0:
        return TargetResolution(
            target=None,
            abstain_reason=AbstainTrigger.AB2,
            reason=(
                "adjective is sentence-initial, so no preceding head noun "
                "exists; MSA attributive adjectives follow their head"
            ),
        )

    agreeing: list[TargetCandidate] = []

    for index in range(cue_index - 1, -1, -1):
        token = tokens[index]

        if token.pos in NOMINAL_HEAD_POS:
            if token.gen == cue_gen and cue_gen in ("m", "f"):
                agreeing.append(token)
                # Look one step further for a same-gender competitor — this is
                # the C04 situation (`مهارات تواصل ممتازة`).
                if index - 1 >= 0:
                    previous = tokens[index - 1]
                    if (
                        previous.pos in NOMINAL_HEAD_POS
                        and previous.gen == cue_gen
                    ):
                        agreeing.append(previous)
                break
            # A nominal that does NOT agree blocks the search: it stands between
            # the adjective and any earlier head, and Arabic agreement would not
            # reach past it.
            return TargetResolution(
                target=None,
                abstain_reason=AbstainTrigger.AB2,
                reason=(
                    f"nearest preceding nominal {token.token!r} does not agree "
                    f"in gender (head={token.gen}, cue={cue_gen}); no target "
                    f"is recoverable by adjacency"
                ),
            )

        if token.pos not in SKIPPABLE_POS:
            return TargetResolution(
                target=None,
                abstain_reason=AbstainTrigger.AB2,
                reason=(
                    f"search blocked by {token.token!r} (pos={token.pos}); "
                    f"only conjunctions, adjectives and punctuation may be "
                    f"skipped when looking back for a head"
                ),
            )

    if not agreeing:
        return TargetResolution(
            target=None,
            abstain_reason=AbstainTrigger.AB2,
            reason="no agreeing nominal head found before the adjective",
        )

    if len(agreeing) > 1:
        return TargetResolution(
            target=None,
            abstain_reason=AbstainTrigger.AB2,
            reason=(
                f"two same-gender nominals compete for attachment: "
                f"{agreeing[0].token!r} and {agreeing[1].token!r}. Agreement "
                f"cannot separate them and no parser is available, so this "
                f"abstains rather than guessing (cf. fixture C04, REVIEW)"
            ),
            ambiguous_between=tuple(agreeing),
        )

    return TargetResolution(
        target=agreeing[0],
        abstain_reason=None,
        reason=(
            f"nearest preceding nominal {agreeing[0].token!r} agrees in gender "
            f"({cue_gen}); MSA attributive adjectives follow their head"
        ),
    )
