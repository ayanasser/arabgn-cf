# Linguistic Specification and Annotation Guidelines

**Scope:** Modern Standard Arabic recruitment text (job advertisements and CVs).
**Audience:** implementers of the Layer 2 tagger, and human annotators producing
the gold standard.
**Status:** v0.1 — sections marked ⚠ need author review before freeze.

This document is the single source of truth for what counts as a gender cue and
what "applicant-referring" means. Code and human annotation must agree with it;
where they disagree, this document is authoritative and the disagreement is a bug
or an annotation error, not a matter of judgement.

---

## 1. The phenomenon being measured

Arabic marks gender obligatorily through agreement on verbs, adjectives,
participles and pronouns — not only on nouns and names. A CV written by a woman
carries feminine agreement throughout:

| Masculine | Feminine | Gloss |
|---|---|---|
| حاصل على | حاصلة على | holder of |
| تخرج | تخرجت | graduated |
| عمل | عملت | worked |
| مسؤول عن | مسؤولة عن | responsible for |
| يتمتع بـ | تتمتع بـ | possesses |

Redacting the applicant's name removes one cue and leaves all the others. That is
the paper's thesis, and the tagger's job is to count the others.

---

## 2. Definitions

**Gender cue.** A token whose morphological analysis carries `gen ∈ {m, f}` and
whose POS is a content class (see §3.1). Function words are excluded.

**Applicant-referring.** A gender cue is applicant-referring when the entity whose
gender it marks is the job applicant — the person who would submit the CV or
respond to the advertisement.

