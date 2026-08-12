"""Corpus loading. I/O — not frozen (ADR 007).

Corpus *checksums* enter the freeze hash (architecture §6.3); the loader that
computes them does not.
"""

from arabgn.corpus.arabjobs import (
    ArabJobsLoader,
    CorpusStats,
    describe,
    load_arabjobs,
)

__all__ = ["ArabJobsLoader", "load_arabjobs", "describe", "CorpusStats"]
