# θ sweep over fixture groups 1–3

**Run:** 12 August 2026 · camel-tools 1.6.0 · `calima-msa-r13` ·
`BERTUnfactoredDisambiguator.pretrained('msa', top=100)`
**Method:** `arabgn.analysis.cues.rationality_mass` +
`arabgn.analysis.thresholds.sweep_feasible_region`
**Grid:** θ ∈ [0, 1] step 0.005, θ_low ≤ θ_high → 20,301 pairs

This is the Phase 2B deliverable required by `docs/build-plan.md`: rather than
leaving fixtures unrunnable because θ is unset, each is evaluated across the θ
grid and the passing region reported. It is also the calibration evidence spec
§4.2 says must exist.

**θ is not chosen here.** It is calibrated against the *gold set* at the Phase 4
gate, not against fixtures. This sweep bounds the search and tests whether a
feasible region exists at all.

---

## 1. Measured mass, per fixture

| Fixture | Group | Cue | Confidence | Expected | mass(r) | mass(i) | candidates |
|---|---|---|---|---|---|---|---|
| A01 | 1 | المرشحة | settled | applicant | 0.7465 | 0.2535 | 6 |
| A02 | 1 | مهندس | settled | applicant | 0.8954 | 0.1046 | 7 |
| A03 | 1 | المهندسة | settled | applicant | 0.7465 | 0.2535 | 6 |
| A04 | 2 | خبرة | settled | non_applicant | 0.0000 | 0.9039 | 15 |
| A05 | 2 | الشركة | settled | non_applicant | 0.0000 | 1.0000 | 6 |
| A06 | 2 | سنوات | settled | non_applicant | 0.0000 | 0.9524 | 9 |
| A07 | 2 | هندسة | settled | non_applicant | 0.0000 | 1.0000 | 8 |
| B01 | 3 | حاصلة | **REVIEW** | ABSTAIN | 0.3243 | 0.6757 | 34 |
| B02 | 3 | حاصل | **REVIEW** | ABSTAIN | 0.3184 | 0.6816 | 19 |

All nine cues were found, analysed in full sentence context, and reproduce
ADR 001's recorded masses to within 0.001 where they overlap.

## 2. Feasible region

| Case set | Feasible pairs | of 20,301 |
|---|---|---|
| 7 settled fixtures only (groups 1–2) | 4,950 | 24.4% |
| 9 fixtures, treating B01/B02 as binding abstains | **2,249** | 11.1% |

Adding the two Tier B abstain requirements roughly halves the region but leaves
it large and two-dimensional. Both routes from ADR 001 remain open:

| Route | Feasible pairs |
|---|---|
| via θ_high ∈ (0.676, 0.747] | 1,222 |
| via θ_low ∈ (0.254, 0.324] | 1,222 |
| satisfying both simultaneously | 195 |

## 3. The separability risk is **less severe than ADR 001 estimated**

ADR 001 derived a ~7-point window from three measurements and flagged it as "a
material risk, not a detail". Measured jointly over nine cues, that is too
pessimistic:

- The feasible region is **2,249 grid points**, not a seven-point line.
- The most robust configuration is **θ_high = 0.495, θ_low = 0.285**, which sits
  **0.030 away from the nearest infeasible point in every direction** — six grid
  steps of slack on both axes simultaneously.
- That configuration classifies all nine fixtures correctly: A01–A03 rational,
  A04–A07 irrational, B01/B02 abstain.

The reason the earlier estimate was tight is that it used only `المرشحة`
(r = 0.747) as the rational exemplar. `مهندس` sits at r = 0.8954, and the three
irrational cues sit at i ≥ 0.9039 — two at exactly 1.0000. The classes are much
better separated than one example on each side suggested.

**This does not retire the Phase 4 gate.** The gold set will contain hundreds of
cues spanning cases far less clean than seven hand-picked fixtures, and the gate
can still fail there. It does mean the design is not balanced on a knife edge.

## 4. Caveats that bound this result

1. **B01 and B02 are `REVIEW`.** Their `ABSTAIN` expectation is an open question
   (register D7 — the role test may resolve `حاصلة` via the preceding `مهندسة`).
   They are reported here as a hypothetical, not as binding. If D7 resolves them
   to `applicant`, the constraint inverts and this region changes.
2. **Seven settled fixtures is a small, deliberately clean sample.** They were
   authored to be canonical, so they overstate separability relative to corpus
   text.
3. **The role test is not applied.** Groups 1–2 are swept on rationality alone;
   with AB6 in play a rational cue can still abstain.
4. **`مطلوبة` (§7.1) and `المتقدم` (§7.2) are excluded** — they are groups 6 and
   are known systematic error classes.

## 5. Method discrepancy to resolve — spec §4.2 wording

Spec §4.2 says mass is computed "using the analyses' **log-probabilities**".
Measured both ways on `حاصلة` in `مطلوبة مهندسة برمجيات حاصلة على بكالوريوس هندسة`:

| Method | mass(i) | mass(r) | Reproduces ADR 001? |
|---|---|---|---|
| Σ candidate `score`, normalised | 0.6757 | 0.3243 | **yes** (ADR: 0.676 / 0.324) |
| Σ `exp(pos_lex_logprob)`, normalised | 0.7632 | 0.2368 | no |

The implementation uses `score`, because that is what reproduces the calibration
evidence. **The two are not interchangeable** — θ is calibrated against these
numbers and then frozen into the pre-registration, so the method is part of the
frozen definition.

**Author action:** amend spec §4.2 to say "candidate scores" rather than
"log-probabilities", or state that the log-probability method is intended and
re-derive ADR 001's evidence under it. Recorded in `docs/AUTHOR-ACTIONS.md`.

## 6. Reproducing this

```bash
uv sync --extra dev
camel_data -i morphology-db-msa-r13
camel_data -i disambig-bert-unfactored-msa
uv run pytest tests/test_thresholds.py tests/test_tagger.py -v
```

`tests/test_tagger.py::test_adr_001_masses_reproduce` is the regression test on
the calibration evidence: if those masses drift, the pre-registered θ no longer
means what ADR 001 says it means.
