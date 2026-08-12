# Phase 0 closure + Phase 1 — ArabGN-CF

**Status:** approved 12 August 2026. Supersedes the phase plan in the original
kickoff prompt; adopts the build order in `docs/decision_register.md` Part 1.
**Scope:** closes Phase 0 and builds Phase 1, stopping at the Phase 1 review gate.

## Context

ArabGN-CF is a measurement instrument supporting a NILES 2026 SS2 paper. Its
output is a scientific claim, so correctness and reproducibility outrank speed and
elegance (CLAUDE.md).

The repository currently contains documentation and fixtures but **no code**.
`docs/decision_register.md` holds thirteen open decisions and states that writing
an implementation prompt before D1–D6 and D10 close "would resolve them by
default, which is the defect this register exists to prevent."

Seven are now closed by author decision:

| ID | Decision | Resolution |
|---|---|---|
| D1 | Abstain mechanism | **Calibrated** (spec §4.2). Threshold-free fails empirically in both variants. Architecture §4.4 is an author error about trigger 1 (= AB1) and needs rewriting, not reinterpreting. |
| D2 | Tier membership | **(a) + `morph_class`.** Keep mechanism-based POS tiers; record enough on each `TaggedCue` to reconstruct linguistic class; report §8.1 as tier × morph-class cross-tabulation. Gated on a feasibility probe. |
| D3 | `AdRecord` | Rename `DocRecord`, add `doc_type: ad \| cv`. |
| D4 | Fixture `group:` | Add the key. Tighten the never-edit rule to name protected fields rather than the whole file. |
| D5 | Diacritics | Byte-identity fixture on single-mark tokens only; sidesteps NFC combining-mark reordering rather than answering it. |
| D10 | Lockfile | `uv`, with `--exclude-newer`. Lock exists from the first commit. |
| D11 | Freeze boundary | Split: pure logic frozen and I/O-free; model loading unfrozen, pinned via `db_version` / `toolkit_version` on every cue. |

**Still open, and deliberately not resolved here:** D6 (enclitics — scopes Phase
2B), D7 (role test), D8 (pro-drop), D9 (institution list), D12 (abstain-trigger
count reconciliation — direction stated, needs sign-off), D13 (determinism —
verified, becomes a test).

This plan closes Phase 0 and builds Phase 1 of the register's corrected build
order, stopping at the Phase 1 review gate.

---

## Part A — Phase 0 closure

### A0. Commit this plan to the repository ✔ done

This file. It records the corrected build order, the seven closed decisions with
the evidence behind them, and the three items flagged but deliberately not
decided — none of which is recoverable from the repository alone.

Read alongside `docs/decision_register.md` (the thirteen decisions and their
priorities) and `docs/decisions/` (one ADR per closed decision).

### A1. ADRs

Create `docs/decisions/`. One ADR per closed decision, each naming its `D`-number
so the register and the ADR set stay cross-referenced.

| File | Covers |
|---|---|
| `001-abstain-mechanism-calibrated.md` | D1 |
| `002-tier-membership-and-morph-class.md` | D2 |
| `003-docrecord-and-doc-type.md` | D3 |
| `004-fixture-group-key-and-scoped-never-edit-rule.md` | D4 |
| `005-diacritic-preservation.md` | D5 |
| `006-lockfile-uv.md` | D10 |
| `007-freeze-boundary.md` | D11 |

**ADR 001 carries the most weight** — θ becomes a pre-registered constant. It must
cite the measurements, not the person who produced them:

- Raw candidate membership abstains on A01 (`المرشحة`) and A02 (`مهندس`), the two
  cleanest positives. Unusable.
  *(Corrected from the source table, which labelled the `مهندس` row A04; A04's cue
  is `خبرة`. Author confirmed the row is A02.)*
- Rank-based (top-1 vs top-2) resolves B01 `حاصلة` to irrational — the exact error
  AB1 exists to catch.
- Probability mass: `خبرة` i=0.904; `المرشحة` r=0.747, i=0.254; `حاصلة` i=0.676
  r=0.324 (ad) and i=0.670 r=0.330 (CV).

Record the **joint** feasible region, not a single window. Working the §4.2 rule
against those masses:

```
خبرة   → irrational : θ_high ≤ 0.904 , θ_low > ~0.096
المرشحة → rational   : θ_high ≤ 0.747 , θ_low > 0.254
حاصلة  → abstain    : (θ_high > 0.676) OR (θ_low ≤ 0.324)
```

