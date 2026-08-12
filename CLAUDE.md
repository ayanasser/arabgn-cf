# CLAUDE.md

Instructions for AI coding agents working in this repository. Read this before
writing any code. If something here conflicts with a suggestion you were about
to make, this file wins.

---

## What this project is

ArabGN-CF is a **measurement instrument** for auditing gender bias in Arabic
résumé ranking. It supports an academic paper (NILES 2026, SS2) whose central
claims are that (a) Arabic grammatical gender agreement carries applicant gender
through name redaction, and (b) counterfactual hiring audits are usually
underpowered to claim "no bias".

Full design: `docs/architecture.md`. Linguistic rules: `docs/linguistic-spec.md`.
Open decisions: `docs/decision_register.md`. Closed ones: `docs/decisions/`.
Build order and current phase: `docs/project-plan.md`, `docs/build-plan.md`.

**Read the register before implementing anything.** Several decisions are open and
block specific phases; resolving one by default is the failure mode it exists to
prevent.

**The output of this repo is a scientific claim, not a product.** Correctness and
reproducibility outrank speed, elegance, and convenience in every trade-off.

---

## Hard prohibitions

These are not style preferences. Violating any of them invalidates results.

### 1. Never normalise Arabic orthography

Do **not** map `ة` → `ه`, `أ إ آ` → `ا`, or `ى` → `ي`.

Ta-marbuta (`ة`) is the primary feminine marker. It is the signal this entire
project measures. Standard Arabic preprocessing pipelines strip it as a matter of
course — that habit would silently destroy the study.

Unicode NFC is the only permitted normalisation. `tests/test_normalisation.py`
asserts this; do not weaken or skip that test.

### 2. Never train, fine-tune, or adapt a model

Every model in this repo is measured, never trained. This includes "just a small
classifier" for referent resolution. A trained component would have to enter the
cryptographic freeze and would make the audit subjects non-reproducible.

If a task seems to need training, stop and raise it rather than implementing it.

### 3. Never drop abstentions from metrics

Abstained cues are reported as their own category. Do not exclude them to improve
precision, and do not silently assign them to a class. Any metric function that
takes abstentions must report the abstention rate alongside.

### 4. Never emit "no bias"

The reporting layer refuses this phrase by design. It is not a bug. No test can
license the claim, so no output may make it. See `docs/architecture.md` §7.4.

### 5. Never add a dependency without asking

Every dependency changes the lockfile and therefore the freeze hash. Adding one is
a project decision, not an implementation detail.

### 6. Never introduce nondeterminism

The project's central claim is that a reviewer can reproduce results from a hash.
Forbidden: unseeded sampling, iteration over `set`, relying on dict ordering for
output, parallelism that changes output order, wall-clock or PID in any derived
value.

Every function producing output must be deterministic given the config and seed.

---

## Environment setup

```bash
uv sync --extra dev          # uv.lock is authoritative; see ADR 006

# Model data is a SEPARATE step. Installing packages does not fetch it.
camel_data -i morphology-db-msa-r13
camel_data -i disambig-bert-unfactored-msa
```

Dependency resolution is pinned with `uv lock --exclude-newer <timestamp>`, so the
lockfile is reproducible from a date. `uv.lock` enters the freeze hash
(`docs/architecture.md` §6.3). A reviewer reproduces with `uv sync --frozen`,
which fails loudly if the lock and `pyproject.toml` disagree.

If you hit `FileNotFoundError` under `~/.camel_tools/data/`, the data step was
skipped. Run it — do not switch toolkits to work around it.

**The download name and the API name differ.** `camel_data -i` takes
`morphology-db-msa-r13`; `MorphologyDB.builtin_db()` takes **`calima-msa-r13`**.
Passing the download name to the API raises `KeyError`, not a helpful message.
Verified 12 Aug 2026 — see `docs/decisions/002-appendix-morph-class-feasibility.md`.

---

## Toolkit decisions (settled — do not revisit)

| Decision | Choice | Why |
|---|---|---|
| Morphology | CAMeL Tools 1.6, `morphology-db-msa-r13` | Exposes `gen`, `form_gen`, and `rat` separately |
| Disambiguator | `BERTUnfactoredDisambiguator`, **not** MLE | MLE misgenders `مهندسة` as masculine and `تخرج` as feminine; BERT gets both right |
| Candidate retention | `top=100`, **never** default | Default returns top-1, which destroys the Tier B abstain mechanism entirely |

