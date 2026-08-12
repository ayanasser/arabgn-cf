# ADR 006 — `uv` is the lockfile tool, with `--exclude-newer`

- **Register ID:** D10 (P2)
- **Status:** Accepted
- **Date:** 12 August 2026
- **Affects:** `pyproject.toml` · `uv.lock` · `CLAUDE.md` (Environment setup) ·
  Phase 1 · Phase 9 freeze

---

## Context

Architecture §6.3 hashes "run config, every analysis module's source, corpus
checksums, model version pins, and **dependency lockfile**". `pyproject.toml`
declares constraints, not a resolution — it is not a lockfile. Two different
machines resolving the same `pyproject.toml` a week apart can install different
transitive versions, and the freeze hash would not notice.

## Decision

**`uv`**, with `uv.lock` committed from the first commit of Phase 1.

Resolution is pinned with `--exclude-newer <timestamp>`, which instructs the
resolver to ignore any package release published after a given moment. That gives
reproducible resolution **from a timestamp** — which is precisely the property
§6.3 needs, and the same class of guarantee the external time anchor provides for
the analysis itself.

Alternatives considered: `pip-tools` (conservative, produces a flat
`requirements.txt` lock, no `--exclude-newer` equivalent) and `poetry` (heavier,
and its lock format has changed across major versions, which is a liability for a
freeze that must verify in two years).

## Consequences

- `uv.lock` enters the freeze manifest — see [[007-freeze-boundary]].
- The `--exclude-newer` timestamp is itself a frozen constant and must be declared
  in the pre-registration alongside the model pins.
- CLAUDE.md's Environment setup section changes from `pip install -e ".[dev]"` to
  `uv sync --extra dev`. The `camel_data` steps are unchanged and remain separate —
  `uv` does not fetch model data any more than `pip` did.
- Adding a dependency now changes `uv.lock` and therefore the freeze hash
  visibly, which is what CLAUDE.md prohibition 5 is trying to achieve.
- A reviewer reproducing the environment runs `uv sync --frozen`, which fails
  loudly if `uv.lock` and `pyproject.toml` disagree.

## Related

[[007-freeze-boundary]]