The abstain constraint is a **disjunction**, so two independent routes exist:
`θ_high ∈ (0.676, 0.747]` **or** `θ_low ∈ (0.254, 0.324]`. Both windows are ~7
points. A separability gate that sweeps only θ_high would report "no θ exists"
while a feasible θ_low region was available — the gate must sweep jointly.

Also record: `حاصلة` sits at r=0.324 / 0.330 across two very different contexts.
Context is not moving the minority reading. That stability is evidence that
abstaining is *correct behaviour* rather than a limitation — a reportable point,
per the author.

**No θ values are set.** Calibration stays at Phase 4 against the gold set.

### A2. Document amendments

| File | Change | Decision |
|---|---|---|
| `docs/architecture.md` §4.4 | Rewrite trigger 1. Delete the "defensible without calibration data" claim; point to spec §4.2. | D1 |
| `docs/architecture.md` §4.4 | Add AB3 and AB6 so the list is six, matching spec §6. **Flag at review** — D12 direction is stated but unsigned. | D12 |
| `docs/architecture.md` §3.2 | `AdRecord` → `DocRecord`; add `doc_type enum ad \| cv`. | D3 |
| `docs/architecture.md` §4.5 | Add `morph_class`; note `rat_candidates` is a `frozenset` serialised sorted. | D2, D13 |
| `docs/architecture.md` §8.1 | Tier-wise breakdown becomes tier × morph-class cross-tabulation. | D2 |
| `docs/linguistic-spec.md` §4.2 | Clear the ⚠; record the mass rule as settled; state the joint separability gate. | D1 |
| `docs/linguistic-spec.md` §5 | State that tiers are mechanism-based and linguistic class is recorded separately, not inferred from tier. | D2 |
| `docs/linguistic-spec.md` §9 | Update the open-items table. | all |
| `CLAUDE.md` | Tighten the never-edit rule to name protected fields: `text`, `cue`, `expected_label`, `expected_tier`, `abstain_id`, `expected_text_norm`, `expected_cue_emitted`. Add `uv` to setup. Reword the freeze boundary per D11. | D4, D10, D11 |
| `docs/decision_register.md` | Mark D1–D5, D10, D11 closed with ADR links. | — |

§12 of `architecture.md` (conversion log) records that this file is a conversion;
every amendment above must be appended to it so a reviewer can tell converted
text from post-conversion edits.

### A3. Fixture file

Authorised edits only, under the tightened D4 rule:

- Add `group: <1–9>` to all 26 existing fixtures, matching the section comments.
- Add `O03`, harakat: `مُهَنْدِسَة` — single mark per base letter, no stacking, so
  NFC is identity and `expected_text_norm` is byte-identical. Note in the fixture
  that this **avoids** the combining-mark reordering question rather than
  answering it, so a later stacked-mark fixture is still owed.
- Extend the header comment to document `group`, `assert_type`,
  `expected_cue_emitted`, `text_f` / `text_m` — currently undocumented.

No protected field on any existing fixture is touched.

### A4. Proposal corrections

The SS2 proposal is **not yet submitted**. It claims "Phase 0 of the instrument is
complete and tested", **117 automated tests**, **~7,900 lines**, and a feasibility
table with "Instrument ready, blocking" (4–7 Aug) and "Tagger implemented"
(6–10 Aug). None of this exists in the repository.

Deliverable: `docs/proposal-corrections.md` — an itemised list of every claim
needing rewrite, with the repository-verified position for each. The PDF is not
editable here; the author edits the source document.

Per the author, this outranks everything else in the register. **It should be
cleared before Part C starts.**

---

## Part B — `morph_class` feasibility probe (go/no-go)

The author's caveat on D2: it is unknown whether active-participle status can be
reliably derived from CAMeL analysis fields. It may need a frozen lexeme list or
pattern matching. **Check before committing to the cross-tab; fall back to plain
(a) if unreliable.**

This is the only step needing `camel_data` downloads.

Probe the analysis dict for the D2 table's tokens — `حاصلة`, `حاصل`, `حاصلا`,
`وحاصلة` (POS `noun`, Tier B); `المتقدم`, `المسؤولة`, `مسؤول`, `العاملة` (POS
`adj`, Tier C); `خريجة`, `المرشحة` (agentive noun, Tier A) — and report which
fields separate the classes: `pattern`, `root`, `lex`, `bw`, `stem`, `diac`,
`pos`, `asp`, `vox`.

