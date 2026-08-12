# What needs you

**Updated:** 12 August 2026 · Companion to `docs/STATUS.md`.

Ordered by how much work each unblocks. Nothing here can be decided by an
implementer — that is why it is here rather than done.

---

## 🔴 Now — ahead of all engineering

### 1. Correct the SS2 proposal

**Why it outranks everything:** C4's argument is that a reviewer can check the
artifact. The proposal's artifact claims are the most checkable statements in it,
and they are false.

| Claim | Reality |
|---|---|
| "Phase 0 of the instrument is complete and tested" | Design docs complete; implementation at Phase 1 |
| "117 automated tests" | see `docs/STATUS.md` §6 for the live count |
| "~7,900 lines" | roughly an order of magnitude fewer |
| Feasibility table: "Instrument ready, blocking" (4–7 Aug) | Generator, scoring and analysis unbuilt |
| Feasibility table: "Tagger implemented" (6–10 Aug) | Phase 2B in progress |

It is **not yet submitted**, so this is an edit, not a correction to chairs.
Full itemisation and suggested rewrites: `docs/proposal-corrections.md`.

**Also decide the timeline.** C1 by 18 August is not reachable — the gold set
alone is days of human work. Three options are laid out in §4 of that document.

**Action:** edit the source document. I cannot edit the PDF.

---

## 🟠 Next — each unblocks a phase

### 2. D6 — Are enclitic pronouns separate cues? *(scopes Phase 2B)*

Spec §3.2. `خبرتها` carries **two** gender markings for two different entities:
the experience (feminine, irrational) and its possessor (feminine, possibly the
applicant). Spec recommends treating the enclitic as a separate cue with its own
span.

Currently excluded, so the tagger will under-count applicant cues in exactly the
possessive constructions CVs are full of.

**Action:** confirm the spec's recommendation, or rule it out.

### 3. D8 — Pro-drop default by document type *(unblocks C05, C06, C07 and half of Phase 5)*

Spec §5.2. `تخرجت من جامعة القاهرة` has no overt subject. Spec recommends: in CV
context a subjectless finite verb defaults to applicant-referring; in ad context
it does not, because the subject may be the company (`الشركة تبحث`).

This is the paper's central phenomenon — `تخرجت`, `عملت` are exactly the markings
that survive name redaction.

**Action:** confirm the recommendation. `DocRecord.doc_type` already exists to
carry it.

### 4. D7 — The role test and its closed list *(blocks Phase 5)*

Spec §5.1. Rational ≠ applicant: `يعمل تحت إشراف المدير التنفيذي` — `المدير` is
rational but is not the applicant. Spec recommends four qualifying roles and
proposes excluding supervision/employer/client relations, but notes the closed
list "needs annotation work."

**This is the hardest item here and deserves the most thought.** The list is a
frozen artifact entering the pre-registration.

### 5. D9 — Institution-name list *(blocks Phase 7 accuracy)*

Spec §7.3. `شمس` in `جامعة عين شمس` analyses as `rat=r` — a false
applicant-referring cue inside an institution name. Options: a frozen
institution list applied as a pre-pass (declared in the pre-registration), or
accept and report.

Affects fixture E03.

### 6. D12 — Sign off the abstain trigger count

Architecture §4.4 listed four triggers; spec §6 lists six. I applied the spec's
six, since the register states spec is authoritative — but you have not signed
that off. Trivial to confirm, and it is in the code now.

---

## 🟡 Start in parallel — human lead time

### 7. Recruit and brief annotators *(Phase 4 — the binding constraint)*

Architecture §9: adjudication is "the only component with human lead time" and
"cannot be compressed at the end." ADR 001 made it **upstream** of finishing the
tagger, because θ calibrates against the gold set.

Needed:
- Annotators fluent in MSA, briefed on spec §8
- A double-annotated subset for Cohen's κ
- A third annotator for adjudication (§8.4)
- **κ ≥ 0.7 or the gold set is unusable** — this gate can genuinely fail;
  referent classification is hard

The tooling will be ready before the people are. **Start recruiting now.**

### 8. The ten REVIEW fixtures

Each is an open question being skipped, not a passing test.

| Fixture | Question | Depends on |
|---|---|---|
| B01, B02 | Is ABSTAIN right, or does the role test resolve `حاصلة`? | D7 |
| C04 | Does `ممتازة` attach to `مهارات` or `تواصل`? | — |
| C05, C06, C07 | Pro-drop default | D8 |
| E01 | Confirm the `مطلوبة` error-class framing and its human gold label | — |
| E02 | Accept AB2 abstain for `المتقدم`, or add an applicant lexicon? | — |
| E03 | Institution list, or accept and report? | D9 |
| T02 | Verb-agreement twin | Phase 5 |

To settle one: tell me the ID, the expected value, and why. I update the fixture,
amend the spec section, write an ADR, and un-skip the test. **That is the only
circumstance in which I touch a fixture.**

---

## 🟢 Lower urgency, but they block the freeze

| # | Item | Blocks |
|---|---|---|
| 9 | Export Figures 1 & 2 from the source Google Doc as images into `docs/` | Reviewability — they exist only in the PDF |
| 10 | Author a stacked-diacritic fixture (shadda + vowel); expected value must be yours | Closes the ADR 005 gap |
| 11 | Define σ²_cv in the SE formula — CV-level random effect or twin-discordance variance? One sentence | C4 freeze (arch §7.3, §10 #4) |
| 12 | Declare the Holm family explicitly | C4 freeze |
| 13 | Choose the external time anchor (OSF / AsPredicted / OpenTimestamps), ~1 h | Phase 9; without it C4 is not independently verifiable |
| 14 | Chase ArabJobs redistribution permission | Phase 7 *release*, not analysis |
| 15 | Choose the twin-CV generation method (template / LLM / hybrid) | Phase 8 |
| 16 | Choose the Arabic encoder audit subject | Phase 10 |
| 17 | Resolve the §11 positioning issue — does C1 cover CVs or only ads? | Draft framing |

---

## Quick reference — what unblocks the most

1. **Proposal correction** — nothing downstream repairs it
2. **Annotator recruitment** — longest lead time, gates Phase 4 → 2B → 7
3. **D8** — unblocks three fixtures and half of Phase 5
4. **D6** — scopes Phase 2B
5. **D7** — hardest, blocks Phase 5
