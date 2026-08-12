# Finding 001 — AB4 is a gender-asymmetric abstain trigger

- **Register ID:** D14 (new, **P0** — blocks Phase 6 and contaminates Phase 7)
- **Found:** 12 August 2026, by the Phase 3 twin-symmetry harness
- **Status:** open — needs an author decision
- **Evidence:** `tests/test_tagger.py::test_t01_twin_symmetry_end_to_end`
  (`xfail(strict=True)`)

---

## What was found

Running fixture T01's twin pair end-to-end through
`BERTUnfactoredDisambiguator.pretrained('msa', top=100)`:

> حاصلة على بكالوريوس هندسة من جامعة القاهرة
> حاصل على بكالوريوس هندسة من جامعة القاهرة

Both twins abstain — but **for different reasons**:

| Twin | Trigger | Why |
|---|---|---|
| `حاصلة` (f) | **AB4** — candidates disagree on `gen` | 34 candidates: 21 `gen=f`, **12 `gen=m`** |
| `حاصل` (m) | **AB1** — rationality does not resolve | 19 candidates: 18 `gen=m`, **0 `gen=f`** |

The feminine surface form admits masculine analyses. The masculine form admits no
feminine ones.

## Why it matters

**The labels match; the strata do not.** Spec §8.3 stratifies adjudication *by
abstain trigger*, and architecture §8.1 requires tier-wise metrics broken down the
same way. Twins that abstain under different triggers are sampled at different
rates, adjudicated in different strata, and reported in different rows.

Fixture B02's note states the stake directly:

> "if the tagger abstains on the feminine form but resolves the masculine, the
> instrument is itself gender-asymmetric, which would be fatal to the paper."

This is the same failure one step in: both abstain, but the *route* differs
systematically by gender. Any downstream measurement inherits that asymmetry, and
nothing in the analysis layer can separate instrument asymmetry from ranker bias —
which is precisely the confound the whole twin design exists to avoid.

## It is structural, not a bug

Architecture §4.2 already records the underlying fact:

> "feminine surface forms frequently return both masculine and feminine analyses
> out of context. Out-of-context analysis is therefore insufficient."

What was **not** drawn from it is the consequence for AB4. The trigger is defined
in spec §6 as "candidate analyses disagree on `gen` after disambiguation" — and
because feminine forms carry more gender-ambiguous analyses than masculine ones,
that condition is met more often for feminine cues **as a property of the
morphology database**, independently of the text.

No threshold choice removes it. Computing AB4 on gender *mass* rather than raw
candidate membership narrows it but does not close it:

| Token | mass(f) | mass(m) |
|---|---|---|
| `حاصلة` | 0.673 | 0.300 |
| `حاصل` | 0.000 | 0.955 |

`حاصل` resolves cleanly under any sane threshold; `حاصلة` does not.

## Options — author decision required

1. **Compute AB4 on gender mass with its own calibrated threshold.** Consistent
   with ADR 001's treatment of AB1, and arguably the correct reading of "after
   disambiguation" — raw candidate membership is the same over-permissive rule
   ADR 001 rejected for rationality. Reduces the asymmetry; does not remove it.
   Adds a third pre-registered constant.
2. **Drop AB4, or restrict it to cases where the *disambiguated* gender is
   genuinely in doubt.** Simplest, and defensible if AB5 (form/functional
   divergence) already catches the cases that matter. Loses a trigger the design
   currently declares.
3. **Keep AB4 and measure the asymmetry as a reported quantity.** Honest, and in
   keeping with how §7.1/§7.2 error classes are handled — but it means every
   trigger-stratified table carries a known gender confound that must be stated.
4. **Symmetrise at the trigger level:** if either twin fires AB4, both abstain
   under AB4. Only available where twins are paired by construction (Phases 8+),
   not in the Phase 7 corpus sweep where cues arrive unpaired.

**Recommendation, but yours to make: (1) plus (3)** — bring AB4 into line with
AB1's mass treatment, then measure and report the residual asymmetry rather than
claiming it is gone. That keeps the trigger, matches the spec's "after
disambiguation" wording, and puts a number on a limitation a reviewer would
otherwise find.

## Why this is worth reporting in the paper

The instrument caught a gender asymmetry **in itself**, before any measurement was
taken, because twin symmetry was built as a gate rather than assumed. That is a
concrete demonstration of the design principle the paper argues for. A version of
this project without the Phase 3 harness would have shipped the asymmetry into
C1's abstention tables and reported it as a property of Arabic recruitment text.

## Reproducing

```bash
uv run pytest tests/test_tagger.py::test_t01_twin_symmetry_end_to_end -rx
```

The test is `xfail(strict=True)`: it reports a **failure** the moment D14 is
resolved and the twins become symmetric, so the finding cannot be silently
forgotten.
