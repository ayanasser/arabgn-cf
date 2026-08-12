# ArabGN-CF — build status

**Last updated:** 13 August 2026 · **Live document** — updated as work lands.
**Companion:** `docs/AUTHOR-ACTIONS.md` — what is waiting on you.

Legend: ✅ done · 🟡 partial (reason given) · ⛔ blocked (blocker named) · ⬜ not started

---

## Summary

| | Count |
|---|---|
| Phases complete | 6 of 11 (0, 1, 2A, 3, 9, 10-machinery) |
| Phases partial | 2 (2A, 2B) |
| Phases blocked | 6 (4, 5, 6, 7, 8–11) |
| Tests passing | **257** (+1 skipped, +1 xfailed finding) |
| Decisions closed | 7 of 18 |
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

## 4. Phase 2A — Adjudication tooling ✅ (tooling) / ⛔ (gold set)

Buildable without you; the **gold set** is not.

| Item | Status |
|---|---|
| Blind annotation interface (§8.2) | ✅ structural — `AnnotationItem` has no prediction fields |
| `unclear` recorded, never coerced (§8.1) | ✅ |
| Append-only store, annotator id + timestamp | ✅ no update/delete path exists |
| Stratified sampling (§8.3) | ✅ error class is part of the stratum key |
| Cohen's κ + κ ≥ 0.7 hard gate | ✅ raises, does not warn |
| Third-annotator adjudication (§8.4) | ✅ persistent disagreement → `unclear` |
| Joint θ separability check (ADR 001) | ✅ sweeps both parameters |
| CLI (`annotate`, `kappa`) | ✅ `arabgn/adjudication/cli.py` |
| Sentence segmentation for display context | ✅ `arabgn/analysis/segment.py` (frozen) |
| Pool builder → `items.jsonl` / `manifest.jsonl` | ✅ `arabgn/adjudication/pool.py` |
| **Pool drawn — 200 items, seed 20260812** | ✅ `build/pool/` (gitignored: ArabJobs text) |
| **Annotated gold set** | ⛔ **human lead time — days** |

### Corpus sweep behind the pool — 13 August 2026

Not a C1 result: Tiers A/B only, provisional θ. Reported because the counts are
large enough to change two open decisions.

Re-run 13 August with Tier C's adjective branch live.

| | |
|---|---|
| documents | 8,546 |
| tokens analysed | 645,458 |
| cues detected | 411,520 |
| classified — Tiers A, B, C | 365,709 |
| **verbs skipped at the agreement step — D8** | **12,085** |
| collapsed — advertisement repeated verbatim | 33,726 |
| abstentions | 170,694 (46.7%) |

Tier C is **68,718** cues — 61,551 adjectives and 7,167 verbs. The verbs are
present because AB4 fires *before* the agreement step: a verb whose candidates
disagree on gender abstains without needing a pro-drop default, so that decision
is D8-independent.
| `referent = applicant` | **0** — D7 is open, so every rational cue abstains under AB6 |

Abstain triggers, all 296,991 Tier A/B cues:

| Trigger | Count | Share of abstentions | Depends on θ? |
|---|---|---|---|
| **AB4** — gender disagreement | **87,485** | **51%** | **no** |
| AB2 — agreement target not identifiable | 24,994 | 15% | no |
| AB5 — form/functional divergence | 23,934 | 14% | no |
| AB1 — rationality unresolved | 18,283 | 11% | yes |
| AB6 — role test indeterminate | 13,536 | 8% | yes |
| AB3 — agreement target itself abstains | 2,462 | 1% | yes |

**AB2, AB4 and AB5 do not depend on θ**, so 80% of the abstain queue does not move
when θ is calibrated. D14 therefore governs half the queue corpus-wide, not one
fixture pair.

Two further numbers from this run:

- **Tier C abstains 77% of the time** — 52,672 of 68,718. Only 16,046 resolve,
  all to `non_applicant` inherited from an irrational target. Architecture §8.1
  predicted Tier C would be the weakest tier and that hiding it would not be
  defensible; that is now measured rather than anticipated.
- **AB2 is 24,994** — for roughly a quarter of Tier C cues no agreement target is
  recoverable by adjacency. That is the declared limit of the no-parser method
  (`agreement_target.py`), now quantified rather than asserted.

### R3 is uncertifiable while D7 is open — 13 August 2026

