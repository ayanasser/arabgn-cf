# ArabGN-CF — System Architecture and Design Specification

| Field | Value |
|---|---|
| Project | Name Redaction Does Not Blind an Arabic Résumé Ranker |
| Target venue | NILES 2026, Special Session SS2 |
| Document status | Design specification, v0.1 |
| Last updated | 12 August 2026 |

> **Conversion note.** This file is a faithful Markdown conversion of
> `ArabGN-CF-architecture.pdf` (12 pp), produced 12 August 2026. Section
> numbering, table contents and wording are preserved verbatim. Three items could
> not be carried across mechanically and are marked inline: **Figure 1** (§2),
> **Figure 2** (§4.3), and the superscripts in the SE formula (§7.3). Arabic
> tokens were stored in the PDF in visual (reversed) order with U+06BE in place of
> U+0647; every token was rebuilt and verified character-for-character against
> `docs/linguistic-spec.md`. See §12 for the full conversion log.
> The PDF remains in the repository as the signed original.

---

## 1. Purpose and scope

### 1.1 What this system is

ArabGN-CF is a measurement instrument, not a bias-detection product. It exists to
make a specific class of claim checkable: that in Arabic, obligatory grammatical
gender agreement carries the applicant's gender through any name-redaction
safeguard, and that counterfactual hiring audits which claim "no bias" are usually
underpowered to license that claim.

The system produces four deliverables:

| ID | Deliverable | Type |
|---|---|---|
| C1 | Cue-level prevalence of applicant-referring gender marking in Arabic recruitment text | Empirical finding |
| C2 | ArabGN-CF — the open, frozen audit instrument | Software artifact |
| C3 | Variance components and power/feasibility result for twin-contrast audits | Empirical + analytical |
| C4 | Public pre-registration of the confirmatory study, timestamped before unblinding | Registered protocol |

### 1.2 What this system is explicitly not

- It is not an audit result. Confirmatory twin contrasts stay sealed.
- It is not an evaluation of any commercial hiring system.
- It does not produce population statistics about real applicants. Twins are
  synthetic by necessity — no two real applicants have identical qualifications.
- Nothing built here is itself an audit subject.

### 1.3 Scope boundaries

- **Language variety:** Modern Standard Arabic. Dialectal CVs out of scope.
- **Gender:** treated as binary, because Arabic agreement morphology is binary.
  The agreement-free register is the closest the design comes to a neutral form,
  and its adequacy is itself a measured quantity, not an assumption.
- **Audit subjects:** frozen, version-pinned, open-weight systems only. Measured,
  never trained.

---

## 2. System overview

Five layers. Data flows top to bottom; the freeze layer gates everything below it.

> **[FIGURE NOT EXTRACTED] Figure 1 — Five-layer system architecture.**
> Raster image on p. 3 of the PDF; no text layer. The five layers are recoverable
> from the section headings below: Layer 1 Data (§3), Layer 2 Tagger (§4), Layer 3
> Generator (§5), Layer 4 Blinding and freeze (§6), Layer 5 Scoring, analysis,
> reporting (§7). **Consult the PDF for the figure itself.**

Two scoring backends exist behind one interface:

- **Deterministic synthetic backend** — pure function, no model downloads, runs on
  a laptop. Lets a reviewer re-run every estimator against known ground truth.
  This is what the 117 tests exercise.
- **Real ranker backend** — the version-pinned open-weight audit subjects.

---

## 3. Layer 1 — Data

### 3.1 Inputs

| Input | Source | Licence | Status |
|---|---|---|---|
| ArabJobs corpus | arXiv:2509.22589 | CC-BY | Redistribution query outstanding |
| CV seed templates | To be assembled | To be determined | Not started |
| Occupation/seniority taxonomy | Derived from ArabJobs metadata | — | Not started |
| Run configuration | Authored in-repo | — | Not started |

### 3.2 Corpus loader — contract

Input: raw ArabJobs distribution. Output: a normalised record per advertisement.

```
AdRecord
  ad_id            str    stable hash of source text
  text_raw         str    unmodified source
  text_norm        str    Unicode-normalised, diacritics preserved
  country          enum   EG | JO | SA | AE
  occupation       str    from source metadata
  seniority        enum   entry | mid | senior | unspecified
  source_checksum  str
```

Normalisation rules (must be frozen and tested): Unicode NFC; alef/ya/ta-marbuta
normalisation is not applied — ta-marbuta is the primary feminine marker and
normalising it would destroy the signal being measured. This is the single most
important preprocessing decision in the system and needs an explicit test
asserting ta-marbuta survives.

