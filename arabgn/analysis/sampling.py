"""Stratified sampling for adjudication. Spec §8.3, architecture §8.1.

Pure and deterministic — enters the freeze manifest.

Strata: country, seniority, POS class, tier, abstain trigger. The §7.1
(``مطلوبة``) and §7.2 (``المتقدم``) error classes are **over-sampled**, because
they are known systematic errors whose magnitude the paper reports rather than
hides.

Determinism (prohibition 6)
---------------------------
Unseeded sampling is forbidden. Every function here takes an explicit ``seed``,
sorts its input by ``cue_id`` before drawing, and iterates strata in sorted key
order. Two runs with the same seed and inputs produce byte-identical output
regardless of the order cues arrive in.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Hashable, Iterable, Mapping, Sequence

__all__ = [
    "StratumKey",
    "SamplingPlan",
    "stratify",
    "stratified_sample",
    "DEFAULT_OVERSAMPLE",
    "DEFAULT_ABSTAIN_OVERSAMPLE",
    "error_class_of",
    "is_abstained",
]

#: Error classes to over-sample, per spec §8.3 and architecture §8.1
#: ("Over-sample abstentions and the مطلوبة error class").
#: Keyed by surface token; the multiplier scales that stratum's quota.
DEFAULT_OVERSAMPLE: Mapping[str, float] = {
    "مطلوبة": 3.0,  # spec §7.1 — rat=i on all readings, but refers to the sought person
    "مطلوب": 3.0,
    "المتقدم": 3.0,  # spec §7.2 — pos=adj, rat=n, routes to Tier C with no target
    "المتقدمة": 3.0,
}

#: The other half of architecture §8.1's sampling plan — "Over-sample
#: **abstentions** and the مطلوبة error class."
#:
#: Abstained cues are the ones the tagger could not resolve, so they are where
#: human labels buy the most: θ is calibrated against the AB1 boundary cases, and
#: AB4's gender asymmetry (register D14) is measured on real text only here. Drawn
#: proportionally they are a minority of any sample, and most annotator hours go
#: to cues the tagger already answered.
#:
#: 3.0 matches the weight :data:`DEFAULT_OVERSAMPLE` already applies to the known
#: error classes, so the pre-registration declares one weight and a reason rather
#: than two unrelated constants.
#:
#: **This is a frozen, pre-registered parameter.** Changing it changes which cues
#: are adjudicated and therefore every §8.1 figure. It also makes the sample
#: deliberately unrepresentative of the corpus: any prevalence statistic computed
#: from annotated cues must be re-weighted back using
#: :attr:`SamplingPlan.per_stratum`, which records the draw per stratum for
#: exactly that purpose.
DEFAULT_ABSTAIN_OVERSAMPLE = 3.0

StratumKey = tuple[Hashable, ...]


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    """A drawn sample, with the provenance needed to reproduce it."""

    cue_ids: tuple[str, ...]
    seed: int
    per_stratum: Mapping[StratumKey, int]
    #: Names of the stratum-key elements, positionally aligned with the keys in
    #: :attr:`per_stratum`. This is the five spec §8.3 variables **plus** a
    #: trailing ``error_class``, which is part of the key so that §7.1/§7.2 cues
    #: form their own strata and can be quota'd precisely.
    strata_fields: tuple[str, ...]
    requested: int
    #: The abstention multiplier this draw used. Recorded on the plan because it
    #: is a pre-registered parameter and because any prevalence figure computed
    #: from the drawn cues has to be re-weighted by it.
    abstain_oversample: float
    #: Strata that produced fewer cues than their quota, because the stratum was
    #: smaller than the quota. Reported, never silently absorbed — a silently
    #: shortfallen stratum reads as "covered" when it is not.
    shortfalls: Mapping[StratumKey, tuple[int, int]]


def error_class_of(
    cue: Mapping[str, object], oversample: Mapping[str, float] = DEFAULT_OVERSAMPLE
) -> str | None:
    """The known error class a cue belongs to, or ``None``.

    Spec §7.1 (``مطلوبة``) and §7.2 (``المتقدم``) are named systematic error
    classes whose magnitude the paper reports rather than hides.
    """
    token = str(cue.get("token", ""))
    return token if token in oversample else None


def is_abstained(cue: Mapping[str, object]) -> bool:
    """Did the tagger abstain on this cue?

    Read from ``abstain_reason`` rather than from ``referent``, because the
    contract makes the trigger mandatory on every abstention
    (``TaggedCue.__post_init__``) — so a missing trigger is impossible rather
    than ambiguous.
    """
    return cue.get("abstain_reason") is not None


def _default_key(cue: Mapping[str, object], fields: Sequence[str]) -> StratumKey:
    return tuple(cue.get(f) for f in fields)


def stratify(
    cues: Iterable[Mapping[str, object]],
    fields: Sequence[str],
    *,
    key_fn: Callable[[Mapping[str, object], Sequence[str]], StratumKey] | None = None,
) -> dict[StratumKey, tuple[Mapping[str, object], ...]]:
    """Partition cues into strata, deterministically.

    Cues are sorted by ``cue_id`` inside each stratum so the partition does not
    depend on input order.
    """
    key_fn = key_fn or _default_key
    buckets: dict[StratumKey, list[Mapping[str, object]]] = defaultdict(list)
    for cue in cues:
        buckets[key_fn(cue, fields)].append(cue)
    return {
        key: tuple(sorted(items, key=lambda c: str(c["cue_id"])))
        for key, items in sorted(buckets.items(), key=lambda kv: str(kv[0]))
    }


def stratified_sample(
    cues: Iterable[Mapping[str, object]],
    *,
    n: int,
    seed: int,
    fields: Sequence[str] = (
        "country",
        "seniority",
        "pos",
        "tier",
        "abstain_reason",
    ),
    oversample: Mapping[str, float] = DEFAULT_OVERSAMPLE,
    abstain_oversample: float = DEFAULT_ABSTAIN_OVERSAMPLE,
) -> SamplingPlan:
    """Draw ``n`` cues, stratified per spec §8.3, over-sampling both classes
    architecture §8.1 names: abstentions, and the known error classes.

    Parameters
    ----------
    n:
        Target sample size. The realised size may be smaller when strata are
        smaller than their quotas — see :attr:`SamplingPlan.shortfalls`, which
        records every such case rather than absorbing it.
    seed:
        Required. Prohibition 6 forbids unseeded sampling; the seed enters the run
        config and therefore the freeze hash.
    fields:
        Stratification variables. Defaults to the five in spec §8.3.
    oversample:
        Token → multiplier for known error classes.
    abstain_oversample:
        Multiplier for abstained cues. ``1.0`` restores proportional sampling.
        Frozen and pre-registered — see :data:`DEFAULT_ABSTAIN_OVERSAMPLE`, and
        note the re-weighting obligation recorded there.

    Determinism
    -----------
    Same ``(cues, n, seed, fields, oversample)`` → identical ``cue_ids``, in the
    same order, regardless of the order ``cues`` is supplied in.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if abstain_oversample <= 0:
        raise ValueError(
            f"abstain_oversample must be positive, got {abstain_oversample}. "
            f"Use 1.0 for proportional sampling; 0 would drop every abstention, "
            f"which prohibition 3 forbids."
        )

    cue_list = tuple(cues)
    if not cue_list:
        raise ValueError("cannot sample from an empty cue set")

    # Both over-sampled properties are part of the stratum key, not weights
    # applied to a stratum that merely *contains* such a cue. Weighting the whole
    # stratum would inflate every cue sharing it — over-sampling the neighbours
    # of the error class instead of the error class itself, which is not what
    # spec §8.3 asks for.
    #
    # Abstention is keyed even though `abstain_reason` is usually already one of
    # `fields`, which makes it redundant there and harmless. It is not redundant
    # when a caller passes a narrower `fields`: without it, a stratum could mix
    # abstained and resolved cues, and the multiplier would enlarge that
    # stratum's quota without making the draw inside it prefer the abstentions
    # the quota was enlarged for.
    def key_fn(cue: Mapping[str, object], flds: Sequence[str]) -> StratumKey:
        return (
            *(cue.get(f) for f in flds),
            is_abstained(cue),
            error_class_of(cue, oversample),
        )

    strata = stratify(cue_list, fields, key_fn=key_fn)

    # Each stratum is now homogeneous in both, so the multipliers apply to
    # exactly the cues they are meant to. They compose: an abstained مطلوبة is
    # both a known error class and an unresolved cue.
    weights: dict[StratumKey, float] = {}
    for key, items in strata.items():
        error_class = key[-1]
        multiplier = oversample.get(str(error_class), 1.0) if error_class else 1.0
        if key[-2]:  # abstained
            multiplier *= abstain_oversample
        weights[key] = len(items) * multiplier

    total_weight = sum(weights.values())

    # Proportional quotas, floored, then the remainder distributed by largest
    # fractional part with the stratum key as a deterministic tie-break.
    raw = {key: n * w / total_weight for key, w in weights.items()}
    quotas = {key: int(value) for key, value in raw.items()}
    remaining = n - sum(quotas.values())
    if remaining > 0:
        order = sorted(
            raw.items(), key=lambda kv: (-(kv[1] - int(kv[1])), str(kv[0]))
        )
        for key, _ in order[:remaining]:
            quotas[key] += 1

    rng = random.Random(seed)
    drawn: list[str] = []
    per_stratum: dict[StratumKey, int] = {}
    shortfalls: dict[StratumKey, tuple[int, int]] = {}

    for key in sorted(strata, key=str):
        items = strata[key]
        quota = quotas.get(key, 0)
        take = min(quota, len(items))
        if take < quota:
            shortfalls[key] = (quota, len(items))
        if take:
            picked = rng.sample(list(items), take)
            drawn.extend(str(c["cue_id"]) for c in picked)
        per_stratum[key] = take

    return SamplingPlan(
        cue_ids=tuple(sorted(drawn)),
        seed=seed,
        per_stratum=per_stratum,
        # Positionally aligned with the keys actually produced by `key_fn`.
        # `error_class` stays last so the weight lookup above reads off `key[-1]`.
        strata_fields=(*fields, "abstained", "error_class"),
        requested=n,
        shortfalls=shortfalls,
        abstain_oversample=abstain_oversample,
    )
