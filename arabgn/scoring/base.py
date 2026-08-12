"""The scoring interface both backends implement. Architecture §2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

__all__ = ["ScoredPair", "ScoringBackend"]


@dataclass(frozen=True, slots=True)
class ScoredPair:
    """One twin pair scored against one ad.

    ``score_f - score_m`` is the per-pair difference architecture §7.2 asks for
    (female minus male). It is stored as a derived property rather than a field
    so it cannot drift from its components.
    """

    ad_id: str
    pair_id: str
    score_f: float
    score_m: float

    @property
    def difference(self) -> float:
        """Female minus male. Architecture §7.2, "score level"."""
        return self.score_f - self.score_m


class ScoringBackend(Protocol):
    """What the analysis layer is allowed to assume about a scorer."""

    def score_pairs(
        self, ad_ids: Sequence[str], pair_ids: Sequence[str]
    ) -> tuple[ScoredPair, ...]:
        """Score every (ad, pair) combination. Deterministic given the config."""
        ...