R3 (agreement-free) is the register whose entire purpose is certifying that no
applicant-referring gender marking is present. The naive check — count cues
labelled `applicant`, require zero — would **certify every document today**,
because with the role test indeterminate no cue can be labelled `applicant` at
all.

`registers.check_r3` therefore treats an abstention as *unresolved*, never as
*not applicant* (prohibition 3), and returns a third outcome: `certifiable =
False`. While D7 is open every rational cue abstains under AB6, so no R3 document
certifies. That is the honest position — the alternative is a register certified
by a tagger incapable of finding the thing it certifies the absence of.

This makes D7 a blocker for **C2's register typology** as well as for C1's Tier C.

## 5. Phase 2B — Tier A/B extractor ✅ (code) / ⛔ (frozen θ)

| Item | Status |
|---|---|
| Disambiguator wrapper, `top=100` | ✅ rejects any other `top` |
| Determinism assertion (D13) | ✅ 3 runs byte-identical, asserted in tests |
| Cue detection + POS filter (§3.1) | ✅ N01/N02 pass against the real model |
| Probability-mass rationality rule (§4.2) | ✅ reproduces ADR 001 to <0.001 |
| θ sweep over fixtures | ✅ `docs/theta-sweep.md` |
| Tier A/B classification (§5) | ✅ incl. AB1, AB4, AB5, AB6 |
| Tier C → `NotImplementedError` | ✅ names cue, POS, D7 and D8 |
| **Frozen θ values** | ⛔ Phase 4 |

## 6. Phase 3 — Twin symmetry (provisional) ✅ — **and it found a real asymmetry**

| Item | Status |
|---|---|
| `check_twin_symmetry` — count, tier, referent, trigger | ✅ |
| Reusable property sweep over arbitrary pairs | ✅ `check_all_pairs` |
| No token-count assertion (architecture §5.2) | ✅ asserted absent |
| T01 end-to-end through the real model | ⚠️ **`xfail(strict)` — finding D14** |
| T02 | ⛔ REVIEW, skipped |

**Finding D14 — AB4 is gender-asymmetric.** `حاصلة` abstains under AB4 (34
candidates, 12 of them `gen=m`); `حاصل` abstains under AB1 (19 candidates, 0
`gen=f`). Same label, different trigger, therefore different adjudication strata.
Structural, not a code bug. `docs/findings/001-ab4-is-gender-asymmetric.md`.

Still a smoke test — Tiers A/B only. Phase 6 is the binding form.

## 7. Phases 4–11 ⛔

