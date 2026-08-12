# Corrected Build Order and Decision Register

**Supersedes:** the phase plan in `claude-code-kickoff-prompt.md`.
**Status:** the build order below is settled. **Both P0 items are now closed**
(D1, D2), along with D3, D4, D5, D10 and D11. Six remain open.

**Updated 12 August 2026.** Closed decisions have an ADR in `docs/decisions/`;
each entry below links to it. Execution plan: `docs/build-plan.md` (Phase 0 + 1)
and `docs/project-plan.md` (all eleven phases).

| ID | Status | ADR |
|---|---|---|
| D1 Abstain mechanism | **Closed** — calibrated | `001-abstain-mechanism-calibrated.md` |
| D2 Tier membership | **Closed** — (a) + `morph_class`, cross-tab conditional on probe | `002-tier-membership-and-morph-class.md` |
| D3 `DocRecord` | **Closed** | `003-docrecord-and-doc-type.md` |
| D4 Fixture `group:` | **Closed** | `004-fixture-group-key-and-scoped-never-edit-rule.md` |
| D5 Diacritics | **Closed**, with a known gap | `005-diacritic-preservation.md` |
| D6 Enclitic pronouns | Open — blocks Phase 2B scope | — |
| D7 Role test | Open — blocks Phase 5 | — |
| D8 Pro-drop default | Open — blocks Phase 5 | — |
| D9 Institution list | Open — blocks Phase 7 accuracy | — |
| D10 Lockfile | **Closed** — `uv` | `006-lockfile-uv.md` |
| D11 Freeze boundary | **Closed** — split, explicit manifest | `007-freeze-boundary.md` |
| D12 Abstain trigger counts | Open — direction stated, **needs sign-off** | — |
| D13 Determinism | Open — verified; becomes an asserted test |
| **D14 AB4 is gender-asymmetric** | **Open, P0** — found 12 Aug by the Phase 3 harness; `docs/findings/001-ab4-is-gender-asymmetric.md` | — |

---

## Part 1 — Corrected build order

The previous plan dropped architecture §9 Step 5 (full ArabJobs sweep → C1
tables), placed adjudication behind two serial gates in contradiction of §9 and of
its own rationale, and asserted a twin-symmetry invariant that cannot be
discharged before Tier C exists.

### Revised phases

| Phase | Work | Arch §9 Step | Gate type |
|---|---|---|---|
| 1 | Repository skeleton, data contracts, normalisation | 1 | Review |
| 2A | Adjudication tooling — **starts with Phase 1, runs continuously** | 3 | None (continuous) |
| 2B | Tier A/B cue extractor | 2 | Review |
| 3 | Twin symmetry, Tiers A/B only — **provisional** | — | Review |
| 4 | Gold set reaches κ ≥ 0.7; threshold calibration if D1 selects calibrated | 3 | Hard block |
| 5 | Tier C dependency layer | 4 | Review |
| 6 | Twin symmetry **re-run across all tiers** — binding | — | Hard block |
| 7 | Full ArabJobs sweep → C1 tables | 5 | **Deliverable** |
| 8 | Generator and register invariants | 6 | Review |
| 9 | Blinding, freeze, external time anchor | 7 | Review |
| 10 | Analysis layer, pilot, power curves → C3 | 8 | Review |
| 11 | Pre-registration → C4 | 9 | Deliverable |

### What changed and why

**Phase 2A runs in parallel, not fourth.** Architecture §9 Step 3 states
adjudication is the only component with human lead time and cannot be compressed
at the end. If decision D1 retains calibrated thresholds, the gold set is
*upstream* of completing the extractor, not downstream — Phase 2B cannot be
finished without it. Treat 2A as continuous background work from day one, not a
gated phase.

**Phase 3 is explicitly provisional.** Twin symmetry over Tiers A and B tests
symmetry-in-abstention, not symmetry-in-classification. The cues carrying the
paper's phenomenon — verb agreement, participles routed to Tier C — are absent.
Phase 3 is a smoke test. Phase 6 is the invariant.

**Phase 6 is a hard block.** If the instrument classifies feminine and masculine
text asymmetrically, every downstream measurement is confounded by the instrument
itself. Nothing proceeds past a failure here.

**Phase 7 restored.** The previous plan omitted it entirely. Architecture §9 calls
it the first publishable finding and states that C1 alone stands if the project
stalls elsewhere. It is the highest-value deliverable in the sequence and it was
missing.

**Phase 4 is a hard block on κ.** Below κ ≥ 0.7 the gold set is not usable, so
every precision/recall figure downstream is uninterpretable. This is a real
possibility, not a formality — referent classification is a genuinely hard
annotation task.

---

## Part 2 — Decision register

Thirteen open items. P0 blocks implementation entirely; P1 blocks a specific
phase; P2 blocks the freeze.

### P0 — blocks any implementation

**D1. Abstain mechanism: threshold-free or calibrated?**

Architecture §4.4 and linguistic spec §4.2 specify incompatible designs.

- §4.4: the trigger derives from the morphology database, needs no calibration
  data, and is defensible in the paper without a gold set.
- §4.2: the trigger depends on `θ_high` / `θ_low`, calibrated against the gold set
  and frozen, declared in the pre-registration.

| | Threshold-free | Calibrated |
|---|---|---|
| Pre-registration | Cleaner — no free parameters to defend | Two frozen parameters to justify |
| Gold set dependency | None | Blocks Phase 2B completion |
| Accuracy | Lower — raw candidate membership is noisy (`معتمدة` → `{i,n,r}`) | Higher |
| Reviewer objection | "Your abstain rate is near 100%" | "Where did θ come from?" |

