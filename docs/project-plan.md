# ArabGN-CF — Whole-project implementation plan

**Date:** 12 August 2026 · **Target:** NILES 2026 SS2, submission 18–19 August
**Build order:** `docs/decision_register.md` Part 1 (supersedes the original
kickoff phase plan)
**Phase 0 + Phase 1 detail:** `docs/build-plan.md`
**Decisions:** `docs/decisions/` (closed) · `docs/decision_register.md` (open)

---

## 1. The critical path, and what actually gates it

The project has eleven phases. Only some of them are engineering.

```
Phase 1 ──► 2B ──► 3 ──────────────► 5 ──► 6 ──► 7 ──► 8 ──► 9 ──► 10 ──► 11
             ▲                        ▲                              ▲
             │                        │                              │
        Phase 2A ──► Phase 4 ─────────┘                    external time anchor
      (human annotation)  (κ ≥ 0.7 + θ calibration)
```

**The binding constraint is Phase 4, and it is human, not technical.** ADR 001
made the gold set *upstream* of finishing the tagger: θ cannot be calibrated
without it, and Tier A/B classification cannot be completed without θ. Architecture
§9 says this outright — adjudication "cannot be compressed at the end."

Everything else can be built today. Phase 4 cannot.

### What blocks on a person, not a keyboard

| Blocker | Blocks | Who |
|---|---|---|
| Gold set annotated to κ ≥ 0.7 | Phase 4, 2B completion, 7 | Multiple annotators, ~days |
| θ_high / θ_low calibration + separability check | Phase 2B, 7 | Follows the gold set |
| D6 enclitic pronouns | Phase 2B scope | Author |
| D7 role test + closed list | Phase 5 | Author — annotation work |
| D8 pro-drop default | Phase 5, fixtures C05–C07 | Author |
| D9 institution-name list | Phase 7 accuracy | Author |
| Ten `REVIEW` fixtures | Binding coverage across 2B/3/5 | Author |
| ArabJobs redistribution permission | Phase 7 *release* (not analysis) | External, outstanding |
| External time anchor (OSF/AsPredicted/OpenTimestamps) | Phase 9, C4 | External, ~1 h |
| Audit-subject model downloads + GPU | Phase 10 pilot | Compute |

---

## 2. Phase-by-phase

### Phase 1 — Skeleton, contracts, normalisation `[arch §9 Step 1]`

Detail in `docs/build-plan.md` Part C. Packaging under `uv`, `DocRecord` /
`TaggedCue` / enums, NFC-only normalisation under `arabgn/analysis/`, fixture
loader, normalisation and contract tests.

**Gate:** review. **Blocked by:** nothing. **Buildable today.**

### Phase 2A — Adjudication tooling `[arch §9 Step 3]`

Runs continuously from day one, not as a gated phase — it is the only component
with human lead time.

Per spec §8: annotators see sentence, highlighted cue, document type, and
**nothing else** — not the prediction, tier, or abstain status. `unclear` is
recorded, never coerced. Append-only store, stable annotator ID, timestamp.
Stratified sampling per §8.3 (country, seniority, POS class, tier, abstain
trigger; over-sample the §7.1 `مطلوبة` and §7.2 `المتقدم` error classes).
Cohen's κ over the double-annotated subset. Third-annotator adjudication per §8.4.

Two things this must also carry, added by ADR 001 and ADR 002:

- the **joint θ separability check** (sweep θ_high and θ_low together — see below)
- `morph_class` recorded per cue so the §8.1 cross-tabulation is possible

**Gate:** none (continuous). **Blocked by:** nothing to *build*. **Buildable
today** — the tool, not the gold set.

### Phase 2B — Tier A/B cue extractor `[arch §9 Step 2]`

`BERTUnfactoredDisambiguator.pretrained('msa', top=100)` — `top=100` is
load-bearing; with top-1 the Tier B abstain can never fire. POS filtering per
spec §3.1 (N01/N02 guard it). Rationality resolution per the calibrated mass rule
(ADR 001). Tier A/B classification per spec §5, tier label on every cue and never
re-inferred. Determinism asserted (register D13: verified byte-identical across
three runs including model reload).

Tier C cues raise `NotImplementedError` with cue and POS.

**Runs the θ sweep** rather than stalling on unset thresholds: each group-1/2/3
fixture is evaluated across the (θ_high, θ_low) grid and the passing region is
reported per fixture. That output *is* the calibration evidence §4.2 requires.

**Gate:** review. **Blocked by:** D6 (scope); *completion* blocked by Phase 4 θ.
**Mostly buildable today** — everything except the frozen θ.

> Note: an earlier concern that `حاصلة` would tag as `adj` and route to Tier C,
> colliding with fixtures B01/B02, was **wrong on the facts**. Register D2's
> verified table shows `حاصلة` is POS `noun` → Tier B, matching the fixtures.

### Phase 3 — Twin symmetry, Tiers A/B — **provisional**

Structural identity across a twin pair: same cue count, tiers, labels, abstain
triggers; only `gen` differs. Reusable as a property check over arbitrary pairs,
not just T01/T02.

Explicitly a **smoke test**. It tests symmetry-in-abstention, not
symmetry-in-classification, because the cues carrying the paper's phenomenon are
Tier C and absent here. T02 is `REVIEW` and skips. Do **not** assert token-count
equality — architecture §5.2 states that is unsatisfiable and forcing it produces
silent padding, itself a confound.

**Gate:** review. **Blocked by:** nothing. **Buildable today.**

### Phase 4 — Gold set κ ≥ 0.7 + θ calibration — **HARD BLOCK**

