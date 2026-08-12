# ADR 001 — AB1 uses calibrated probability mass, not a threshold-free rule

- **Register ID:** D1 (P0)
- **Status:** Accepted
- **Date:** 12 August 2026
- **Affects:** `docs/architecture.md` §4.4 · `docs/linguistic-spec.md` §4.2 ·
  Phase 2B · Phase 4 calibration gate
- **Supersedes:** the no-calibration claim in architecture §4.4

---

## Context

Two documents specified incompatible mechanisms for the same abstain trigger.

- **Architecture §4.4** described trigger 1 as "derived from the morphology
  database rather than a tuned threshold, which makes it defensible in the paper
  without calibration data."
- **Linguistic spec §4.2** made the same trigger depend on `θ_high` / `θ_low`,
  computed over candidate probability mass and calibrated against the gold set.

The threshold-free formulation is materially more attractive for the paper: no
free parameters to defend, no gold-set dependency, nothing to pre-register. It was
therefore tested rather than dismissed.

## Evidence

Three formulations were measured against the fixture set. Two failed, in opposite
directions, on **settled** fixtures.

### Threshold-free, raw candidate-set membership

Abstain whenever candidate analyses disagree on `rat`.

| Fixture | Token | `rat_cands` | Result |
|---|---|---|---|
| A01 | المرشحة | `{i, r}` | abstains ✗ |
| A02 | مهندس | `{i, r}` | abstains ✗ |

Fails on the two cleanest positive cases in the suite. Consistent with spec §4.2's
prediction that raw membership drives the abstain rate toward 100%. Unusable.

> Provenance note: the source measurement table labelled the `مهندس` row A04.
> A04's cue is `خبرة`; `مهندس` is A02. Author confirmed the row is **A02**. The
> correction strengthens the argument — the failure lands on A01 and A02, the two
> canonical positives.

### Threshold-free, rank-based

Abstain iff top-1 and top-2 disagree on `rat`.

| Fixture | Token | top-1 / top-2 | Result |
|---|---|---|---|
| A01 | المرشحة | r / r | resolves rational ✓ |
| A04 | خبرة | i / i | resolves irrational ✓ |
| B01 | حاصلة | i / i | resolves irrational ✗ |
| E03 | شمس | r / i | abstains ✓ |

Better, but it confidently resolves `حاصلة` to irrational — precisely the error
AB1 exists to catch, and precisely the case spec §4.1 documents as unresolvable at
top-1.

### Calibrated, probability mass

| Token | Mass |
|---|---|
| خبرة | i = 0.904 |
| المرشحة | r = 0.747, i = 0.254 |
| حاصلة (ad context) | i = 0.676, r = 0.324 |
| حاصلة (CV context) | i = 0.670, r = 0.330 |

This formulation admits a configuration that satisfies every settled fixture.

## Decision

**Adopt the calibrated probability-mass rule** of linguistic spec §4.2.

Architecture §4.4's threshold-free claim is an authoring error about trigger 1
(= AB1), confirmed by the author. It is **rewritten**, not reinterpreted. Leaving
both claims in the documents was the defect.

**No θ values are set by this ADR.** Calibration happens once, against the gold
set, at the Phase 4 gate, and the values are then frozen and pre-registered.

## Consequences

### The feasible region is two-dimensional, and the gate must sweep it jointly

Working the §4.2 rule against the masses above:

```
خبرة    → must resolve irrational :  θ_high ≤ 0.904 ,  θ_low > ~0.096
المرشحة  → must resolve rational   :  θ_high ≤ 0.747 ,  θ_low > 0.254
حاصلة   → must abstain            :  (θ_high > 0.676)  OR  (θ_low ≤ 0.324)
```

The abstain constraint is a **disjunction**, because abstention only requires the
irrational branch to fail. Two independent routes therefore exist:

- `θ_high ∈ (0.676, 0.747]`, or
- `θ_low ∈ (0.254, 0.324]`

Both windows span roughly seven points. **A separability check that sweeps only
θ_high can report "no feasible θ exists" while a valid θ_low region is
available.** The Phase 4 gate must sweep both parameters jointly.

### The separability check is a gate that can fail

Seven points of separation, estimated from one example on each side, is a material
risk rather than a detail. Before θ is committed to the pre-registration, run a
separability check over the gold set: if the mass distributions of clean rational
cases and genuinely ambiguous cases **overlap**, no θ exists and AB1 needs
redesigning rather than tuning.

This is a **hard block at Phase 4**, not a formality.

### `حاصلة` is stable across context — this is a finding, not a limitation

`حاصلة` returns r = 0.324 in ad context and r = 0.330 in CV context. Two very
different contexts move the minority reading by six thousandths. Context is not
disambiguating it.

That stability is positive evidence that **abstention is the correct behaviour**
for this lexeme, rather than an instrument shortcoming. Worth stating in the paper
rather than filing under limitations — it converts the abstain mechanism from an
admission into a result.

### Costs accepted

- Two frozen parameters must be justified in the pre-registration.
- The gold set becomes **upstream** of completing the Tier A/B extractor, not
  downstream. This is why `docs/decision_register.md` Part 1 runs adjudication
  (Phase 2A) continuously from day one rather than as a gated phase.
- The anticipated reviewer objection shifts from "your abstain rate is near 100%"
  to "where did θ come from?" — answerable by the pre-registration and the
  separability check.

## Related

[[002-tier-membership-and-morph-class]] — D2 interacts with this decision: tier
paths carry different candidate-set shapes (`المسؤولة` → `{i,n,r}` via `adj`
versus `المرشحة` → `{i,r}` via `noun`), so the `n` mass differs by path and the
rule must behave sanely across both.
