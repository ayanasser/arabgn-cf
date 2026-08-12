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

from arabgn.analysis.agreement_target import (
    TargetCandidate,
    VerbBranchNotImplemented,
    find_agreement_target,
)
from arabgn.analysis.cues import (
    CandidateAnalysis,
    dominant_gender,
    form_divergence,
    gender_disagreement,
    rationality_mass,
)
from arabgn.analysis.thresholds import ThresholdConfig, resolve_rationality
from arabgn.contracts import AbstainTrigger, Rationality, Referent, Tier

__all__ = [
    "Classification",
    "classify",
    "TierCNotImplemented",
    "NOMINAL_POS",
    "TIER_C_POS",
]

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
    #: For Tiers A and B this is the cue's own rationality mass. For **Tier C it
    #: is the agreement target's**, because that is what the decision was made on
    #: — a Tier C cue carries ``rat = n`` and its own mass says nothing.
    mass: dict[Rationality, float]
    #: Tier C only: the agreement target whose rationality was inherited.
    head_token: str | None = None


def classify(
    token: str,
    pos: str | None,
    candidates: Sequence[CandidateAnalysis],
    config: ThresholdConfig,
    *,
    gen: str | None = None,
    form_gen: str | None = None,
    role_test_passes: bool | None = None,
    cue_index: int | None = None,
    tokens: Sequence[TargetCandidate] | None = None,
) -> Classification:
    """Classify one cue under spec §5, Tiers A and B only.

    Parameters
    ----------
    role_test_passes:
        Spec §5.1. ``True``/``False`` if the role test has been applied,
        ``None`` if it is indeterminate — which is **AB6**, not a default to
        ``applicant``. The role test itself is register D7 and unsettled, so this
        is supplied by the caller rather than computed here.
    cue_index, tokens:
        The cue's position in its sentence and the sentence's tokens. Required
        for Tier C, which resolves by agreement and therefore cannot see enough
        from the cue alone. Ignored for Tiers A and B.

    Raises
    ------
    TierCNotImplemented
        If the cue routes to Tier C and no sentence context was supplied.
    VerbBranchNotImplemented
        For verb cues. The subject may be pro-dropped and the default by document
        type is register D8, unsettled.

    Examples
    --------
    A04 ``خبرة`` — rat=i unambiguous, not applicant-referring::

        classify("خبرة", "noun", cands, cfg).referent is Referent.NON_APPLICANT
    """
    # AB4 / AB5 fire regardless of tier ("any" in spec §6). Checked before tier
    # routing because a cue whose gender is itself in doubt cannot have a
    # trustworthy referent, whatever mechanism would have resolved it. The tier
    # still tracks the mechanism the cue *would* have used, so an adjective that
    # abstains on gender is Tier C and not Tier B — tier is a property of the cue
    # (ADR 002), not of the trigger that stopped it.
    abstaining_tier = Tier.C if pos in TIER_C_POS else Tier.B

    if gender_disagreement(candidates):
        return Classification(
            tier=abstaining_tier,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB4,
            rationality=None,
            mass=rationality_mass(candidates),
        )
    if form_divergence(gen, form_gen):
        return Classification(
            tier=abstaining_tier,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB5,
            rationality=None,
            mass=rationality_mass(candidates),
        )

    if pos in TIER_C_POS:
        return _classify_tier_c(
            token,
            pos,
            candidates,
            config,
            gen=gen,
            role_test_passes=role_test_passes,
            cue_index=cue_index,
            tokens=tokens,
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


def _classify_tier_c(
    token: str,
    pos: str | None,
    candidates: Sequence[CandidateAnalysis],
    config: ThresholdConfig,
    *,
    gen: str | None,
    role_test_passes: bool | None,
    cue_index: int | None,
    tokens: Sequence[TargetCandidate] | None,
) -> Classification:
    """Spec §5, Tier C — inherit rationality from the agreement target.

    The four-step procedure, in order:

    1. Identify the agreement target (:mod:`arabgn.analysis.agreement_target`).
    2. Resolve *that token's* rationality by Tier A rules.
    3. Inherit — the cue is applicant-referring iff its target is.
    4. Abstain if the target cannot be identified, or itself abstains.

    **D7 does not block step 3 when the target is irrational.** The role test only
    applies to *rational* cues (spec §5.1), so ``خبرة واسعة`` resolves to
    ``non_applicant`` with no author decision needed — the target ``خبرة`` is
    ``rat=i`` and adjectives inherit. That is the majority case in real
    advertisements, and it is why the adjective branch is worth wiring now rather
    than waiting for D7.

    When the target *is* rational, the role test applies exactly as it does in
    Tier A, so an unsettled D7 yields AB6 rather than a guess.
    """
    if cue_index is None or tokens is None:
        raise TierCNotImplemented(
            f"cue {token!r} (pos={pos!r}) routes to Tier C, which resolves by "
            f"agreement and so cannot be decided from the cue alone — pass "
            f"`cue_index` and `tokens`. The verb branch stays blocked on "
            f"register D8 (pro-drop) and the role test on D7."
        )

    cue_gender = gen
    if cue_gender is None:
        dominant = dominant_gender(candidates)
        cue_gender = None if dominant is None else dominant.value

    # Propagates VerbBranchNotImplemented for verbs — D8.
    resolution = find_agreement_target(cue_index, pos, cue_gender, tokens)

    if not resolution.resolved:
        # Step 4a — no target. AB2, with the search's own explanation.
        return Classification(
            tier=Tier.C,
            referent=Referent.ABSTAIN,
            abstain_reason=resolution.abstain_reason or AbstainTrigger.AB2,
            rationality=None,
            mass={},
        )

    target = resolution.target
    assert target is not None  # implied by `resolved`

    if not target.candidates:
        # The caller supplied a target with no analyses, so its rationality
        # cannot be resolved. That is AB3 — the target does not resolve — rather
        # than an assumption that it is irrational.
        return Classification(
            tier=Tier.C,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB3,
            rationality=None,
            mass={},
            head_token=target.token,
        )

    # Step 2 — the target's rationality, by the same §4.2 rule Tier A/B uses.
    target_mass = rationality_mass(target.candidates)
    outcome = resolve_rationality(target_mass, config)

    if outcome.abstains:
        # Step 4b — AB3, "agreement target itself abstains" (spec §6).
        return Classification(
            tier=Tier.C,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB3,
            rationality=None,
            mass=target_mass,
            head_token=target.token,
        )

    # Step 3 — inherit.
    if outcome.value is Rationality.I:
        # `خبرة واسعة` — the experience is feminine and is not a person.
        return Classification(
            tier=Tier.C,
            referent=Referent.NON_APPLICANT,
            abstain_reason=None,
            rationality=Rationality.I,
            mass=target_mass,
            head_token=target.token,
        )

    # Target is rational, so the role test applies to it exactly as in Tier A.
    if role_test_passes is None:
        return Classification(
            tier=Tier.C,
            referent=Referent.ABSTAIN,
            abstain_reason=AbstainTrigger.AB6,
            rationality=Rationality.R,
            mass=target_mass,
            head_token=target.token,
        )
    return Classification(
        tier=Tier.C,
        referent=(
            Referent.APPLICANT if role_test_passes else Referent.NON_APPLICANT
        ),
        abstain_reason=None,
        rationality=Rationality.R,
        mass=target_mass,
        head_token=target.token,
    )