Verified evidence: raw candidate-set membership is too permissive. `شمس` and
`معتمدة` both return `{i, n, r}`. A threshold-free rule that abstains on any
disagreement will abstain on nearly everything.

*Recommendation, but yours to make:* calibrated, and amend §4.4 to drop the
no-calibration claim. The threshold-free version does not appear to work on real
text. If you take this, §4.4 must be rewritten — leaving both claims in the
documents is the current defect.

**D2. Tier membership: morphological class or CAMeL POS?**

Verified 12 Aug: active participles split across tiers by lexeme, not by
linguistic property.

| Token | Category | POS | Tier |
|---|---|---|---|
| حاصلة، حاصل، حاصلا، وحاصلة | active participle | `noun` | B |
| المتقدم، المسؤولة، مسؤول، العاملة | active participle | `adj` | C |
| خريجة، المرشحة | agentive noun | `noun` | A |

Consequences if unaddressed:
- Tier-wise precision/recall (§8.1) stratifies by an artifact of the CAMeL
  lexicon, not by anything the paper can interpret.
- `rat_candidates` differs systematically by path: `المسؤولة` → `{i,n,r}`,
  `المرشحة` → `{i,r}`. The `n` from the `adj` path changes how D1's rule behaves
  across tiers.
- `حاصلة` never surfaces `r` at top-1 in any tested context, including
  `خريجة كلية الهندسة وحاصلة على تقدير جيد` where the reference is unmistakable.

Options: (a) keep POS-based tiers and report the lexicon dependency as a
limitation; (b) redefine tiers on morphological class so participles form one
path; (c) add a participle tier.

Touches: spec §5, §7.2; architecture §8.1.

### P1 — blocks a specific phase

**D3. `AdRecord` → `DocRecord`, add `doc_type`.** Architecture §3.2 omits
`doc_type`, but spec §5.2 requires it, every fixture carries it, and Tier C
pro-drop is undefined without it. `AdRecord` is also the wrong name once the
contract holds CVs. *Blocks Phase 1.*

**D4. Fixture `group:` key.** Groups exist only as YAML comments and cannot be
derived from ID prefixes (A01–A03 and A04–A07 are different groups). Add the key
to the fixture file — the never-edit rule binds the implementing agent, not the
fixture author. *Blocks Phase 2B tests.*

**D5. Diacritic rule.** Architecture §3.2 says diacritics preserved; no fixture
covers harakat. Add a fixture asserting `مُهَنْدِسَة` survives normalisation
unchanged. *Blocks Phase 1.*

**D6. Enclitic pronouns as separate cues.** Spec §3.2. `خبرتها` carries two gender
markings referring to different entities. *Blocks Phase 2B scope.*

**D7. Role test and its closed list.** Spec §5.1. Rational ≠ applicant; a job ad
refers to managers, clients, teams. *Blocks Phase 5.*

**D8. Pro-drop default by document type.** Spec §5.2. `تخرجت` in a CV has no overt
subject. *Blocks Phase 5 and fixtures C05–C07.*

**D9. Institution-name list.** Spec §7.3. `شمس` in `جامعة عين شمس` returns
`rat=r`. *Blocks Phase 7 accuracy.*

### P2 — blocks the freeze

**D10. Lockfile tool.** Architecture §6.3 hashes the dependency lockfile.
`pyproject.toml` is not a lockfile. Choose uv, pip-tools, or poetry. *Blocks
Phase 9 and should be settled at Phase 1 so the lock exists from the first
commit.*

**D11. Freeze boundary.** `CLAUDE.md` says modules under `arabgn/analysis/` enter
the freeze and must be I/O-free. The tagger lives in `arabgn/tagger/` and produces
C1. Does it enter the freeze? If yes, the layout needs revising and the tagger
must be I/O-free.

**D12. Reconcile abstain trigger counts.** Architecture §4.4 lists four; spec §6
lists six (adds AB3, AB6). Spec is authoritative; architecture needs updating.

**D13. Determinism assertion.** BERT disambiguation verified byte-identical across
three runs including model reload, CPU, single process — scores stable to 10
decimal places. This must become an asserted test and be re-verified on the
hardware doing the real sweep. GPU kernel nondeterminism is the usual failure.
Also: `rat_candidates` is typed as `set` in §4.5; prohibition 6 forbids iterating
a set for output. Store as `frozenset`, serialise sorted.

---

## Part 3 — Sequencing the decisions

D1 and D2 interact and should be settled together. If D2 redefines tiers on
morphological class, participles occupy one path and D1's rule only has to behave
consistently within it rather than across two paths with different candidate-set
shapes.

Settle in this order:

1. **D1 + D2 together** — everything else in the tagger depends on them.
2. **D3, D4, D5, D10** — mechanical, unblock Phase 1, no research needed.
3. **D6** — scopes Phase 2B.
4. **D11, D12, D13** — documentation and layout, can run alongside Phase 1.
5. **D7, D8, D9** — needed before Phase 5, not before Phase 1. These are the
   genuinely hard linguistic questions and deserve the most thought.

Once D1–D6 and D10 are closed, a corrected implementation prompt can be written
for Phases 1 through 2B. Writing one before then would resolve them by default,
which is the defect this register exists to prevent.