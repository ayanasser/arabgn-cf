"""Deterministic synthetic scoring backend. Architecture §2, §8.3, §8.4.

Generates scores from a known variance structure with a **known injected effect**,
so every estimator downstream can be checked against ground truth it cannot see.

The generative model, and why it needs interaction terms
--------------------------------------------------------
::

    score_f[a,c] = mu + effect/2 + ad[a] + pair[c]
                   + ad_gender[a]/2 + pair_gender[c]/2 + resid_f[a,c]
    score_m[a,c] = mu - effect/2 + ad[a] + pair[c]
                   - ad_gender[a]/2 - pair_gender[c]/2 + resid_m[a,c]

so the contrast is::

    difference[a,c] = effect + ad_gender[a] + pair_gender[c]
                      + (resid_f - resid_m)

**The level effects ``ad[a]`` and ``pair[c]`` cancel; the interaction terms do
not.** This distinction is the whole content of architecture §7.3's open issue,
and getting it wrong makes the SE formula incoherent:

* A model with **only** level effects produces iid differences. Then σ²_ad and
  σ²_cv are both zero, clustering buys nothing, and ``SE² = σ²_ad/A + σ²_cv/C +
  σ²_resid/(A·C)`` reduces to the iid formula. That is not the design being
  analysed.
* The terms that survive differencing are **interactions with gender**:
  ``ad_gender[a]`` is how much *this ad* rewards feminine over masculine text,
  and ``pair_gender[c]`` is how much *this twin pair* discords.

So in the SE formula, σ²_ad is the variance of the ad×gender interaction and
σ²_cv is **twin-discordance variance** — not a CV-level random effect. That is
precisely the reading architecture §7.3 says "the notation reads like" the wrong
one, and §10 decision 4 says must be defined in one sentence before the C4 freeze.

This backend makes the distinction testable: raising ``sd_pair`` (a level effect)
must not move the differences at all, while raising ``sd_pair_gender``
(discordance) must.

Determinism (prohibition 6)
---------------------------
Every draw comes from ``numpy.random.default_rng(seed)`` with an explicit seed,
and the seed enters the run config and therefore the freeze hash. Draws are made
in a fixed order over sorted ids, so the same config always produces byte-identical
scores regardless of the order ids are supplied in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arabgn.scoring.base import ScoredPair

__all__ = ["SyntheticConfig", "SyntheticBackend"]


@dataclass(frozen=True, slots=True)
class SyntheticConfig:
    """Known ground truth for a synthetic cell.

    ``effect`` is the injected female-minus-male difference. ``0.0`` gives the
    zero-cue calibration cell of architecture §8.4 — "the instrument should return
    null. If it returns a signal, the pipeline has a leak."
    """

    effect: float = 0.0

    #: Level effects. These CANCEL in the twin difference — an ad that scores
    #: everyone highly does not create a gender contrast. Included because they
    #: are present in real scores and the estimator must be robust to them.
    sd_ad: float = 1.0
    sd_pair: float = 1.0

    #: Interaction-with-gender effects. These SURVIVE differencing and are what
    #: σ²_ad and σ²_cv denote in architecture §7.3's SE formula.
    #: ``sd_ad_gender``: how much ads vary in rewarding feminine over masculine.
    #: ``sd_pair_gender``: twin discordance.
    sd_ad_gender: float = 0.0
    sd_pair_gender: float = 0.0

    sd_resid: float = 1.0
    mu: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        for name in (
            "sd_ad", "sd_pair", "sd_ad_gender", "sd_pair_gender", "sd_resid"
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


class SyntheticBackend:
    """Pure, seeded, no model downloads.

    Example — a positive control (architecture §8.3), an effect of known size::

        backend = SyntheticBackend(SyntheticConfig(effect=0.5, seed=1))
        pairs = backend.score_pairs(ad_ids, pair_ids)

    If an estimator cannot recover ``0.5`` here, "every null elsewhere is
    uninterpretable."
    """

    def __init__(self, config: SyntheticConfig) -> None:
        self.config = config

    def score_pairs(
        self, ad_ids: Sequence[str], pair_ids: Sequence[str]
    ) -> tuple[ScoredPair, ...]:
        """Score every (ad, pair) cell.

        Ids are sorted before drawing so the output does not depend on the order
        they arrive in — two callers passing the same ids in different orders get
        identical scores (prohibition 6).
        """
        cfg = self.config
        ads = sorted(set(ad_ids))
        pairs = sorted(set(pair_ids))
        if not ads or not pairs:
            raise ValueError("need at least one ad and one pair")

        rng = np.random.default_rng(cfg.seed)

        # Drawn in a fixed order so the same seed always gives the same draws.
        ad_effect = rng.normal(0.0, cfg.sd_ad, size=len(ads))
        pair_effect = rng.normal(0.0, cfg.sd_pair, size=len(pairs))
        ad_gender = rng.normal(0.0, cfg.sd_ad_gender, size=len(ads))
        pair_gender = rng.normal(0.0, cfg.sd_pair_gender, size=len(pairs))
        resid_f = rng.normal(0.0, cfg.sd_resid, size=(len(ads), len(pairs)))
        resid_m = rng.normal(0.0, cfg.sd_resid, size=(len(ads), len(pairs)))

        out: list[ScoredPair] = []
        for i, ad_id in enumerate(ads):
            for j, pair_id in enumerate(pairs):
                # Cancels in the difference.
                shared = cfg.mu + ad_effect[i] + pair_effect[j]
                # Survives the difference — this is what σ²_ad and σ²_cv denote.
                gendered = (cfg.effect + ad_gender[i] + pair_gender[j]) / 2.0
                out.append(
                    ScoredPair(
                        ad_id=ad_id,
                        pair_id=pair_id,
                        score_f=shared + gendered + resid_f[i, j],
                        score_m=shared - gendered + resid_m[i, j],
                    )
                )
        return tuple(out)
