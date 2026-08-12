"""Pure analysis logic. Enters the freeze manifest.

Everything under this package is **I/O-free and side-effect-free** (ADR 007,
CLAUDE.md "Architecture constraints"):

* no model loading
* no filesystem or network access
* no wall-clock, no PID, no randomness
* no reliance on ``set`` iteration or dict ordering for output

Model loading lives in ``arabgn/tagger/``, which does **not** enter the freeze;
model identity is pinned instead by ``toolkit_version`` and ``db_version``
recorded on every ``TaggedCue``.

Consequence for tests: nothing here requires ``camel_data``, so a reviewer can
exercise this logic on a laptop with no downloads.

The freeze set is an explicit manifest of paths in the run config, **not** a glob
over this directory — a glob silently changes the hash when a file is added.
"""