Output: `docs/decisions/002-appendix-morph-class-feasibility.md`, with a **go**
(fields suffice — record the derivation) or **no-go** (fall back to plain (a),
drop the cross-tab, amend ADR 002). Either outcome is recorded before the contract
is written, because `morph_class` is a field on `TaggedCue`.

---

## Part C — Phase 1 build

### C1. Packaging

`pyproject.toml`: `arabgn` package; `camel-tools==1.6.*` (CLAUDE.md settles 1.6);
dev extra `pytest`, `pyyaml`. Nothing else — prohibition 5.
`uv lock --exclude-newer <date>`; commit `uv.lock` in the same commit.

### C2. Layout and the freeze boundary

D11 splits pure logic from I/O. That places two Phase 1 modules differently from
the original prompt, and the plan states it rather than doing it silently:

```
arabgn/
  contracts.py          dataclasses + enums, no I/O
  analysis/
    __init__.py         freeze-boundary docstring
    text.py             normalise() — pure, frozen
  tagger/               (Phase 2B) model loading, I/O, unfrozen
```

`text.py` sits under `analysis/` because normalisation is pure and is, per
architecture §3.2, "the single most important preprocessing decision in the
system" — it must enter the freeze.

**Recommendation for the freeze set:** define it as an **explicit manifest of
paths** in config rather than "whatever is in `arabgn/analysis/`". A directory
glob silently changes the hash when a file is added, which is the opposite of what
§6.3 wants. `contracts.py` belongs in the manifest — it defines output shape — but
does not belong under `analysis/`. Flag at the gate.

### C3. Contracts — `arabgn/contracts.py`

- `DocRecord` per amended §3.2 (with `doc_type`).
- `TaggedCue` per amended §4.5 (with `morph_class`, subject to Part B).
- Enums: `Tier` (A|B|C), `Referent` (applicant|non_applicant|ABSTAIN),
  `AbstainTrigger` (AB1–AB6, spec §6), `Gender` (m|f), `Rationality` (r|i|n),
  `DocType` (ad|cv), `MorphClass` (subject to Part B).
- `rat_candidates` stored as `frozenset`, serialised in sorted order — prohibition
  6 forbids set iteration for output.

### C4. Normalisation — `arabgn/analysis/text.py`

Unicode NFC only. Docstring carries prohibition 1 and an Arabic example showing
`ة` surviving. No alef/ya/ta-marbuta mapping, no diacritic stripping.

### C5. Fixture loader — `tests/conftest.py`

Parse the YAML; expose fixtures by `group`, by `confidence`, and by `assert_type`
— the file has four shapes: cue-label, `expected_cue_emitted: false`,
`assert_type: normalisation`, `assert_type: twin_symmetry`. Every `REVIEW` fixture
skips with a reason naming the open spec section. Deterministic ordering
throughout — no set iteration, no dict-order reliance.

### C6. Tests

- `tests/test_normalisation.py` — O01 (ta-marbuta), O02 (hamza), O03 (harakat).
  Each assertion names its fixture ID.
- `tests/test_contracts.py` — `rat_candidates` serialisation stable across two
  constructions with different insertion order (D13).

No test asserts current behaviour; every assertion traces to a fixture ID or a
spec section.

### C7. Commits

One concern each, conventional messages: ADRs → doc amendments → fixture edits →
proposal corrections → probe appendix → packaging → contracts → normalisation →
loader → tests.

---

## Verification

```bash
uv sync --extra dev
uv run pytest -v
```

Expected at the Phase 1 gate:

- `test_normalisation.py` — 3 passed. O01 proves `ة` survives; failure here
  invalidates the study (CLAUDE.md prohibition 1).
- `test_contracts.py` — passed.
- Collection reports 10 `REVIEW` fixtures skipped, each with a reason naming its
  open spec section — not silently absent.
- **No `camel_data` download needed.** Phase 1 imports no model. Part B's probe is
  the only step that does, and it is not part of the test suite.

Byte-level check that NFC did not alter the fixtures:

```bash
uv run python -c "import unicodedata as u,pathlib; \
s=pathlib.Path('tests/fixtures/tagger_fixtures.yaml').read_text(); \
print('NFC is identity:', u.normalize('NFC',s)==s)"
```

**Gate deliverable:** the contract definitions and the normalisation test output,
then stop.

---

## Out of scope

No tagger, no cue detection, no tier classification, no θ values, no twin-symmetry
harness, no adjudication tooling. D6–D9 and D12–D13 remain open. Phase 2B does not
begin until D6 closes and the Part A proposal correction is cleared.