---

## 4. Layer 2 — Tagger (C1)

### 4.1 Toolkit decision

CAMeL Tools 1.6 with `morphology-db-msa-r13`, verified 12 August 2026.

The database exposes three separate fields that the design depends on:

| Field | Meaning | Why it matters |
|---|---|---|
| `gen` | Functional gender | The semantically real gender |
| `form_gen` | Surface / form gender | Diverges on broken plurals |
| `rat` | Rationality (humanness): `r` / `i` / `n` | Distinguishes person-referring from thing-referring |

The `rat` field is what does the applicant-vs-job-property work the proposal
describes. This is not a heuristic we invented — it is an established feature in
the Arabic agreement-modelling literature (Alkuhlani & Habash) with published
annotation guidelines, which strengthens C1's defensibility.

### 4.2 Verified behaviour

Probed 12 August 2026 against the built-in MSA database:

| Token | `rat` values returned | Interpretation |
|---|---|---|
| المهندسة | `r` only | Unambiguously applicant-referring |
| خبرة / الشركة / سنوات | `i` only | Unambiguously not the applicant |
| حاصلة | `r` and `i` | Genuine ambiguity |
| واسعة (adjective) | `n` | Inherits rationality from head noun |
| تخرجت (verb) | `n` | Inherits rationality from subject |

Also observed: feminine surface forms frequently return both masculine and
feminine analyses out of context. Out-of-context analysis is therefore
insufficient — the disambiguator must run over full sentences.

### 4.3 Three-tier referent classifier

> **[FIGURE NOT EXTRACTED] Figure 2 — Referent classification and abstain
> routing.** Raster image on p. 5 of the PDF; no text layer. The routing logic it
> depicts is specified in prose in `docs/linguistic-spec.md` §5 (Tiers A/B/C) and
> §6 (abstain triggers AB1–AB6), which is the authoritative source for
> implementation. **Consult the PDF for the figure itself.**

Tier C is the core of C1, not a refinement. The highest-value applicant cues —
تخرجت, حاصلة, مطلوبة — are verbs and participles carrying `rat = n`. A tagger
with only Tiers A and B will miss most of what the paper is about.

### 4.4 Abstain policy

Abstain fires on any of:

- **Rationality disagreement** — candidate analyses disagree on `rat` (Tier B).
- **Unresolved agreement target** — Tier C, no head noun recoverable.
- **Gender disagreement** — candidate analyses disagree on `gen` after
  disambiguation.
- **Form/functional divergence** — `gen` ≠ `form_gen`, flagged for review.

The first trigger is derived from the morphology database rather than a tuned
threshold, which makes it defensible in the paper without calibration data.

### 4.5 Output contract

```
TaggedCue
  cue_id            str
  ad_id             str
  token             str
  char_span         (int, int)
  sentence_context  str
  pos               str
  gen               enum   m | f
  form_gen          enum   m | f
  rat_candidates    set    subset of {r, i, n}
  tier              enum   A | B | C
  referent          enum   applicant | non_applicant | ABSTAIN
  abstain_reason    enum | null
  head_token        str | null      Tier C only
  toolkit_version   str
  db_version        str
```

### 4.6 Known limitation to report

مطلوبة returns `rat = i` on all readings, but in recruitment ads it frequently
does refer to the sought person ("مطلوبة مهندسة"). The morphology database
encodes general MSA rationality, not recruitment register. Expect a systematic
error class here. It should be over-sampled in adjudication and reported as a
named limitation rather than discovered by a reviewer.

---

## 5. Layer 3 — Generator (C2)

### 5.1 Five-register ad typology

| Register | Description | Machine-checked invariant |
|---|---|---|
| R1 | As-found generic masculine | Contains ≥1 applicant-referring masculine cue |
| R2 | Dual / inclusive | Both gendered forms present for each applicant cue |
| R3 | Agreement-free | Zero applicant-referring gender cues (verified by the tagger) |
| R4 | Syntax-matched masculine placebo | Matches R2 in length and structure, no inclusive semantics |
| R5 | Cross-lingual English | No grammatical gender agreement |

R3's invariant is enforced by the Layer 2 tagger, which creates a dependency: the
tagger must be trustworthy before the generator can certify a register. This is a
second reason to build Layer 2 first.

R4 exists to separate "the model responds to inclusive framing" from "the model
responds to longer or more complex text."

### 5.2 Twin CV pair generator