This is a claim about *reference*, not about grammar. `خبرة واسعة` ("broad
experience") is grammatically feminine twice over, but the feminine marking belongs
to `خبرة`, which is a thing, not a person. Neither token is applicant-referring.

**Rationality (`rat`).** A lexical feature distinguishing human referents (`r`)
from non-human (`i`) from not-applicable (`n`, typically verbs and adjectives,
which inherit rationality from their agreement target). This is the established
feature from the Arabic agreement-modelling literature (Alkuhlani & Habash 2011),
exposed directly by CAMeL Tools.

Rationality is the primary evidence for applicant-reference, but it is **not
identical to it**. See §5.

---

## 3. Cue detection

### 3.1 Included POS classes

Include: `noun`, `noun_prop`, `adj`, `verb`, `adj_comp`, `noun_quant`.

Exclude: `prep`, `conj`, `part`, `pron` (see §3.2), `punc`, `digit`, `abbrev`,
and anything with `gen ∈ {na}`.

Rationale: function words return spurious gender and rationality candidates. `على`
returns `rat={n, na, r}`, which would flood the abstain queue with noise.

### 3.2 Pronouns ⚠

Attached pronouns (`لديه`, `لديها`, `خبرته`, `خبرتها`) are genuine gender cues and
frequently applicant-referring. They are currently excluded pending a decision on
whether the enclitic (`enc0`) is treated as a separate cue or as part of the host
token.

**Author decision required.** Recommended: treat the enclitic as a separate cue
with its own span, because `خبرتها` contains two gender markings referring to two
different entities — the experience (feminine, irrational) and its possessor
(feminine, potentially the applicant).

### 3.3 Multiple cues per token

A token may carry more than one gender marking. Each is a separate `TaggedCue`
with its own character span. Do not collapse them.

---

## 4. Using candidate analyses

The disambiguator returns ranked candidate analyses. Configuration is
`BERTUnfactoredDisambiguator.pretrained('msa', top=100)`.

### 4.1 Why not top-1

Top-1 is unreliable for rationality on this register. Verified example:

> مطلوبة مهندسة برمجيات **حاصلة** على بكالوريوس هندسة

`حاصلة` here refers to the sought engineer — a person — but the top analysis
returns `rat=i`. The correct reading is present in the candidate set
(`rat_cands = {i, r}`) but not ranked first.

Using top-1 would misclassify this cue *and* would prevent the Tier B abstain from
ever firing, because a single candidate can never disagree with itself.

### 4.2 Why not raw candidate-set membership either

Raw membership is too permissive. Verified:

| Token | `rat_cands` | Problem |
|---|---|---|
| معتمدة | `{i, n, r}` | Adjective; `r` is a spurious low-probability reading |
| شمس | `{i, n, r}` | Part of the proper noun `عين شمس` |
| برمجيات | `{i, n}` | Unambiguously a thing |

If any `r` in the candidate set triggers "possibly applicant-referring", nearly
every token qualifies and the abstain rate approaches 100%.

**SETTLED 12 August 2026 — ADR 001 (register D1).** Compute the probability mass
of each rationality value across candidates using the analyses' log-probabilities,
and apply:

- mass(`r`) ≥ θ_high and mass(`i`) < θ_low → rational
- mass(`i`) ≥ θ_high and mass(`r`) < θ_low → irrational
- otherwise → **abstain**

θ_high and θ_low are calibrated once against the gold set, then frozen. They must
be declared in the pre-registration.

Both threshold-free alternatives were tested and both fail on **settled**
fixtures, in opposite directions:

| Formulation | Failure |
|---|---|
| Raw candidate-set membership | Abstains on A01 `المرشحة` and A02 `مهندس` — the two cleanest positives |
| Rank-based (top-1 vs top-2) | Resolves B01 `حاصلة` to irrational — the exact error AB1 exists to catch |

Architecture §4.4's former claim that this trigger needs no calibration data has
been withdrawn as an authoring error.

#### 4.2.1 Calibrating θ — the separability gate

The feasible region is **two-dimensional and disjunctive**. Against the measured
masses (`خبرة` i=0.904; `المرشحة` r=0.747/i=0.254; `حاصلة` i=0.676/r=0.324):

```
θ_high ∈ (0.676, 0.747]     OR     θ_low ∈ (0.254, 0.324]
```

Two independent routes, each roughly seven points wide. **Sweep both parameters
jointly.** A θ_high-only sweep can conclude "no feasible θ exists" while a valid
θ_low region sits unexamined.

Before θ is committed to the pre-registration, confirm on the gold set that the
mass distributions of clean rational cases and genuinely ambiguous cases do not
overlap. If they do, no θ exists and **AB1 must be redesigned, not tuned.** This
gate can fail.

#### 4.2.2 Context does not disambiguate `حاصلة` — and now we know why

`حاصلة` returns mass(`r`) = 0.324 in ad context and 0.330 in CV context. Two very
different contexts move the minority reading by six thousandths.

Probing the morphology database (12 Aug 2026) shows the `rat` ambiguity **is a
lexical class ambiguity**, decomposing cleanly by the `stemcat` field:

| `stemcat` | analyses | `rat` | `lex` | gloss |
|---|---|---|---|---|
| `N/ap` | 22 | `i` | حاصِل | **income** + [fem.sg.] |
| `Nall` | 11 | `r` | حاصِل | **holder** + [fem.sg.] |

Both readings are grammatically licensed in both contexts, so there is nothing for
context to resolve. The instrument is not failing to decide — without world
knowledge there is genuinely nothing to decide.

**Abstention is therefore correct behaviour for this lexeme, not an instrument
shortcoming**, and the paper can say precisely what is being abstained on, with a
dictionary gloss, rather than reporting a bare abstention rate.

---

## 5. Referent classification — the three tiers

> **Tiers are mechanism-based, not linguistic — ADR 002 (register D2), 12 Aug
> 2026.** A tier names *how* reference is resolved: lexically (A), by abstaining
> on lexical ambiguity (B), or by syntactic inheritance (C). It is **not** a claim
> about the linguistic category of the cue, and must never be read as one in any
> output or table.
>
> Tier membership follows CAMeL POS, which splits active participles across tiers
> by lexeme rather than by property:
>
> | Token | Category | POS | Tier |
> |---|---|---|---|
> | حاصلة، حاصل، حاصلا، وحاصلة | active participle | `noun` | B |
> | المتقدم، المسؤولة، مسؤول، العاملة | active participle | `adj` | C |
> | خريجة، المرشحة | agentive noun | `noun` | A |
>
> Linguistic class is therefore recorded **separately**, in `TaggedCue.morph_class`,
> and §8.1 of the architecture is reported as a tier × morph-class
> cross-tabulation. This also means `rat_candidates` differs by path — `المسؤولة`
> → `{i,n,r}` via `adj`, `المرشحة` → `{i,r}` via `noun` — so the extra `n` mass
> must be accounted for when applying §4.2 across tiers.

### Tier A — lexical resolution

**Applies when:** cue POS is `noun` or `noun_prop`, and rationality resolves
unambiguously under §4.2.

**Decision:**
- rational → applicant-referring **if** it also passes the role test (§5.1)
- irrational → not applicant-referring

**Examples:**

| Token | Context | `rat` | Label |
|---|---|---|---|
| المهندسة | المهندسة المسؤولة عن المشروع | `r` | applicant-referring |
| خبرة | خبرة واسعة في التطوير | `i` | not applicant-referring |
| الشركة | الشركة تبحث عن موظفين | `i` | not applicant-referring |
| سنوات | خمس سنوات | `i` | not applicant-referring |

### 5.1 The role test ⚠

Rational ≠ applicant. A job ad may refer to other people: the hiring manager, the
team, the company's clients, a reporting line.

> يعمل تحت إشراف **المدير** التنفيذي
> ("works under the supervision of the executive **director**")

`المدير` is rational, but it is not the applicant.

**Author decision required.** Recommended rule: a rational cue is
applicant-referring when it occupies one of these roles:

1. The subject of an applicant-describing predicate (`مطلوب`, `يشترط`, `نبحث عن`)
2. The head of the ad's main requirement noun phrase
3. A first-person self-reference in a CV context
4. The antecedent resolved from an applicant-referring verb (§Tier C)

And is *not* applicant-referring when governed by a supervision, employer, or
client relation. This needs a closed list, which is annotation work.

### Tier B — lexical ambiguity → abstain

**Applies when:** cue POS is nominal and rationality does not resolve under §4.2.

**Decision:** abstain. Route to human adjudication.

**Canonical example:** `حاصلة` — `rat_cands = {i, r}` with neither dominant. The
word means "obtainer/holder" and genuinely can describe a person or a result.

This tier is the design's honesty mechanism. A high Tier B abstention rate is an
acceptable outcome and should be reported, not engineered away.

### Tier C — syntactic resolution

**Applies when:** cue POS is `verb` or `adj`, i.e. `rat = n`.

These carry gender by *agreement*, not lexically, so their rationality must be
inherited from the agreement target.

**Procedure:**

1. Identify the agreement target — subject for a verb, modified head noun for an
   adjective.
2. Resolve that target's rationality by Tier A rules.
3. Inherit: the cue is applicant-referring iff its target is.
4. If the target cannot be identified, or resolves to Tier B, **abstain**.

**Examples:**

| Cue | Target | Target `rat` | Label |
|---|---|---|---|
| تخرجت (in تخرجت من جامعة القاهرة) | implicit subject = applicant | `r` | applicant-referring |
| واسعة (in خبرة واسعة) | خبرة | `i` | not applicant-referring |
| كبيرة (in شركة كبيرة) | شركة | `i` | not applicant-referring |
| المثالية (in المرشحة المثالية) | المرشحة | `r` | applicant-referring |

**Tier C carries the highest-value cues.** `تخرجت`, `عملت`, `حاصلة`, `مسؤولة` are
exactly the markings that survive name redaction. A tagger that handles only Tiers
A and B misses the paper's central phenomenon.

### 5.2 Pro-drop ⚠

Arabic is pro-drop: `تخرجت من جامعة القاهرة` has no overt subject. The subject is
the applicant, recoverable only from discourse context (it is a CV).

**Author decision required.** Recommended: in CV context, a finite verb with no
overt subject defaults to applicant-referring. In ad context, it does not — the
subject may be the company (`الشركة تبحث`). This makes the label
context-dependent, so `AdRecord` must carry a document-type flag.

---

## 6. Abstain triggers — complete list

| ID | Trigger | Tier |
|---|---|---|
| AB1 | Rationality does not resolve under §4.2 | B |
| AB2 | Agreement target not identifiable | C |
| AB3 | Agreement target itself abstains | C |
| AB4 | Candidate analyses disagree on `gen` after disambiguation | any |
| AB5 | `gen` ≠ `form_gen` (functional/form divergence) | any |
| AB6 | Rational cue whose role test is indeterminate (§5.1) | A |

Every abstained cue records its trigger ID. Adjudication is stratified by trigger.

---

## 7. Known systematic error classes

Report these; do not special-case them in code.

### 7.1 `مطلوب` / `مطلوبة`

Returns `rat=i` on all readings. In recruitment register it frequently refers to
the sought person (`مطلوبة مهندسة`). The morphology database encodes general MSA,
not recruitment usage.

Expected effect: under-counting of applicant-referring cues in ad headers.
Over-sample in adjudication.

### 7.2 `المتقدم` ("the applicant")

Analysed as `pos=adj`, `rat=n`, so it routes to Tier C and needs a target that
does not exist — it *is* the target. Expected to abstain under AB2.

Expected effect: the single most explicitly applicant-referring word in Arabic
recruitment text may be systematically abstained.

### 7.3 Proper-noun fragments

`شمس` in `جامعة عين شمس` analyses as `rat=r`. Multi-token proper nouns are not
recognised as units.

Expected effect: false applicant-referring cues inside institution names. Mitigate
with a frozen list of institution names, applied as a pre-pass, declared in config.

### 7.4 Broken plurals

`gen` and `form_gen` diverge (e.g. `طلبة` is form-feminine, functionally masculine
plural). AB5 catches these.

---

## 8. Annotation protocol

For the human gold standard.

### 8.1 Task

For each presented cue, in its full sentence context, label:

- `applicant` — the marking refers to the job applicant
- `non_applicant` — it refers to anything else
- `unclear` — genuinely indeterminate from the context shown

`unclear` is a valid answer. Annotators are not asked to guess, and the rate of
`unclear` is itself reported.

### 8.2 What annotators see

The full sentence, the cue highlighted, and the document type (ad or CV). They do
**not** see the tagger's prediction, its tier, or its abstain status. Blind
annotation is required or precision estimates are contaminated.

### 8.3 Sampling

Stratified by: country, seniority, POS class, tier, abstain trigger. Over-sample
§7.1 and §7.2 error classes. A subset is double-annotated for Cohen's κ; target
κ ≥ 0.7 before the gold set is usable.

### 8.4 Adjudication

Disagreements go to a third annotator. Persistent disagreement after adjudication
is recorded as `unclear` and reported, not forced to a label.

---

## 9. Open items requiring author decision

| § | Item | Register | Status |
|---|---|---|---|
| 4.2 | The probability-mass rule | D1 | **Settled** 12 Aug 2026 — ADR 001 |
| 5 | Tier membership vs linguistic class | D2 | **Settled** 12 Aug 2026 — ADR 002 |
| 3.2 | Enclitic pronouns as separate cues | D6 | Open — blocks Phase 2B scope |
| 5.1 | The role test and its closed list of non-applicant relations | D7 | Open — blocks Phase 5 |
| 5.2 | Pro-drop default by document type | D8 | Open — blocks Phase 5, fixtures C05–C07 |
| 7.3 | Institution-name list source | D9 | Open — blocks Phase 7 accuracy |
| 4.2 | θ_high / θ_low **values** | D1 | Open — calibrated at Phase 4, not choosable now |

None of the open items can be settled by an implementer. All must be resolved and
frozen before confirmatory analysis.

Note that ADR 001 settles the *rule*; the θ **values** remain open by design and
are calibrated once against the gold set at the Phase 4 gate. See §4.2.1 — that
gate can fail.

The full decision register, including items outside this document's scope, is
`docs/decision_register.md`.