Two gates, either of which can fail:

1. **κ ≥ 0.7.** Below it the gold set is unusable and every downstream
   precision/recall figure is uninterpretable. Referent classification is a
   genuinely hard annotation task; this is a real possibility.
2. **θ separability.** Sweep θ_high and θ_low **jointly** — ADR 001 shows the
   feasible region is a disjunction with two independent routes
   (`θ_high ∈ (0.676, 0.747]` **or** `θ_low ∈ (0.254, 0.324]`), each ~7 points
   wide. A θ_high-only sweep can report "no θ exists" while a valid θ_low region
   sits unexamined. If clean and ambiguous cases genuinely overlap in mass, **AB1
   needs redesigning, not tuning.**

**Gate:** hard block. **Blocked by:** human annotation. **Not achievable today.**

### Phase 5 — Tier C dependency layer `[arch §9 Step 4]`

Agreement-target identification (subject for verbs, modified head for
adjectives), rationality inherited from the target, abstain on AB2/AB3. Highest
technical risk in C1, and it carries the paper's core phenomenon — `تخرجت`,
`عملت`, `حاصلة`, `مسؤولة`.

**Gate:** review. **Blocked by:** D7 (role test), D8 (pro-drop), and D9 for E03.
**Scaffolding buildable today; the rules are not.**

### Phase 6 — Twin symmetry across all tiers — **HARD BLOCK**

The binding form of the invariant. If the instrument classifies feminine and
masculine text asymmetrically, every downstream measurement is confounded by the
instrument itself. Nothing proceeds past a failure here.

**Gate:** hard block. **Blocked by:** Phase 5.

### Phase 7 — Full ArabJobs sweep → C1 tables `[arch §9 Step 5]` — **DELIVERABLE**

Prevalence metrics per architecture §8.5, by country, seniority, occupation; mean
cues per ad and per 100 tokens; distribution over POS class and tier; **tier ×
morph_class cross-tabulation** (ADR 002); abstentions reported separately and
never silently dropped or silently counted (prohibition 3).

The highest-value deliverable in the sequence. Architecture §9: C1 is the only
contribution that is a genuine empirical finding independent of the twin
machinery — if the project stalls anywhere, C1 still stands alone.

**Blocked by:** Phases 4–6, D9. Redistribution permission affects *release*, not
analysis.

### Phase 8 — Generator and register invariants `[arch §9 Step 6]`

Five-register typology R1–R5 with machine-checked invariants; R3 (agreement-free)
is certified **by the Layer 2 tagger**, which is why the tagger comes first. Twin
CV pairs under architecture §5.2's revised matching invariants — identical
content-word count, identical qualification slots, character-length within
declared tolerance, tokenization delta **measured and reported, not forced to
zero**.

Generation method is register D-item / architecture §10 decision 2, still open
(template / LLM / hybrid). Any LLM used is version-pinned and enters the freeze.

### Phase 9 — Blinding, freeze, external time anchor `[arch §9 Step 7]`

HMAC cell blinding, key held outside the repo, unblinding logged and one-way.
Tests confirming no cell identity leaks through file ordering, filename, or record
ordering — architecture §6.1 names ordering as the most common failure mode.

Freeze hash over the **explicit manifest** (ADR 007), not a directory glob.

**External time anchor is required, not optional.** A hash you compute and print
in your own paper proves the config did not drift; it does not prove the analysis
predates unblinding, because you control both artifact and clock. ~1 hour of work.
Without it C4's central claim is not independently verifiable.

### Phase 10 — Analysis, pilot, power curves → C3 `[arch §9 Step 8]`

Two-way cluster-robust variance over ads and twins; Holm correction with the
family declared explicitly; TOST for equivalence margins; power curves over A and
C. 40 ads × 50 twins pilot → variance components.

Guarded reporting layer (architecture §7.4): refuses the phrase "no bias"
(prohibition 4), names clustering structure on every interval, blocks equivalence
claims below achieved margin, labels underpowered cells **inconclusive, not null**.

**Open issue that must close first:** architecture §7.3 — is σ²_cv a CV-level
random effect or twin-discordance variance? In a paired design the pair-level
effect cancels in the difference. A statistics reviewer will query the notation.
One sentence, but it blocks the freeze.

### Phase 11 — Pre-registration → C4 `[arch §9 Step 9]`

Cells, margins and their derivation, the Holm family, positive control, zero-cue
calibration cell, the pre-committed lexical-deflation test, the decision rule.
Depends on C3's numbers. Timestamped before unblinding.

---

## 3. What I can finish today

**Buildable now, in order:** Phase 0 closure (ADRs, doc amendments, fixture
`group:` key, proposal corrections) → `morph_class` feasibility probe → Phase 1
complete → Phase 2A tooling → Phase 2B up to the θ boundary → Phase 3.

**Not buildable today, and why:** Phase 4 needs humans annotating over days.
Phases 5–7 need D7/D8/D9 from you plus Phase 4's output. Phases 8–11 sit behind
those, plus an external service and a GPU pilot.

**Highest-leverage thing you can do in parallel:** settle D6, D7, D8, D9 and the
ten `REVIEW` fixtures, and start annotators on Phase 2A the moment it exists.
Every one of those is on the critical path and none of them is code.

---

## 4. Ahead of all of it

The SS2 proposal claims Phase 0 complete and tested, 117 automated tests, ~7,900
lines, and an implemented tagger. None of that exists. It is **not yet
submitted** — see `docs/proposal-corrections.md`. C4's entire argument is that a
reviewer can check the artifact, so these claims are checkable and currently
false. Correcting them outranks everything above.