Produces (female, male) CV pairs identical in every respect except gender
agreement morphology.

**Revised matching invariant.** The proposal specifies refusal to emit pairs
differing in token count. This is likely unsatisfiable: حاصل and حاصلة differ
under every subword tokenizer in the audit set, so a strict equality constraint
either blocks all output or forces silent padding, which is itself a confound.

Replace with a set of invariants that are satisfiable and honest:

- Identical content-word count.
- Identical qualification slot values (degree, years, institution, skills).
- Character-length difference within a declared tolerance.
- Per-pair tokenization delta measured and reported per audit subject, not forced
  to zero.
- Zero difference in any non-gender lexical item, asserted by diff.

This converts an unenforceable guarantee into a measured covariate, which is a
stronger position under review.

### 5.3 Generation method — open decision

| Method | Control | Naturalness | Leakage risk |
|---|---|---|---|
| Template-based | Highest | Lowest | Lowest |
| LLM-generated under constraints | Lowest | Highest | Highest — style may encode gender beyond morphology |
| Hybrid: template skeleton, LLM-filled slots | Medium | Medium | Medium, containable |

Recommendation pending: the hybrid, with LLM output passed through the Layer 2
tagger to verify no unintended gender cues entered the "gender-neutral" content
slots. Note that any LLM in the generator must be version-pinned and included in
the freeze.

---

## 6. Layer 4 — Blinding and freeze

### 6.1 HMAC cell blinding

Cell identity (which register, which twin polarity) is hidden from everyone who
prepares or scores material. Requirements:

- Key held outside the analysis repository.
- Blinding applied before material reaches the scoring layer.
- Unblinding is a separate, logged, one-way operation.
- Tests must confirm no cell identity leaks through file ordering, filename, or
  record ordering — ordering leaks are the most common failure mode here.

### 6.2 SD-matched competitor pools

Each twin is scored against a pool of competitor CVs matched on score standard
deviation, adopted as method from Goyal et al. (arXiv:2604.06097). Pool
composition is drawn once, frozen, and reused across cells so that pool variation
does not enter the twin contrast.

### 6.3 Cryptographic freeze

Hash over: run config, every analysis module's source, corpus checksums, model
version pins, and dependency lockfile. Confirmatory analysis refuses to run if the
hash does not match.

**Design change required.** A hash you compute and print in your own paper proves
the config did not drift. It does not prove the analysis predates unblinding,
because you control both the artifact and the clock. It needs an external time
anchor:

- OSF Registries entry (gives a timestamped DOI, and matches the social-science
  pre-registration norm the paper invokes), or
- AsPredicted, or
- An OpenTimestamps proof anchored to a public blockchain.

Cost is roughly an hour. Without it, C4's central claim is not independently
verifiable.

---

## 7. Layer 5 — Scoring, analysis, reporting

### 7.1 Audit subjects

| Subject | Type | Pin |
|---|---|---|
| multilingual-e5-large | Embedding ranker | Exact revision hash |
| BGE-M3 | Embedding ranker | Exact revision hash |
| jina-v3 | Embedding ranker | Exact revision hash |
| Arabic encoder (AraBERT / CAMeLBERT / MARBERT — to select) | Embedding ranker | Exact revision hash |
| Open-weight LLM screener × 2 | Generative screener | Exact revision + decoding params |

Ecological validity note for the paper: bare cosine similarity is not how
production ATS systems rank. The LLM screeners partly close this gap; the
limitation should be stated rather than left for a reviewer to raise.

### 7.2 Outcome measures

**Score level**

- Per-pair score difference, female minus male.
- Mean difference per cell with cluster-robust interval.
- Per-cell score variance (adopted from Goyal et al.).

**Selection level**

- Selection rate at top-k of n (design point: top-10 of 100).
- Adverse impact ratio = SR_female / SR_male, benchmarked against the four-fifths
  rule, 29 CFR 1607.4(D).
- Rank displacement distribution.

### 7.3 Statistical machinery

Variance decomposition for a twin contrast over `A` ads × `C` CV twins:

```
SE² = σ²_ad / A  +  σ²_cv / C  +  σ²_resid / (A · C)
```

> **[SUPERSCRIPTS RECONSTRUCTED]** The PDF text layer flattens the superscripts,
> extracting as `SE2 = σ2_ad / A + σ2_cv / C + σ2_resid / (A · C)`. Rendered above
> as squares. Cross-checked against the identical formula in
> `NILE2026 - SS2 Proposal .pdf` §C3, which agrees.

