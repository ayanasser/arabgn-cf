"""Tier A/B referent classification. Spec §5.

Pure — enters the freeze manifest.

Tier is the resolution **mechanism**, not a linguistic claim (ADR 002):

* **Tier A** — nominal cue, rationality resolves under §4.2 → lexical decision
* **Tier B** — nominal cue, rationality does not resolve → abstain (AB1)
* **Tier C** — ``verb`` / ``adj`` cue, rationality inherited by agreement

Tier C is **not implemented here**. It is Phase 5 and depends on register D7
(role test) and D8 (pro-drop), neither of which is settled. Routing to it raises
:class:`TierCNotImplemented` naming the cue and its POS, so the gap is visible in
a stack trace rather than silently mislabelled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from arabgn.analysis.cues import (
    CandidateAnalysis,
    form_divergence,
    gender_disagreement,
    rationality_mass,
)
from arabgn.analysis.thresholds import ThresholdConfig, resolve_rationality
from arabgn.contracts import AbstainTrigger, Rationality, Referent, Tier

__all__ = ["Classification", "classify", "TierCNotImplemented", "NOMINAL_POS"]

#: Spec §5 — Tier A/B apply when the cue POS is nominal.
NOMINAL_POS = frozenset({"noun", "noun_prop", "noun_quant"})

#: Spec §5 — Tier C applies when the cue carries gender by agreement.
TIER_C_POS = frozenset({"verb", "adj", "adj_comp"})


class TierCNotImplemented(NotImplementedError):
    """Raised when a cue routes to Tier C. Phase 5; blocked on D7 and D8."""


@dataclass(frozen=True, slots=True)
class Classification:
    """The tier, referent and abstain trigger for one cue.

    ``tier`` is always populated and is never re-inferred downstream —
    architecture §8.1 requires tier-wise metrics.
    """

    tier: Tier
    referent: Referent
    abstain_reason: AbstainTrigger | None
    rationality: Rationality | None
    mass: dict[Rationality, float]


def classify(
    token: str,
    pos: str | None,
    candidates: Sequence[CandidateAnalysis],
    config: ThresholdConfig,
    *,
    gen: str | None = None,
    form_gen: str | None = None,
    role_test_passes: bool | None = None,
) -> Classification:
    """Classify one cue under spec §5, Tiers A and B only.

    Parameters
    ----------
    role_test_passes:
        Spec §5.1. ``True``/``False`` if the role test has been applied,
        ``None`` if it is indeterminate — which is **AB6**, not a default to
        ``applicant``. The role test itself is register D7 and unsettled, so this
        is supplied by the caller rather than computed here.

    Raises
    ------
    TierCNotImplemented
        If the cue routes to Tier C.

    Examples
    --------
    A04 ``خبرة`` — rat=i unambiguous, not applicant-referring::

        classify("خبرة", "noun", cands, cfg).referent is Referent.NON_APPLICANT
    """
    if pos in TIER_C_POS:
        raise TierCNotImplemented(
            f"cue {token!r} (pos={pos!r}) routes to Tier C — agreement-target "
            f"resolution is Phase 5, blocked on register D7 (role test) and D8 "
            f"(pro-drop default). Not implemented; not guessed."
        )

    # AB4 / AB5 fire regardless of tier ("any" in spec §6). Checked before the
    # rationality rule because a cue whose gender is itself in doubt cannot have
    # a trustworthy referent, whatever its rationality resolves to.
    if gender_disagreement(candidates):
        return Classification(
            tier=Tier.B,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB4,
            rationality=None,
            mass=rationality_mass(candidates),
        )
    if form_divergence(gen, form_gen):
        return Classification(
            tier=Tier.B,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB5,
            rationality=None,
            mass=rationality_mass(candidates),
        )

    mass = rationality_mass(candidates)
    outcome = resolve_rationality(mass, config)

    # Tier B — lexical ambiguity, spec §5. The design's honesty mechanism: a high
    # abstention rate is an acceptable outcome and is reported, not engineered
    # away.
    if outcome.abstains:
        return Classification(
            tier=Tier.B,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB1,
            rationality=None,
            mass=mass,
        )

    # Tier A — lexical resolution, spec §5.
    if outcome.value is Rationality.I:
        return Classification(
            tier=Tier.A,
            referent=Referent.NON_APPLICANT,
            abstain_reason=None,
            rationality=Rationality.I,
            mass=mass,
        )

    # Rational. Spec §5.1: rational ≠ applicant — a job ad also refers to hiring
    # managers, teams and clients.
    if role_test_passes is None:
        return Classification(
            tier=Tier.A,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB6,
            rationality=Rationality.R,
            mass=mass,
        )
    return Classification(
        tier=Tier.A,
        referent=(
            Referent.APPLICANT if role_test_passes else Referent.NON_APPLICANT
        ),
        abstain_reason=None,
        rationality=Rationality.R,
        mass=mass,
    )
