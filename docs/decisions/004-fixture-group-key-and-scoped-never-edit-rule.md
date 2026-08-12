# ADR 004 — Fixtures gain a `group:` key; the never-edit rule is scoped to fields

- **Register ID:** D4 (P1)
- **Status:** Accepted
- **Date:** 12 August 2026
- **Affects:** `CLAUDE.md` (Testing) · `tests/fixtures/tagger_fixtures.yaml` ·
  `tests/conftest.py` · Phase 2B tests

---

## Context

`tests/fixtures/tagger_fixtures.yaml` organises 26 fixtures into nine groups, and
the phase plan drives Phase 2B tests from "groups 1, 2, 3 and 7". But the groups
exist **only as YAML comments**. There is no `group:` key, and group cannot be
derived from the ID prefix — A01–A03 (Tier A rational) and A04–A07 (Tier A
irrational) are different groups sharing the `A` prefix.

Two options were available: add the key to the fixture file, or have
`tests/conftest.py` carry a hardcoded ID→group map.

The implementer initially recommended the loader map, on the grounds that it
leaves ground truth untouched — while noting that the map can silently drift from
the comments.

## Decision

**Add `group:` to the fixture file.** The drift objection is decisive: drift here
means tests silently stop covering what the comments say they cover, and a green
suite would not reveal it. In a project whose entire claim is that a reviewer can
reproduce results, a test-coverage map that can quietly diverge from its own
documentation is exactly the wrong trade.

**And scope the never-edit rule.** CLAUDE.md previously read:

> Fixtures are ground truth authored by a human. Never edit a fixture to make a
> test pass.

As written this binds the whole file, which is over-broad — and D4 is the first
case where that bites. The rule exists to protect **ground truth about Arabic**,
not test bookkeeping. It is amended to name the protected fields explicitly:

`text` · `text_f` · `text_m` · `cue` · `expected_label` · `expected_tier` ·
`abstain_id` · `expected_text_norm` · `expected_cue_emitted` · `confidence`

Those may only be changed by the fixture author, and only through the settle-a-
REVIEW-fixture procedure. Everything else in the file — `group`, `note`,
`doc_type`, `assert_type`, header comments, ordering — is organisational and may
be maintained by an implementer.

`confidence` is deliberately protected: flipping `REVIEW` → `settled` is precisely
the corruption the rule guards against.

## Consequences

- All 26 existing fixtures gain `group: <1–9>` matching their section comments
  (27 after O03 is added by ADR 005).
- The header comment block is extended to document the fields it currently omits:
  `group`, `assert_type`, `expected_cue_emitted`, `text_f` / `text_m`.
- `tests/conftest.py` exposes fixtures by `group`, by `confidence`, and by
  `assert_type` — reading all three from the data rather than from a code-side
  map.
- CLAUDE.md's Testing section is rewritten. The prohibition is *narrowed in scope
  and strengthened in specificity*: it now names what must never change, instead
  of relying on an implementer's judgement about what counts as "a fixture".

## Note

This ADR authorises exactly two categories of fixture-file edit: adding `group:`,
and adding new fixtures where the author has specified the expected values (see
[[005-diacritic-preservation]]). It authorises no change to any existing
protected field.

## Related

[[005-diacritic-preservation]]
