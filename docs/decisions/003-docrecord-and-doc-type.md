# ADR 003 — `AdRecord` becomes `DocRecord` and gains `doc_type`

- **Register ID:** D3 (P1)
- **Status:** Accepted
- **Date:** 12 August 2026
- **Affects:** `docs/architecture.md` §3.2 · `arabgn/contracts.py` · Phase 1 ·
  Phase 5 (pro-drop)

---

## Context

The corpus-loader contract in architecture §3.2 defines `AdRecord` with seven
fields and no document-type flag. Three independent places require one:

1. **Linguistic spec §5.2** states it directly: *"This makes the label
   context-dependent, so `AdRecord` must carry a document-type flag."* Pro-drop
   resolution defaults differently in a CV (subjectless finite verb → applicant)
   than in an ad (the subject may be the company — `الشركة تبحث`).
2. **Every fixture** in `tests/fixtures/tagger_fixtures.yaml` carries
   `doc_type: ad | cv`, including the settled ones.
3. **Tier C is undefined without it** — fixtures C05–C07 turn on the CV default.

Separately, the name is wrong. Once the contract holds CVs as well as
advertisements, `AdRecord` misdescribes its own contents, and the `ad_id` field
misdescribes its key.

## Decision

Amend architecture §3.2:

```
DocRecord
  doc_id           str    stable hash of source text
  doc_type         enum   ad | cv
  text_raw         str    unmodified source
  text_norm        str    Unicode-normalised, diacritics preserved
  country          enum   EG | JO | SA | AE
  occupation       str    from source metadata
  seniority        enum   entry | mid | senior | unspecified
  source_checksum  str
```

`AdRecord` → `DocRecord`; `ad_id` → `doc_id`; add `doc_type`.

## Consequences

- `TaggedCue.ad_id` (architecture §4.5) renames to `doc_id` for consistency. This
  is the only knock-on rename.
- No fixture changes — fixtures already carry `doc_type`, and it is not a
  protected field question since nothing about its values is altered.
- The architecture doc's §3.2 heading "Corpus loader — contract" still says
  "a normalised record per advertisement." That sentence is amended to "per
  document."
- Phase 5 pro-drop (register D8) can now be specified. It remains open — this ADR
  provides the field, not the rule.

## Related

[[008-pro-drop-default]] does not exist yet; D8 is open.
