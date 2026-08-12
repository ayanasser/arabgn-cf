# ArabGN-CF

**A measurement instrument for auditing gender bias in Arabic résumé ranking.**

Supporting artifact for *"Name Redaction Does Not Blind an Arabic Résumé Ranker:
An Open, Pre-Registered Instrument and Power Analysis for Gender-Bias Audits in
AI-Assisted Recruitment"* — NILES 2026, Special Session SS2.

> **The output of this repository is a scientific claim, not a product.**
> Correctness and reproducibility outrank speed, elegance and convenience in every
> trade-off. See [`CLAUDE.md`](CLAUDE.md).

---

## The problem

Every published fairness safeguard for automated résumé screening assumes that
removing the applicant's name removes the protected attribute.

**Arabic breaks that assumption at the level of grammar.** Gender agreement is
obligatory on verbs, adjectives, participles and pronouns — not just on names:

| Masculine | Feminine | Gloss |
|---|---|---|
| حاصل على | حاصلة على | holder of |
| تخرج | تخرجت | graduated |
| عمل | عملت | worked |
| مسؤول عن | مسؤولة عن | responsible for |

Redacting `أحمد` → `[REDACTED]` removes one cue and leaves all the others. The
applicant's gender is still marked, repeatedly, throughout the document.

### The hard part: reference, not morphology

Counting feminine endings is not the task. `خبرة واسعة` ("broad experience") is
grammatically feminine **twice over** — but the feminine marking belongs to the
*experience*, which is a thing, not a person. Neither token tells you anything
about the applicant.

So the tagger must decide, for each gender cue, *what it refers to*. Where that is
genuinely undecidable it **abstains** rather than guessing, and routes the case to
human adjudication. A high abstention rate is an acceptable, reportable outcome —
it is the design's honesty mechanism, not a defect.

---

## What this repository contains

| Deliverable | Description |
|---|---|
| **C1** | Cue-level prevalence of applicant-referring gender marking in real Arabic job ads |
| **C2** | ArabGN-CF itself — an open, cryptographically frozen audit instrument |
| **C3** | Variance components and a power/feasibility result for twin-contrast audits |
| **C4** | A public pre-registration, timestamped before unblinding |

### What it is explicitly **not**

- Not an audit result — confirmatory twin contrasts stay sealed.
- Not an evaluation of any commercial hiring system.
- Not population statistics about real applicants — twins are synthetic by
  necessity, since no two real applicants have identical qualifications.
- Nothing built here is itself an audit subject.

---

## Quick start

```bash
# 1. Environment (uv.lock is authoritative and enters the freeze hash)
uv sync --extra dev

# 2. Model data is a SEPARATE step. Installing packages does not fetch it.
uv run camel_data -i morphology-db-msa-r13
uv run camel_data -i disambig-bert-unfactored-msa

# 3. Tests
uv run pytest
```

Expected on a clean checkout:

```
arabgn fixtures: 27 total, 17 settled, 10 REVIEW (skipped)
  REVIEW (open questions, not failures): B01, B02, C04, C05, C06, C07, E01, E02, E03, T02
127 passed, 1 skipped, 1 xfailed
```

The **10 skips are open questions, not gaps in coverage** — see
[`docs/AUTHOR-ACTIONS.md`](docs/AUTHOR-ACTIONS.md). The **1 xfail is a real
finding**, [D14](docs/findings/001-ab4-is-gender-asymmetric.md).

Most tests need no model at all. Only `tests/test_tagger.py` is marked
`needs_camel_data`:

```bash
uv run pytest -m "not needs_camel_data"    # 115 pass, no downloads needed
```

> **Dataset naming gotcha.** `camel_data -i` takes `morphology-db-msa-r13`; the
> Python API takes **`calima-msa-r13`**. Passing the download name to
> `MorphologyDB.builtin_db()` raises a bare `KeyError`.

---

## How the tagger works

Three tiers, named after **how reference is resolved** — not after any linguistic
property of the cue.

