# ADR 002 appendix — `morph_class` feasibility probe

- **Verdict: GO, with an amendment to ADR 002's framing and one caveat**
- **Date:** 12 August 2026
- **Environment:** camel-tools 1.6.0, `calima-msa-r13`, Python 3.12.12
- **Probe:** `Analyzer.analyze()` over the D2 token set, all analyses (not top-1)

The author's condition on ADR 002:

> I don't know how reliably active-participle status can be derived from the CAMeL
> analysis fields. It may need a frozen lexeme list or pattern matching, and that
> needs checking before you commit to the cross-tab. If it turns out unreliable,
> fall back to (a).

---

## 1. First: a correction to CLAUDE.md and the setup docs

The download package and the API dataset have **different names**:

| Purpose | Name |
|---|---|
| `camel_data -i ...` | `morphology-db-msa-r13` |
| `MorphologyDB.builtin_db(...)` | `calima-msa-r13` |

`MorphologyDB.builtin_db('morphology-db-msa-r13')` raises `KeyError`. CLAUDE.md
and architecture §4.1 both quote the download name; neither records the API name.
Recorded here so the next implementer does not lose time on it.

Available `MorphologyDB` datasets: `calima-egy-r13`, `calima-glf-01`,
`calima-lev-01`, `calima-msa-r13`, `calima-msa-s31`.

## 2. The field that carries morphological class

**`stemcat`.** It is present on every analysis and encodes the stem's
morphological category directly. Observed values on the fixture vocabulary:

`N/ap` · `N-ap` · `Nall` · `N` · `N0` · `Ndu` · `Napdu` · `NAt` · `NapAt` ·
`PV` · `PV_intr` · `IV_0hwnyn` · `IV_0hwnyn_yu`

`pattern` corroborates it — form-I active participles carry the templatic pattern
`1ا2ِ3` (فاعِل) — but `pattern` alone would require a hand-built pattern→class
table, whereas `stemcat` states the category.

## 3. The finding that matters — D2's premise is wrong, and the truth is better

D2 framed the problem as *"active participles split across tiers by lexeme"* —
implying tier is a stable but arbitrary property of a token.

It is not. **`pos`, `rat` and `stemcat` co-vary across analyses of the same
token**, and tier therefore follows *the analysis the disambiguator selects in
context*, not the token:

| Token | by `stemcat` |
|---|---|
| حاصلة | `N/ap` → (`noun`, rat=`i`) · `Nall` → (`noun`, rat=`r`) |
| حاصل | `N/ap` → (`noun`, rat=`i`) · `Nall` → (`noun`, rat=`r`) |
| العاملة | `N/ap` → (`noun`, rat=`r`) · `Nall` → (`adj`, rat=`n`) |
| المسؤولة | `Nall` → (`adj`, rat=`n`) **and** (`noun`, rat=`r`) |
| مسؤول | `Nall` → (`adj`, rat=`n`) **and** (`noun`, rat=`r`) |
| المرشحة | `Nall` → (`noun`, rat=`r`) only |
| خريجة | `Nall` → (`noun`, rat=`r`) only |

Two corrections to the D2 table follow:

- **العاملة is not simply `adj`/Tier C.** It carries both an `N/ap` `noun` reading
  (rat=`r`) and an `Nall` `adj` reading (rat=`n`). Which tier it lands in depends
  on context.
- **`المتقدم` is the only genuinely single-analysis case** in the participle set
  (`adj`, `Nall`, rat=`n`, 4 analyses, all identical in these fields) — which is
  exactly why spec §7.2 predicts it abstains under AB2 with no recoverable target.

## 4. The strongest result: AB1's ambiguity on `حاصلة` *is* a class ambiguity

Decomposing B01's `rat_cands = {i, r}` by `stemcat`, with glosses:

| `stemcat` | n | `rat` | `lex` | gloss |
|---|---|---|---|---|
| `N/ap` | 22 | `i` | حاصِل | **income** + [fem.sg.] |
| `Nall` | 11 | `r` | حاصِل | **holder** + [fem.sg.] |

The rationality ambiguity that AB1 exists to catch is not disambiguator noise. It
is a clean, interpretable, lexicographically attested split between two readings
of the same surface form: *"income/proceeds (fem.)"* versus *"holder (fem.)"*.

This materially strengthens two existing claims:

- **ADR 001 §4.2.2** observed that context does not move `حاصلة` (r = 0.324 in ad
  context, 0.330 in CV context) and argued abstention is therefore correct
  behaviour. This explains *why*: both readings are grammatically licensed in both
  contexts, so there is nothing for context to resolve. The instrument is not
  failing to decide — there is genuinely nothing to decide without world
  knowledge.
- **The paper can now say what the tagger abstains on**, in linguistic terms, with
  a dictionary gloss, rather than reporting an abstention rate and leaving the
  reader to wonder whether it is a modelling artifact.

## 5. Verdict

**GO** — `morph_class` enters the `TaggedCue` contract, derived from `stemcat`.

**Amend ADR 002's framing:** `morph_class` is a property of the **selected
analysis**, not of the token. It is recorded per cue alongside the tier that
analysis produced. The architecture §8.1 cross-tabulation is therefore
tier × morph-class *of the winning analysis*, which is well defined.

### Caveat, and it is real

`stemcat` does **not** resolve every case. For `مسؤول` / `المسؤولة`, both the
`adj`/rat=`n` and `noun`/rat=`r` readings sit inside `Nall`, so `stemcat` does not
separate them. It cleanly isolates the form-I active participle (`N/ap`, فاعِل)
but does not give "active participle" as a general linguistic class — form-V
`متقدم` and passive-participle `مسؤول` both fall in `Nall`.

Consequences:

1. A **`stemcat` → `morph_class` mapping table is required**, and it is a
   linguistic artifact that needs author validation, not implementer judgement.
   It enters the freeze manifest (ADR 007), like the institution list in D9.
2. The mapping cannot be enumerated exhaustively from the DB in advance — the
   `stemcat` inventory is not exposed through the public `MorphologyDB` API, so
   the table must be built from values **observed during the ArabJobs sweep** and
   validated then. Until it is, `morph_class` should carry the raw `stemcat` and
   a `null` mapped class rather than a guessed one.
3. **`morph_class` is nullable in the contract** for exactly this reason.

### What Phase 1 does with this

`TaggedCue.morph_class` is added as `str | None`. The contract records the raw
`stemcat` verbatim. The mapping to a human-readable class is deferred to a
separate frozen table, authored later, and is **not** invented now.

That keeps the go decision cheap and reversible: if the mapping turns out
unworkable at Phase 7, the field degrades to raw `stemcat` and §8.1 falls back to
tier-alone with a stated limitation, exactly as the no-go branch would have.