**Open issue requiring resolution before the pre-registration is frozen.** In a
paired design where the female and male twin from the same pair are differenced,
the pair-level random effect cancels in that difference and should not contribute
to the SE of the contrast. If σ²_cv here denotes twin-discordance variance — the
variance of the difference across pairs — the formula is correct, but the notation
reads like a CV-level random effect. A statistics reviewer will query it. Resolve
and define explicitly in one sentence.

**Required components**

- Two-way cluster-robust variance over ads and twins. The proposal reports a 1.6×
  inflation on real structure versus treating resample draws as units, and that
  resample-as-unit understates SE by more than an order of magnitude — that
  comparison is itself a reportable finding.
- Holm correction. The family must be declared explicitly: subjects × registers ×
  outcome measures multiplies quickly, and an undeclared family is a common
  reviewer objection.
- TOST or equivalent for the equivalence margins.
- Power curves over `A` and `C` at the declared margins.

### 7.4 Guarded reporting layer

Hard constraints, each with a test:

- Refuses to emit the phrase "no bias" in any output.
- Every interval reported with its clustering structure named.
- Equivalence claims blocked unless the achieved margin is met.
- Any cell with achieved power below the pre-registered floor is labelled
  inconclusive, not null.

---

## 8. Ground truth and evaluation metrics

There is no labelled "biased / not biased" ground truth, and the paper should say
so directly. Four distinct validation sources substitute for it, and they answer
different questions.

### 8.1 Tagger gold standard — the only direct ground truth

Human-adjudicated cue labels.

| Metric | Definition | Target |
|---|---|---|
| Precision (applicant-referring) | TP / (TP + FP) | Report, do not pre-commit |
| Recall | TP / (TP + FN) | Report |
| F1 | Harmonic mean | Report |
| Abstention rate | Abstains / total cues | Report; high is acceptable if precision on non-abstained is high |
| Inter-annotator agreement | Cohen's κ on double-annotated subset | ≥ 0.7 before adjudication is usable |
| Tier-wise breakdown | All above, split by Tier A / B / C | Required — Tier C will be weakest and hiding that is not defensible |

**Sampling plan.** Stratify by country, seniority, POS class, and tier.
Over-sample abstentions and the مطلوبة error class. Double-annotate a subset for κ.

### 8.2 Design-enforced invariants — not observed, asserted

Twin pairs differ only in gender morphology. This is guaranteed by construction
and verified by machine-checked diff, not measured empirically. State this
distinction plainly — it is a design guarantee, not evidence.

### 8.3 Positive control — instrument sensitivity

A cell with a deliberately injected, known-magnitude effect. If the instrument
fails to recover it, every null elsewhere is uninterpretable. This is what makes a
null result meaningful at all.

### 8.4 Zero-cue calibration cell — instrument specificity

A cell with no gender cue present. The instrument should return null. If it
returns a signal, the pipeline has a leak — most likely through ordering, pool
composition, or blinding failure.

Together, 8.3 and 8.4 are the instrument's ground truth. They deserve explicit
framing in the paper as such, because they are the answer to "how do you validate
a bias measurement with no bias labels."

### 8.5 C1 prevalence metrics

- Proportion of ads containing ≥1 applicant-referring gender cue, by country,
  seniority, occupation.
- Mean cues per ad, and per 100 tokens.
- Distribution over POS class and over tier.
- Distribution over register type as found in the wild.
- All of the above with abstentions reported separately, never silently dropped or
  silently counted.

### 8.6 C3 feasibility metrics

- Estimated σ²_ad, σ²_cv, σ²_resid from the 40 × 50 pilot.
- Required `A` and `C` for each candidate margin.
- Cost translation: expert ad-authoring hours.
- SE inflation factor, resample-as-unit versus two-way cluster-robust.
- Attainability verdict per margin: the 1 pp principled margin versus the
  four-fifths benchmark.

---

## 9. Recommended build order

Ordered by dependency, with the human-lead-time item pulled forward.

| Step | Work | Why here |
|---|---|---|
| 1 | Repository skeleton and data contracts | Cheap; every later module compiles against it. Includes the ta-marbuta preservation test. |
| 2 | Tier A/B cue extractor | Smallest piece producing real output. Testable against fixtures with no corpus, no adjudication, no models. |
| 3 | Adjudication tooling and gold set — **start in parallel with Step 2** | Only component with human lead time. All of §8.1 blocks on it and it cannot be compressed at the end. |
| 4 | Tier C dependency layer | Highest technical risk in C1. Deferred until Tiers A/B are validated so failures are attributable. |
| 5 | Full ArabJobs sweep → C1 tables | Mechanical once Steps 1–4 hold. Produces the first publishable finding. |
| 6 | Generator and register invariants | Depends on a trustworthy tagger for R3 certification. |
| 7 | Blinding, freeze, external time anchor | — |
| 8 | Analysis layer, pilot, power curves → C3 | — |
| 9 | Pre-registration → C4 | Depends on C3's numbers. |