```
                    token carries gen ∈ {m,f}, content POS?
                                   │
                        no ────────┴──────── yes
                         │                    │
                    not a cue          rationality mass
                    (N01 على,          over candidates
                     N02 2018)                │
                                ┌─────────────┼─────────────┐
                          nominal POS                  verb / adj
                                │                           │
                    ┌───────────┴──────────┐         Tier C — inherit
                 resolves            ambiguous       from agreement
                    │                     │            target
              Tier A — lexical      Tier B — ABSTAIN   (Phase 5)
                    │                   (AB1)
          ┌─────────┴────────┐
     irrational          rational
          │                   │
    non_applicant        role test (§5.1)
      (خبرة, الشركة)     ┌────┴────┐
                     passes    indeterminate
                        │            │
                   applicant     ABSTAIN (AB6)
                   (المرشحة)
```

**Rationality (`rat`)** — `r` human, `i` non-human, `n` inherited-by-agreement —
is the established feature from the Arabic agreement-modelling literature
(Alkuhlani & Habash 2011), exposed directly by CAMeL Tools. It is the primary
evidence for applicant-reference but is **not identical to it**: a job ad also
refers to hiring managers, teams and clients.

### Why `top=100` is load-bearing

`BERTUnfactoredDisambiguator.pretrained('msa', top=100)` — never the default.

The default returns top-1. With a **single** candidate analysis, "candidates
disagree on rationality" can never fire, so the Tier B abstain mechanism is
destroyed entirely and every ambiguous cue is silently resolved.

Measured: `حاصلة` returns **34** scored analyses at `top=100`, spanning
`rat ∈ {i, r}`. At top-1 it returns `rat=i` — which is *wrong* in
`مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة`, where it refers to the sought
engineer.

### The abstain triggers

| ID | Trigger | Tier |
|---|---|---|
| AB1 | Rationality does not resolve under the mass rule | B |
| AB2 | Agreement target not identifiable | C |
| AB3 | Agreement target itself abstains | C |
| AB4 | Candidates disagree on `gen` after disambiguation | any |
| AB5 | `gen` ≠ `form_gen` (form/functional divergence) | any |
| AB6 | Rational cue whose role test is indeterminate | A |

Every abstained cue records its trigger. **Abstentions are never dropped from a
metric and never silently assigned to a class.**

---

## Repository layout

```
arabgn/
  contracts.py            DocRecord, TaggedCue, enums — pure, FROZEN
  analysis/               pure, I/O-free, no model loading — FROZEN
    text.py               NFC-only normalisation
    cues.py               POS filtering, rationality mass
    thresholds.py         the §4.2 mass rule + θ separability sweep
    tiers.py              Tier A/B classification
    symmetry.py           twin-symmetry invariant
    agreement.py          Cohen's κ and the κ ≥ 0.7 gate
    sampling.py           stratified sampling for adjudication
  tagger/                 model loading and I/O — NOT frozen
    analyzer.py           BERTUnfactoredDisambiguator wrapper
  adjudication/           annotation tooling — NOT frozen
    items.py              what an annotator sees (and cannot see)
    store.py              append-only JSONL
    cli.py                blind annotation + κ commands

docs/
  architecture.md         five-layer design (converted from PDF; see its §12)
  linguistic-spec.md      what counts as a cue, how reference is decided
  decision_register.md    14 decisions, open and closed
  decisions/              one ADR per closed decision
  findings/               things the instrument discovered about itself
  STATUS.md               live build checklist
  AUTHOR-ACTIONS.md       what is waiting on a human
  theta-sweep.md          calibration evidence
  proposal-corrections.md claims in the SS2 proposal needing correction

tests/
  fixtures/tagger_fixtures.yaml   27 human-authored ground-truth fixtures
```

### The freeze boundary

Architecture §6.3 hashes the run config, every analysis module's source, corpus
checksums, model pins and the dependency lockfile. Confirmatory analysis refuses
to run if the hash does not match.

