"""Scoring backends. Two implementations behind one interface (architecture §2).

* **Deterministic synthetic backend** — a pure function with no model downloads,
  runs on a laptop. Lets a reviewer re-run every estimator against **known ground
  truth**, because the effect is injected rather than measured. This is what the
  test suite exercises.
* **Real ranker backend** — the version-pinned open-weight audit subjects
  (multilingual-e5-large, BGE-M3, jina-v3, an Arabic encoder, two LLM screeners).
  Not implemented yet; it needs model downloads and GPU.

CLAUDE.md: "Tests must never require the real backend."

The synthetic backend is what makes the instrument's own validation possible.
Architecture §8.3 and §8.4 call the positive control and the zero-cue calibration
cell "the instrument's ground truth" — and both are only constructible if you can
inject an effect of known magnitude, or none at all, and check what comes back.
"""

from arabgn.scoring.base import ScoringBackend, ScoredPair
from arabgn.scoring.synthetic import SyntheticBackend, SyntheticConfig

__all__ = [
    "ScoringBackend",
    "ScoredPair",
    "SyntheticBackend",
    "SyntheticConfig",
]