The `top=100` setting is load-bearing. With top-1 there is only ever one candidate
analysis, so "candidates disagree on rationality" can never fire and every
ambiguous cue is silently resolved.

---

## Known tool behaviour you must design around

Verified 12 August 2026. These are measured facts, not guesses.

- **Top-1 rationality is unreliable on recruitment text.** `حاصلة` in
  `مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة` resolves to `rat=i` when it
  refers to the applicant. Use the *candidate set*, not the top analysis, for
  rationality decisions.
- **Candidate sets are noisy.** `معتمدة` returns `{i, n, r}` and `شمس` returns
  `{i, n, r}`. Raw set membership is too permissive as an abstain trigger — weight
  by candidate probability. See `docs/linguistic-spec.md` §4.
- **`مطلوبة` returns `rat=i` on all readings** even when it refers to the sought
  person. Known systematic error class. Do not special-case it in code; it is
  measured and reported as a limitation.
- **Function words are spuriously ambiguous.** `على` returns `rat={n, na, r}`.
  Restrict cue detection to content POS classes.

---

## Architecture constraints

- The three referent tiers (A, B, C) must remain **separately identifiable** in
  output. `docs/architecture.md` §8.1 requires tier-wise precision and recall. Do
  not collapse them into one function or lose the tier label.
- The freeze set is an **explicit manifest of paths** in the run config, not a
  directory glob. A glob silently changes the hash when a file is added, and
  silently misses freeze-relevant files added elsewhere. See ADR 007.
- Modules under `arabgn/analysis/` are pure: no I/O, no side effects, no model
  loading. They enter the manifest. `arabgn/contracts.py` also enters the manifest
  — it defines output shape — but lives outside `analysis/` because both frozen
  and unfrozen layers import it.
- Model loading and caching live in `arabgn/tagger/`, which does **not** enter the
  freeze. Model identity is pinned instead by `toolkit_version` and `db_version`
  recorded on every emitted `TaggedCue` (`docs/architecture.md` §4.5), so
  provenance travels with the data rather than only with a source hash.
- Consequence for tests: `arabgn/analysis/` needs no `camel_data` and runs on a
  laptop. `arabgn/tagger/` tests do require it and are marked so a clean checkout
  fails legibly.
- The scoring layer has two backends behind one interface: a deterministic
  synthetic backend (used by all tests, no model downloads) and the real ranker
  backend. Tests must never require the real backend.

---

## Testing

```bash
pytest                       # full suite
pytest tests/test_tagger.py  # single module
```

**Fixtures are ground truth authored by a human. Never edit a fixture to make a
test pass.** If code disagrees with a fixture, either the code is wrong or the
fixture needs human review — raise it, do not resolve it yourself.

The rule protects ground truth about Arabic, so it names the fields it protects
rather than the whole file (ADR 004). **Never change any of:**

`text` · `text_f` · `text_m` · `cue` · `expected_label` · `expected_tier` ·
`abstain_id` · `expected_text_norm` · `expected_cue_emitted` · `confidence`

Those change only by the fixture author, and only through the settle-a-REVIEW
procedure. `confidence` is protected deliberately: flipping `REVIEW` → `settled`
is exactly the corruption this rule exists to prevent.

Everything else — `group`, `note`, `doc_type`, `assert_type`, header comments,
ordering — is test organisation and may be maintained by an implementer.

**Every `REVIEW` fixture is an open question, not a target.** Skip it, with a
reason naming the open spec section. Ten are currently unresolved.

Do not write tests that assert current behaviour (`assert result == <whatever it
returns now>`). Every test asserts against a value derived from
`docs/linguistic-spec.md` or from `tests/fixtures/`.

---

## Working style

- Small, reviewable commits. One module or one concern per commit.
- When a design decision comes up that is not covered here or in `docs/`, stop and
  ask rather than choosing. Record the answer in `docs/decisions/`.
- Arabic examples in code comments and docstrings are welcome and encouraged —
  they make review far easier for a bilingual reviewer.
- Prefer explicit over clever. A reviewer re-running this in two years matters
  more than concision.