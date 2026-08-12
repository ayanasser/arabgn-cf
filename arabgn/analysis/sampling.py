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
    "error_class_of",
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
) -> SamplingPlan:
    """Draw ``n`` cues, stratified per spec §8.3, with error classes over-sampled.

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

    Determinism
    -----------
    Same ``(cues, n, seed, fields, oversample)`` → identical ``cue_ids``, in the
    same order, regardless of the order ``cues`` is supplied in.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")

    cue_list = tuple(cues)
    if not cue_list:
        raise ValueError("cannot sample from an empty cue set")

    # The error class is part of the stratum key, not a weight applied to a
    # stratum that merely *contains* an error-class cue. Weighting the whole
    # stratum would inflate every cue sharing it — over-sampling the neighbours
    # of the error class instead of the error class itself, which is not what
    # spec §8.3 asks for.
    def key_fn(cue: Mapping[str, object], flds: Sequence[str]) -> StratumKey:
        return (*(cue.get(f) for f in flds), error_class_of(cue, oversample))

    strata = stratify(cue_list, fields, key_fn=key_fn)

    # Each stratum is now homogeneous in error class, so the multiplier applies
    # to exactly the cues it is meant to.
    weights: dict[StratumKey, float] = {}
    for key, items in strata.items():
        error_class = key[-1]
        multiplier = oversample.get(str(error_class), 1.0) if error_class else 1.0
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
        strata_fields=(*fields, "error_class"),
        requested=n,
        shortfalls=shortfalls,
    )
