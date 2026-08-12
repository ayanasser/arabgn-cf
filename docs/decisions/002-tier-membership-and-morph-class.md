# ADR 002 — Tiers stay mechanism-based; linguistic class is recorded separately

- **Register ID:** D2 (P0)
- **Status:** Accepted, with the cross-tabulation **conditional** on the
  feasibility probe in `002-appendix-morph-class-feasibility.md`
- **Date:** 12 August 2026
- **Affects:** `docs/architecture.md` §4.5, §8.1 · `docs/linguistic-spec.md` §5,
  §7.2 · `arabgn/contracts.py` · Phase 2B · Phase 7 reporting

---

## Context

Tier membership is defined in spec §5 by CAMeL POS: nominal cues route to Tier A
or B, `verb` / `adj` cues route to Tier C. Verified probing on 12 August 2026
showed that **active participles split across tiers by lexeme, not by any
linguistic property**:

| Token | Linguistic category | CAMeL POS | Tier |
|---|---|---|---|
| حاصلة، حاصل، حاصلا، وحاصلة | active participle | `noun` | B |
| المتقدم، المسؤولة، مسؤول، العاملة | active participle | `adj` | C |
| خريجة، المرشحة | agentive noun | `noun` | A |

Same linguistic category, different tiers, decided by which entry the CAMeL
lexicon happens to carry.

Three consequences follow:

1. Tier-wise precision/recall (architecture §8.1) stratifies by an artifact of the
   CAMeL lexicon rather than by anything the paper can interpret.
2. `rat_candidates` differs systematically by path — `المسؤولة` → `{i,n,r}` via
   the `adj` path, `المرشحة` → `{i,r}` via the `noun` path. The extra `n` mass
   changes how [[001-abstain-mechanism-calibrated]]'s rule behaves across tiers.
3. `حاصلة` never surfaces `r` at top-1 in any tested context, including
   `خريجة كلية الهندسة وحاصلة على تقدير جيد`, where the reference is unmistakable.

## Options considered

- **(a)** Keep POS-based tiers, report the lexicon dependency as a limitation.
- **(b)** Redefine tiers on morphological class so participles occupy one path.
- **(c)** Add a dedicated participle tier.

## Decision

**(a), extended: keep mechanism-based tiers, and record enough on each
`TaggedCue` to reconstruct the linguistic class.**

Add a `morph_class` field to the `TaggedCue` contract (architecture §4.5). Report
architecture §8.1 as a **tier × morphological-class cross-tabulation** rather than
tier alone.

Rationale, per the author: this converts the lexicon dependency from a footnote
into a **measured quantity the paper can point at**, which is a stronger result
than either hiding it or re-engineering the tier definitions around it. It also
directly serves the §7 error-class reporting, where `المتقدم` (§7.2) is already
known to route by POS in a way that produces a systematic abstain.

Tiers remain mechanism-based because the tier *is* the resolution mechanism —
lexical, ambiguity-abstain, syntactic-inheritance. That is a real distinction and
worth keeping. What was wrong was letting it double as a linguistic claim.

## Conditional on a feasibility probe

The author's caveat, recorded verbatim in intent:

> I don't know how reliably active-participle status can be derived from the CAMeL
> analysis fields. It may need a frozen lexeme list or pattern matching, and that
> needs checking before you commit to the cross-tab. If it turns out unreliable,
> fall back to (a) — but check first, because the cross-tab is worth real effort.

`morph_class` is a field on the output contract, so this must be settled **before**
`TaggedCue` is written, not discovered during Phase 2B.

The probe and its go/no-go verdict are recorded in
`002-appendix-morph-class-feasibility.md`.

- **Go** → `morph_class` enters the contract; §8.1 becomes a cross-tabulation; the
  derivation rule is recorded and frozen.
- **No-go** → fall back to plain (a); drop `morph_class` and the cross-tab; amend
  this ADR; report the lexicon dependency as a stated limitation instead.

## Consequences

- No existing fixture changes. Every `expected_tier` in
  `tests/fixtures/tagger_fixtures.yaml` remains valid as written, because the tier
  definition is unchanged. This is the main practical advantage of (a) over (b)
  and (c), both of which would have required re-tiering ground truth.
- The `tier` enum stays `A | B | C`.
- If the probe returns go, any derivation depending on a frozen lexeme list or
  pattern set must be declared in the pre-registration and enter the freeze hash,
  the same as the institution list contemplated in spec §7.3 (register D9).
- Tier is **never** to be read as a linguistic claim in any output or table.
  Spec §5 must say so explicitly.

## Related

[[001-abstain-mechanism-calibrated]] · [[007-freeze-boundary]]
