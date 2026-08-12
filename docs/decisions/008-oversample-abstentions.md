# ADR 008 — Abstentions are over-sampled ×3 for adjudication

- **Register ID:** D18 (P1)
- **Status:** Accepted
- **Date:** 13 August 2026
- **Affects:** `arabgn/analysis/sampling.py` (frozen) · Phase 4 gold set ·
  architecture §8.1 · the pre-registration

---

## Context

Architecture §8.1's sampling plan reads:

> **Sampling plan.** Stratify by country, seniority, POS class, and tier.
> Over-sample abstentions and the مطلوبة error class. Double-annotate a subset
> for κ.

`arabgn/analysis/sampling.py` implemented the second half and not the first.
`DEFAULT_OVERSAMPLE` keys on surface token, so `مطلوبة` and `المتقدم` were
weighted ×3 while abstentions were drawn at their base rate.

Measured consequence, on a 200-cue draw over the full corpus (13 Aug 2026,
provisional θ, Tiers A/B):

| | drawn | of 200 |
|---|---|---|
| `non_applicant` — tagger resolved it | 123 | 62% |
| `ABSTAIN` — tagger could not | 77 | 38% |

Nearly two-thirds of the scarcest resource in the project — annotator hours —
went to cues the tagger had already answered, and the resolved stratum is
dominated by easy cases (`البرامج`, `سنوات`) that no annotator finds difficult.

Abstentions are where human labels buy the most:

- **θ calibration** happens against the AB1 boundary cases (ADR 001). Cues the
  tagger resolved confidently carry no information about where θ should sit.
- **D14** — AB4's gender asymmetry — is only measurable on abstained cues, and
  AB4 is 54% of all abstentions corpus-wide (63,743 of 118,022).

Resolved cues are still needed: false negatives, and therefore recall, can only
be found by annotating cues the tagger called `non_applicant`. The question was
the ratio, not whether to include them.

## Decision

**Over-sample abstained cues by ×3, matching the weight already applied to the
known error classes.**

Implemented as `DEFAULT_ABSTAIN_OVERSAMPLE = 3.0` in `sampling.py`, with the
multiplier exposed as a parameter and recorded on every `SamplingPlan`.

Abstention joins the stratum **key**, not a weight applied to strata that merely
contain an abstention — the same construction the error classes already use, and
for the same reason. Weighting a mixed stratum would enlarge its quota without
making the draw inside it prefer the cues the quota was enlarged for.

The two multipliers compose: an abstained `مطلوبة` is both a known error class
and an unresolved cue.

## Why ×3 rather than a fresh number

The pre-registration declares one weight and one reason instead of two unrelated
constants. "The same weight the design already applies to known error classes" is
a materially easier sentence to defend than a value chosen specifically for this
draw, and it removes a degree of freedom a reviewer would otherwise ask about.

## Consequences

**The sample is deliberately not representative of the corpus.** This is the
point, and it carries an obligation: any prevalence statistic computed from
annotated cues must be re-weighted back to corpus proportions.
`SamplingPlan.per_stratum` records the draw per stratum and
`SamplingPlan.abstain_oversample` records the weight, so the correction is
recoverable — but it has to actually be performed, and stated in the paper.

Architecture §8.5's prevalence figures come from the **full sweep**, not from the
adjudicated sample, so they are unaffected. What needs re-weighting is anything
that generalises an annotated rate to the corpus.

**This is a frozen, pre-registered parameter.** It enters the freeze through
`sampling.py`'s source and changes which cues are adjudicated, and therefore every
figure in §8.1.

`1.0` restores proportional sampling, so the choice stays visible as a choice.
`0` is refused — prohibition 3 forbids dropping abstentions from a metric, and a
zero weight would drop them from the sample that produces it.

## Alternatives rejected

**Leave it proportional.** Contradicts architecture §8.1 as written, and spends
roughly 60% of a scarce budget on the easy stratum.

**Weight by trigger, e.g. AB4 higher than AB1.** More precisely targeted at D14,
but it multiplies the pre-registered parameters from one to four and pre-judges
which trigger matters most before any of them has been measured against human
labels.

**Sample abstentions only.** Loses recall entirely — false negatives live in the
resolved stratum by definition.

## Verified by

`tests/test_adjudication.py`:

- `test_abstentions_are_oversampled` — drawn rate exceeds base rate
- `test_proportional_sampling_is_still_reachable` — `1.0` restores the base rate
- `test_the_abstention_multiplier_is_recorded_on_the_plan` — a draw that does not
  carry its own weight cannot be corrected afterwards
- `test_a_zero_multiplier_is_refused`