That forces a split ([ADR 007](docs/decisions/007-freeze-boundary.md)):

- **`arabgn/analysis/` is pure** — no I/O, no model loading, no wall-clock, no
  randomness, no `set` iteration for output. It takes analyses as *data*.
- **`arabgn/tagger/` loads models** and is not frozen. Model identity is pinned
  instead by `toolkit_version` / `db_version` recorded on **every emitted cue**,
  so provenance travels with the data rather than only with a source hash.

Consequence: the classification logic is testable on a laptop with no downloads.

The freeze set is an **explicit manifest of paths**, not a directory glob — a glob
silently changes the hash when a file is added, which is the opposite of what a
freeze wants.

---

## Ground truth and fixtures

`tests/fixtures/tagger_fixtures.yaml` is **human-authored ground truth**.

> **Never edit a fixture to make a test pass.** If code disagrees with a fixture,
> either the code is wrong or the fixture needs author review. Raise it.

The rule protects claims about *Arabic*, so it names the fields it protects:

`text` · `text_f` · `text_m` · `cue` · `expected_label` · `expected_tier` ·
`abstain_id` · `expected_text_norm` · `expected_cue_emitted` · `confidence`

Everything else — `group`, `note`, `doc_type`, ordering — is test organisation
([ADR 004](docs/decisions/004-fixture-group-key-and-scoped-never-edit-rule.md)).

`confidence: REVIEW` marks an **open question, not a target**. Ten fixtures are
unresolved; each skips with a reason naming the decision that blocks it. The count
prints in the pytest header so a green suite can't be mistaken for full coverage.

---

## Hard prohibitions

These are not style preferences. Violating any of them invalidates results.

**1. Never normalise Arabic orthography.** Do not map `ة`→`ه`, `أإآ`→`ا`, or
`ى`→`ي`, and do not strip diacritics. Ta-marbuta is the primary feminine marker —
it is *the signal this project measures*. Standard Arabic pipelines strip it as a
matter of course; that habit would silently destroy the study. **Unicode NFC is
the only permitted normalisation**, guarded by fixtures O01/O02/O03 and by a
runtime assertion in `normalise()`.

**2. Never train, fine-tune or adapt a model.** Every model here is measured,
never trained — including "just a small classifier" for referent resolution.

**3. Never drop abstentions from metrics.** They are their own category. Any
metric taking abstentions reports the abstention rate alongside.

**4. Never emit "no bias".** The reporting layer refuses the phrase by design. No
test can license the claim, so no output may make it.

**5. Never add a dependency without asking.** Every dependency changes the
lockfile and therefore the freeze hash.

**6. Never introduce nondeterminism.** No unseeded sampling, no `set` iteration
for output, no dict-order reliance, no wall-clock or PID in derived values.

> Prohibition 6 is not theoretical. `rationality_mass` originally summed candidate
> scores with `+`. Floating-point addition is **not associative**, so the mass
> varied in the last bits with candidate order — `0.5625` vs `0.5625000000000001`.
> A mass sitting near θ could have resolved differently, and the freeze hash would
> not have reproduced. It now uses `math.fsum`.

---

## Twin symmetry — the invariant that matters most

If the instrument classifies feminine text differently from an otherwise-identical
masculine twin, **every downstream measurement is confounded by the instrument
itself**. A measured "bias" could be the ranker's — or the tagger's — and nothing
in the analysis layer can tell them apart.

```bash
uv run pytest tests/test_symmetry.py
```

This is built as a **gate**, not an assumption. It has already earned its keep:

### Finding D14 — AB4 is gender-asymmetric

| Twin | Trigger | Candidates |
|---|---|---|
| `حاصلة` (f) | **AB4** — gender disagreement | 34: 21 `gen=f`, **12 `gen=m`** |
| `حاصل` (m) | **AB1** — rationality unresolved | 19: 18 `gen=m`, **0 `gen=f`** |

