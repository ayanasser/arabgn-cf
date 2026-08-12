# ArabGN-CF — build status

**Last updated:** 12 August 2026 · **Live document** — updated as work lands.
**Companion:** `docs/AUTHOR-ACTIONS.md` — what is waiting on you.

Legend: ✅ done · 🟡 partial (reason given) · ⛔ blocked (blocker named) · ⬜ not started

---

## Summary

| | Count |
|---|---|
| Phases complete | 3 of 11 (Phase 0, 1, 3) |
| Phases partial | 2 (2A, 2B) |
| Phases blocked | 6 (4, 5, 6, 7, 8–11) |
| Tests passing | see §6 |
| Decisions closed | 7 of 13 |
| REVIEW fixtures outstanding | 10 of 27 |

**The critical path is human, not technical.** Everything buildable without your
input or an annotated gold set is done. See `docs/AUTHOR-ACTIONS.md`.

---

## 1. Phase 0 — Doc reconciliation ✅

| Item | Status | Where |
|---|---|---|
| Architecture PDF → Markdown | ✅ | `docs/architecture.md` |
| Figures 1 & 2 flagged unextractable | ✅ | §2, §4.3 — **raster, consult the PDF** |
| Arabic reconstruction verified | ✅ | §12 — 10/10 tokens matched spec spelling |
| Stale path references | ✅ | all resolve |
| ADRs 001–007 | ✅ | `docs/decisions/` |
| Document amendments applied | ✅ | architecture §3.2/4.4/4.5/8.1, spec §4.2/§5/§9, CLAUDE.md |
| Decision register updated | ✅ | `docs/decision_register.md` |
| Proposal corrections itemised | ✅ | `docs/proposal-corrections.md` |
| Build + project plans | ✅ | `docs/build-plan.md`, `docs/project-plan.md` |

## 2. Decisions

| ID | Decision | Status |
|---|---|---|
| D1 | Abstain mechanism → **calibrated** | ✅ ADR 001 |
| D2 | Tier membership → (a) + `morph_class` | ✅ ADR 002 + probe appendix |
| D3 | `DocRecord` + `doc_type` | ✅ ADR 003 |
| D4 | Fixture `group:` + scoped never-edit rule | ✅ ADR 004 |
| D5 | Diacritic preservation | ✅ ADR 005 (known gap: stacked marks) |
| D10 | Lockfile → `uv` | ✅ ADR 006 |
| D11 | Freeze boundary → split + manifest | ✅ ADR 007 |
| D6 | Enclitic pronouns | ⛔ **you** — scopes Phase 2B |
| D7 | Role test + closed list | ⛔ **you** — blocks Phase 5 |
| D8 | Pro-drop default | ⛔ **you** — blocks Phase 5, C05–C07 |
| D9 | Institution-name list | ⛔ **you** — blocks Phase 7 accuracy |
| D12 | Abstain trigger count | 🟡 applied (4→6); **needs your sign-off** |
| D13 | Determinism | 🟡 asserted for contracts; tagger assertion in 2B |

## 3. Phase 1 — Skeleton and contracts ✅

| Item | Status | Where |
|---|---|---|
| `pyproject.toml`, `uv.lock`, Python 3.12 pin | ✅ | `--exclude-newer 2026-08-12` |
| `DocRecord`, `TaggedCue`, 8 enums | ✅ | `arabgn/contracts.py` |
| `rat_candidates` as `frozenset`, sorted serialisation | ✅ | prohibition 6 |
| Abstain/tier invariants enforced in `__post_init__` | ✅ | spec §6, arch §4.5 |
| NFC-only normalisation + prohibition-1 guard | ✅ | `arabgn/analysis/text.py` |
| Fixture loader (group / confidence / assert_type) | ✅ | `tests/conftest.py` |
| REVIEW skips name their blocking decision | ✅ | count printed in pytest header |
| Normalisation + contract tests | ✅ | `tests/` |

## 4. Phase 2A — Adjudication tooling 🟡

Buildable without you; the **gold set** is not.

| Item | Status |
|---|---|
| Blind annotation interface (§8.2) | ⬜ |
| `unclear` recorded, never coerced (§8.1) | ⬜ |
| Append-only store, annotator id + timestamp | ⬜ |
| Stratified sampling (§8.3) | ⬜ |
| Cohen's κ + κ ≥ 0.7 hard gate | ⬜ |
| Third-annotator adjudication (§8.4) | ⬜ |
| Joint θ separability check (ADR 001) | ⬜ |
| **Annotated gold set** | ⛔ **human lead time — days** |

## 5. Phase 2B — Tier A/B extractor 🟡

| Item | Status |
|---|---|
| Disambiguator wrapper, `top=100` | ⬜ |
| Determinism assertion (D13) | ⬜ |
| Cue detection + POS filter (§3.1) | ⬜ |
| Probability-mass rationality rule (§4.2) | ⬜ |
| θ sweep over fixtures | ⬜ |
| Tier A/B classification (§5) | ⬜ |
| Tier C → `NotImplementedError` | ⬜ |
| **Frozen θ values** | ⛔ Phase 4 |

## 6. Phase 3 — Twin symmetry (provisional) ⬜

Smoke test only — Tiers A/B test symmetry-in-abstention, not
symmetry-in-classification. Phase 6 is the binding form.

## 7. Phases 4–11 ⛔

| Phase | Blocker |
|---|---|
| 4 — gold set κ ≥ 0.7 + θ calibration | Human annotation. **Both gates can fail.** |
| 5 — Tier C | D7, D8, D9 |
| 6 — twin symmetry, all tiers | Phase 5 |
| 7 — ArabJobs sweep → C1 tables | Phases 4–6, D9 |
| 8 — generator | Phase 7; generation method undecided |
| 9 — blinding, freeze, time anchor | External service (~1 h) |
| 10 — analysis, pilot, power → C3 | GPU; σ²_cv definition (arch §7.3) |
| 11 — pre-registration → C4 | C3 numbers |

## 8. Known gaps carried forward

| Gap | Raised in |
|---|---|
| Stacked-diacritic normalisation untested | ADR 005 |
| `stemcat` → `morph_class` mapping table unauthored | ADR 002 appendix |
| `stemcat` does not separate `مسؤول` readings | ADR 002 appendix |
| Figures 1 & 2 exist only in the PDF | `docs/architecture.md` §12 |
| Proposal artifact claims false | `docs/proposal-corrections.md` |
| σ²_cv notation ambiguous | architecture §7.3 |

---

## Review criteria

Every item below is reviewed **twice** before commit, against:

1. **Traceability** — each assertion names a fixture id or a spec section.
2. **Prohibitions** — 1 (orthography), 2 (no training), 3 (abstentions kept),
   4 (no "no bias"), 5 (no new deps), 6 (determinism).
3. **No assert-current-behaviour** — no test encodes what the code happens to do.
4. **Freeze boundary** — `analysis/` pure and import-clean; `tagger/` isolated.
5. **Ground truth untouched** — no protected fixture field altered.
6. **Correctness** — does it actually do what it claims, under adversarial reading.

Findings from each pass are recorded in the review log below.

## Review log

| Item | Pass 1 findings | Pass 2 findings |
|---|---|---|
| Phase 1 normalisation | Guard baselined on raw input; NFC composition flagged as a violation. **Fixed** — baseline is now the NFC form. | — |
