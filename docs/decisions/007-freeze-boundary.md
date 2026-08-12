# ADR 007 — Freeze boundary splits pure logic from model I/O

- **Register ID:** D11 (P2)
- **Status:** Accepted
- **Date:** 12 August 2026
- **Affects:** `CLAUDE.md` (Architecture constraints) · package layout ·
  Phase 1 · Phase 2B · Phase 9 freeze

---

## Context

CLAUDE.md states:

> Modules under `arabgn/analysis/` enter the freeze hash. Keep them free of I/O
> and side effects.

The tagger produces C1, the paper's only standalone empirical finding, so its
logic plainly belongs in the freeze. But the tagger must load
`BERTUnfactoredDisambiguator` and a morphology database from `~/.camel_tools/`,
which is I/O by definition. Under the rule as written the tagger both must and
cannot enter the freeze.

## Decision

**Split the tagger along the I/O boundary.**

```
arabgn/
  contracts.py          dataclasses + enums — pure, frozen
  analysis/             pure, I/O-free, frozen
    text.py             normalisation
    ...                 cue detection, rationality resolution, tier classification
  tagger/               I/O, not frozen
    analyzer.py         model loading, caching, disambiguator wrapper
```

Classification logic takes analyses as **input data** and returns decisions. It
never loads a model. The `tagger/` layer loads models and hands analyses to
`analysis/`.

Model identity is pinned not by hashing the loader but by recording
`toolkit_version` and `db_version` **on every emitted `TaggedCue`** — already
required by architecture §4.5. A cue therefore carries its own provenance, and a
model swap is visible in the output data rather than only in a source hash.

### `text.py` moves under `analysis/`

Normalisation is pure, and architecture §3.2 calls it "the single most important
preprocessing decision in the system." It must be frozen. It therefore lives at
`arabgn/analysis/text.py`, not `arabgn/text.py` as earlier phase plans had it.

## Consequences

### The freeze set is an explicit manifest, not a directory glob

Recommended and adopted: define the frozen set as an **explicit list of paths** in
the run config, rather than "whatever is currently in `arabgn/analysis/`."

A glob silently changes the hash when a file is added, and silently fails to
notice when a freeze-relevant file is added *outside* the directory. Both are the
opposite of what §6.3 wants. An explicit manifest makes any change to the frozen
set a reviewable diff.

Initial manifest:

```
arabgn/contracts.py
arabgn/analysis/**            (enumerated, not globbed)
pyproject.toml
uv.lock
<run config>
<corpus checksums>
<model version pins>
```

`contracts.py` is in the manifest because it defines output shape — a change there
changes results — but it is **not** placed under `analysis/`, because it is shared
by frozen and unfrozen layers alike. The manifest is what makes this possible;
under a directory rule it would have to be one or the other.

### Testing

`analysis/` is pure, so its tests need no model downloads and no `camel_data`.
That preserves the property architecture §2 wants for the scoring layer — a
reviewer can exercise the logic on a laptop — and extends it to the tagger's
decision-making.

`tagger/` tests do require `camel_data` and are marked accordingly so a clean
checkout fails legibly rather than confusingly.

## Related

[[006-lockfile-uv]] · [[002-tier-membership-and-morph-class]] — if the
`morph_class` probe returns *go* and the derivation needs a frozen lexeme list,
that list enters the manifest too.