**Why start here.** C1 is the only contribution that is a genuine empirical
finding and is fully independent of the twin machinery. It can be completed,
checked, and written up without the generator, the blinding layer, or any scoring
run. If the project stalls anywhere, C1 still stands alone as a publishable
result. C3 by contrast depends on the generator and a scoring pass, and C4 depends
on C3's numbers.

Start with Steps 1 and 2, and open Step 3 immediately alongside them.

---

## 10. Open decisions

| # | Decision | Blocks |
|---|---|---|
| 1 | ArabJobs redistribution permission | Step 5 release, not Step 5 analysis |
| 2 | Twin CV generation method (§5.3) | Step 6 |
| 3 | Which Arabic encoder as audit subject | Step 8 |
| 4 | σ²_cv definition in the SE formula (§7.3) | C4 freeze |
| 5 | Holm family declaration | C4 freeze |
| 6 | External time-anchor service (§6.3) | Step 7 |
| 7 | CV seed template source and licence | Step 6 |
| 8 | Whether C1's claim covers CVs or only ads (see §11) | Draft framing |

---

## 11. Positioning issue to resolve before drafting

The introduction argues the gender marking sits inside the CV, where no employer
edit and no redaction reaches. C1 measures prevalence in job ads. These are
different corpora supporting different claims, and as written the motivating
premise is not the thing C1 evidences.

Two resolutions:

- **Cheap and honest:** reframe C1 explicitly as measuring how ads refer to
  applicants, and let the CV claim rest on the grammar of Arabic rather than on a
  corpus measurement. Costs nothing, closes the gap.
- **Stronger, more expensive:** add a small hand-collected Arabic CV sample so the
  CV claim carries its own numbers.

This should be settled before drafting, not during.

---

## 12. Conversion log (not part of the original document)

Added by the Markdown conversion, 12 August 2026. Retained because §6.3 hashes
"every analysis module's source" and a reviewer re-reading this in two years needs
to know what was mechanical and what was reconstructed.

**Source:** `docs/ArabGN-CF-architecture.pdf`, 12 pages, producer
`Skia/PDF m153 Google Docs Renderer`. Extracted with `pypdf` 6.15.0,
`extraction_mode="layout"`. The tool was installed outside the project
environment; it is not a project dependency and does not enter the lockfile.

**Carried across verbatim:** all prose, all 14 tables, both contract blocks
(§3.2 `AdRecord`, §4.5 `TaggedCue`), all bulleted lists, all section numbering.

**Not extractable — consult the PDF:**

| Item | Location | Why |
|---|---|---|
| Figure 1 — Five-layer system architecture | §2, PDF p. 3 | Raster image, no text layer |
| Figure 2 — Referent classification and abstain routing | §4.3, PDF p. 5 | Raster image, no text layer |

**Reconstructed, with verification:**

| Item | Issue | How verified |
|---|---|---|
| SE formula superscripts (§7.3) | PDF flattens `SE²`/`σ²` to `SE2`/`σ2` | Matched against the same formula in `NILE2026 - SS2 Proposal .pdf` §C3 |
| Arabic tokens (§4.2, §4.3, §4.6, §5.2, §8.1) | Stored in visual (reversed) order; U+06BE (ARABIC LETTER HEH DOACHASHMEE) substituted for U+0647 (ARABIC LETTER HEH) | Each token reversed and re-mapped, then compared character-for-character against the independently authored `docs/linguistic-spec.md` and `tests/fixtures/tagger_fixtures.yaml` |

The ten Arabic tokens affected — المهندسة، سنوات، الشركة، خبرة، حاصلة، واسعة،
تخرجت، مطلوبة، مهندسة، حاصل — all matched their spec spellings exactly, ta-marbuta
included. No token required judgement. **No orthographic normalisation was applied
to any Arabic in this document** (CLAUDE.md prohibition 1): the U+06BE → U+0647
mapping repairs a font-encoding artifact introduced by the PDF renderer and is not
an alef/ya/ta-marbuta normalisation.