| Phase | Blocker |
|---|---|
| 4 — gold set κ ≥ 0.7 + θ calibration | Human annotation. **Both gates can fail.** |
| 5 — Tier C | 🟡 **adjective branch built and wired into `classify`** — 61,551 cues classified over the corpus, spec §5's four steps, AB2/AB3 routing, agreement search bounded to the cue's segment. Target *identification* holds for C01–C03; **referent** resolution holds for C01/C02, and **C03 is `xfail(strict=True)` on D7** — its target `المرشحة` is rational, so reaching `applicant` needs the role test. **Verb branch blocked on D8** (pro-drop); `شمس` on D9. |
| 6 — twin symmetry, all tiers | Phase 5 |
| 7 — ArabJobs sweep → C1 tables | 🟡 **loader built** — all 8,546 ads load, checksummed, ta-marbuta preserved. The **sweep** still needs Phases 4–6 and D9. |
| 8 — generator | 🟡 **invariants built, generator not.** `arabgn/analysis/twins.py` — §5.2's four enforced invariants plus the tokenization delta measured per audit subject rather than forced to zero. `arabgn/analysis/registers.py` — R1–R5 machine-checked invariants. Both frozen. The **generator** needs the method decision (template / LLM / hybrid), and **R3 cannot certify any document while D7 is open** — see below. |
| 9 — blinding, freeze | ✅ **built** — HMAC blinding, ordering-leak detection, explicit-manifest freeze, CLI. Only the **external time anchor** still needs a human account (~1 h). |
| 10 — analysis machinery | ✅ **built** — synthetic backend, variance decomposition, two-way cluster-robust SE, Holm, TOST, power curves, guarded reporting. The **pilot** still needs the generator (Phase 8) and a scoring pass. σ²_cv wording still owed. |
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
| **AB4 gender-asymmetric (D14, P0)** | `docs/findings/001-...md` |
| spec §4.2 says log-probabilities; evidence uses `score` | `docs/theta-sweep.md` §5 |

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
| Tier C adjectives | CAMeL ships **no dependency parser**, so adjacency is the available method, not a shortcut — declared with its failure modes (coordination, intervening modifiers, predicative use) rather than left implicit. | The freeze-manifest guard fired for the **second** time, catching `agreement_target.py` before it could sit outside the hash. C04's competing-heads case abstains under AB2 with both candidates reported, rather than picking one and silently settling a REVIEW fixture. |
| ArabJobs loader | Corpus has **no seniority column**, so §3.2's "from source metadata" is not satisfiable and spec §8.3's seniority stratum is degenerate. Recorded as `UNSPECIFIED` with an explicit `seniority_derived=False` flag rather than letting the enum default read as a finding. | ArabJobs ships its **own** ad-level `gender` label (male 4,767 / neutral 2,405 / female 1,374). Deliberately **not** used as tagger input — consuming it would make C1 circular. Retained for convergent-validity comparison only, with a test asserting it never reaches a `DocRecord`. |
| Phase 10 analysis | **Generative model was wrong.** With only level effects, both `ad[a]` and `pair[c]` cancel in the twin difference, so differences are iid and σ²_ad/σ²_cv in the §7.3 formula would both be zero — the formula would reduce to the iid case. **Fixed**: added ad×gender and pair×gender interaction terms, which survive differencing and are what σ²_ad and σ²_cv actually denote. This also pins the §10 #4 definition: σ²_cv is twin discordance. | A test asserted inflation ≈1.0 from a single seed and read 0.79. Investigated rather than widening the tolerance: the estimator is correct (mean 0.988 over 20 seeds at 40×50, 1.002 at 100×100) and seed 23 was a low draw. **Fixed** by asserting the expectation across seeds. With interaction terms the inflation is 4.12×. |
| Phase 9 blinding/freeze | Test asserted `'f' not in token` — but `f` is a hex digit, so it appears in any digest by chance. A flawed assertion, not a leak. **Replaced** with an avalanche test (>30% of hex digits must change when polarity flips), which tests the property that matters. | `freeze.py` is pure by design but nothing could **run** it against the repo. **Added** `arabgn/freeze_cli.py` (I/O, unfrozen) with the real 11-source manifest, plus a test asserting the manifest never drifts behind `arabgn/analysis/`. Real hash computes: `edbb4935…`, and the CLI warns that it is NOT a pre-registration freeze while θ is unset. |
| Phase 3 symmetry | Unused test imports; `genders_differ` missing from `__all__`. **Fixed**. | Added an end-to-end run through the real model — the pure-layer test used recorded masses and would never have caught this. **It failed, and the failure is real**: AB4 fires on `حاصلة` and not `حاصل`. Recorded as finding D14 and marked `xfail(strict=True)` rather than weakened. |
| Phase 2B tagger | `rationality_mass` used `+` to sum float scores — **not associative**, so mass differed in the last bits by candidate order (0.5625 vs 0.5625000000000001). A real prohibition-6 violation: a mass near θ could resolve differently, and serialised output would not be byte-stable so the freeze hash would not reproduce. **Fixed**: `math.fsum`, exactly-rounded. Also `blind()` hardcoded `DocType.AD`. | `form_divergence` / `dominant_gender` missing from `__all__`; unused imports. **Fixed**. θ sweep over 9 real fixtures shows the feasible region is 2,249 grid points, **not** the ~7-point window ADR 001 estimated from three cases — risk is lower than recorded. |
| Phase 1 normalisation | Guard baselined on raw input; NFC composition flagged as a violation. **Fixed** — baseline is now the NFC form. | — |
| Phase 2A adjudication | (1) Over-sampling weighted the *whole stratum* containing an error-class cue, not the class — a `مطلوبة` cue gave 9 neighbours 3× weight too. **Fixed**: error class is now part of the stratum key. (2) `adjudicate` missing from `__all__`. (3) `id()` used for test ids — a memory address, nondeterministic. Both **fixed**. | `strata_fields` declared 5 names while keys carried 6 elements, so keys could not be reconstructed positionally. **Fixed**: `error_class` appended. Verified over-sampling now draws §7.1 at 2.22× base rate (was diffuse). |
