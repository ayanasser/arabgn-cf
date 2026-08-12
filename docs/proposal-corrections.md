# SS2 proposal — required corrections before submission

**Source:** `docs/NILE2026 - SS2 Proposal .pdf`, dated 3 August 2026
**Status:** not yet submitted (author confirmed, 12 August 2026)
**Verified against:** repository at commit `18a875c`, 12 August 2026

---

## Why this matters more than the code

C4's argument is that a reviewer can check the artifact. The proposal makes
specific, countable claims about that artifact — line counts, test counts,
completion status. Those are the most checkable claims in the document, and they
are the ones a sceptical reviewer would verify first.

They are currently false. Not aspirational, not rounded — the repository contains
no Python code at all.

Since the proposal is not yet submitted, this is an edit, not a correction to the
session chairs. It costs nothing now and would be very expensive after review.

---

## 1. Artifact claims — §1.2, contribution C2

> "Approximately **7,900 lines**, **117 automated tests**, executable end-to-end on
> a laptop with no model downloads via a deterministic synthetic scoring backend,
> so a reviewer can re-run every estimator against known ground truth."

**Repository position, 12 August 2026:**

| Claim | Actual |
|---|---|
| ~7,900 lines | 0 lines of Python |
| 117 automated tests | 0 tests |
| Deterministic synthetic scoring backend | Not started (Phase 10) |
| Executable end-to-end on a laptop | Not executable |

Every component listed in the same sentence is also unbuilt: five-register ad
typology, twin CV generator, SD-matched competitor pools, HMAC blinding,
cryptographic freeze, guarded reporting layer.

**Suggested rewrite** — describe the design and its status honestly, and let the
frozen artifact carry the numbers when it exists:

> ArabGN-CF is specified as an open, pre-registered audit instrument: a
> five-register ad typology with machine-checked register invariants; a
> gender-controlled twin CV generator; SD-matched competitor pools; HMAC-based
> blinding of cell identity; a cryptographic freeze over config and analysis
> source, after which confirmatory analysis refuses to run on drift; and a
> reporting layer that refuses to emit the phrase "no bias". The instrument is
> designed to run end-to-end on a laptop through a deterministic synthetic scoring
> backend, so that a reviewer can re-run every estimator against known ground
> truth. Implementation is in progress; the released version will be frozen and
> its hash printed here.

If the paper needs a number at submission, quote the number that is true on
submission day, not a projection.

## 2. Completion claim — §1.7

> "**Phase 0 of the instrument is complete and tested.**"

Not the case. Phase 0 as now defined (doc reconciliation and decision closure)
completed 12 August 2026; Phase 1 (skeleton, contracts, normalisation) is in
progress. See `docs/project-plan.md`.

**Suggested rewrite:** "Design specification and linguistic specification are
complete; the decision register is closed on both P0 items. Implementation is
underway."

## 3. Feasibility table — §1.7

| Dates | Work | Stated status | Actual |
|---|---|---|---|
| 3–5 Aug | Confirm SS2 format; ArabJobs redistribution query | Not started | Redistribution query still outstanding — carried into `docs/architecture.md` §10 decision 1 |
| 4–7 Aug | Phase 1 pilot (40 ads × 50 twins, e5-large) → variance components | "Instrument ready, blocking" | **Instrument does not exist.** Generator (Phase 8), scoring and analysis (Phase 10) all unbuilt |
| 6–10 Aug | Tagger sweep over ArabJobs; adjudicate abstention sample → C1 tables | "Tagger implemented" | **Tagger not implemented.** Phase 2B not started; blocked additionally on θ calibration, which is blocked on the gold set |
| 8–14 Aug | Draft | — | Blocked on C1 and C3 numbers |
| 15–17 Aug | `arabgn freeze`; hash into manuscript | — | Freeze layer unbuilt (Phase 9); external time anchor not chosen |

Two rows state the opposite of the repository state. Both need rewriting.

## 4. Timeline realism

The table has the tagger sweep at 6–10 August and submission at 18–19 August.
Today is 12 August. Between here and a defensible C1 table sit:

- Phase 1 → 2B (buildable now)
- **Phase 4: a human-annotated gold set at κ ≥ 0.7** — multiple annotators, days
  of lead time, and architecture §9 states it "cannot be compressed at the end"
- **θ calibration and the separability gate**, which can fail (ADR 001 §4.2.1)
- Phase 5 Tier C, blocked on register D7, D8 and D9 — all unresolved author
  decisions
- Phase 6 twin symmetry across all tiers, a hard block
- Phase 7 sweep

C1 by 18 August is not reachable on the current dependency chain. C3 needs the
generator and a scoring pass on top of that.

**Options, in order of cost:**

1. **Submit on C1's design plus the instrument specification**, with prevalence
   numbers deferred. The paper is already framed as measurement and feasibility,
   and §1.8 risk 1 anticipates the "protocol paper without findings" objection.
2. **Narrow C1's scope** to a hand-checkable subsample rather than the full
   ArabJobs sweep, so a real number exists with a stated denominator.
3. **Move the submission.**

Not an option: leave the artifact claims as they stand and hope no reviewer runs
`wc -l`.

## 5. Smaller items

- **§1.2 C2** — "a gender-controlled twin CV generator that **refuses to emit a
  pair differing in token count**." Architecture §5.2 has already superseded this:
  the constraint is "likely unsatisfiable" because `حاصل` and `حاصلة` differ under
  every subword tokenizer in the audit set, and forcing it produces silent
  padding, itself a confound. The proposal should carry §5.2's revised invariants
  — identical content-word count, identical qualification slots, tokenization
  delta **measured and reported rather than forced to zero**. As the architecture
  doc notes, this is a stronger position under review, not a weaker one.
- **§C3** — the SE formula uses σ²_cv, which architecture §7.3 flags as
  ambiguous between a CV-level random effect and twin-discordance variance. In a
  paired design the pair-level effect cancels in the difference. One sentence of
  definition, but it is `docs/architecture.md` §10 decision 4 and blocks the C4
  freeze. A statistics reviewer will query it.
- **§1.7** — "Phase 1 pilot" and "Phase 0" in the proposal use different phase
  numbering from `docs/project-plan.md`. Worth aligning so the paper and the
  repository refer to the same things.

---

## What is accurate and should stay

Most of the document. The positioning against prior art (§1.6), the SS2 fit
(§1.5), the scope boundaries (§1.3), what the paper deliberately does not report
(§1.4), and the risk analysis (§1.8) are all sound and unaffected. The C1/C3/C4
contributions are well-argued as *claims*; only the artifact-status sentences
supporting C2 are wrong.

The correction is narrow. It is just load-bearing.