Both abstain — but by different routes, so the twins land in different
adjudication strata and different rows of every trigger-stratified table. It is
*structural*: feminine surface forms admit masculine analyses while the converse
is rare, so AB4 fires more often on feminine cues as a property of the morphology
database. No threshold removes it.

Full analysis and four options:
[`docs/findings/001-ab4-is-gender-asymmetric.md`](docs/findings/001-ab4-is-gender-asymmetric.md).

The instrument caught a gender asymmetry **in itself**, before any measurement was
taken. Without this gate it would have shipped into C1's abstention tables and
been reported as a property of Arabic recruitment text.

---

## Adjudication

Human labels are the only direct ground truth (architecture §8.1). The tooling
enforces the protocol structurally rather than by convention:

```bash
uv run python -m arabgn.adjudication.cli annotate \
    --items items.jsonl --out annotations.jsonl --annotator A1

uv run python -m arabgn.adjudication.cli kappa \
    --annotations annotations.jsonl --a A1 --b A2
```

- **Blind by construction.** `AnnotationItem` has *no field* for the prediction,
  tier or abstain status, so no display path can leak them. A convention saying
  "don't show these" is one careless template away from breaking; a type that
  cannot carry them is not.
- **`unclear` is a valid answer**, recorded as itself and never coerced. Its rate
  is reported.
- **Append-only.** No update path, no delete path — an annotation revisable in
  place makes κ silently unstable.
- **κ ≥ 0.7 is a hard gate** that raises, not a warning. Below it the gold set is
  unusable and every downstream precision figure is uninterpretable. *This gate
  can genuinely fail.*
- **Persistent disagreement after third-annotator adjudication is recorded as
  `unclear`**, not forced to a label.

---

## Current status

See [`docs/STATUS.md`](docs/STATUS.md) for the live checklist and the review log.

| Phase | State |
|---|---|
| 0 Doc reconciliation | ✅ |
| 1 Skeleton, contracts, normalisation | ✅ |
| 2A Adjudication tooling | ✅ tooling · ⛔ gold set (human lead time) |
| 2B Tier A/B extractor | ✅ code · ⛔ frozen θ (Phase 4) |
| 3 Twin symmetry (provisional) | ✅ — surfaced D14 |
| 4 Gold set κ ≥ 0.7 + θ calibration | ⛔ human annotation |
| 5 Tier C | ⛔ D7, D8, D9 |
| 6 Twin symmetry, all tiers | ⛔ Phase 5 |
| 7 ArabJobs sweep → C1 | ⛔ Phases 4–6 |
| 8–11 Generator, freeze, analysis, pre-reg | ⛔ |

**The critical path is human, not technical.** Everything buildable without an
author decision or an annotated gold set is done.

---

## Contributing

Read [`CLAUDE.md`](CLAUDE.md) first — it wins over anything here.

- **When a design decision is not covered by the three documents, stop and ask.**
  Record the answer as an ADR in `docs/decisions/`. Guessing is how linguistic
  ground truth gets silently corrupted, and it would not show up in a passing
  suite.
- **No test asserts current behaviour.** Every assertion names the fixture ID or
  spec section it derives from.
- Small commits, one concern each.
- Arabic examples in docstrings and comments are encouraged — they make review far
  easier for a bilingual reviewer.
- Prefer explicit over clever. A reviewer re-running this in two years matters more
  than concision.

---

## Citation and licence

Corpus: **ArabJobs** ([arXiv:2509.22589](https://arxiv.org/abs/2509.22589)), CC-BY.
Used as a dependency; no Arabic-resource novelty is claimed.

Method adopted from Goyal et al.
([arXiv:2604.06097](https://arxiv.org/abs/2604.06097)) — SD-matched competitor
pools and per-cell variance reporting.

Rationality feature: Alkuhlani & Habash (2011), via
[CAMeL Tools](https://github.com/CAMeL-Lab/camel_tools) 1.6.

Repository licence: to be determined before release.
ArabJobs redistribution permission is an outstanding query — C1 reports aggregate
statistics only.
