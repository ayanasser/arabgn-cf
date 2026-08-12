# ADR 005 — Diacritic preservation is asserted on single-mark tokens only

- **Register ID:** D5 (P1)
- **Status:** Accepted, **with a known gap**
- **Date:** 12 August 2026
- **Affects:** `tests/fixtures/tagger_fixtures.yaml` (new O03) ·
  `tests/test_normalisation.py` · Phase 1

---

## Context

Architecture §3.2 requires `text_norm` to be "Unicode-normalised, diacritics
preserved". CLAUDE.md prohibition 1 permits NFC and nothing else. But the fixture
suite guards only two orthographic properties:

- **O01** — ta-marbuta (`ة`) survives
- **O02** — hamza forms (`أ إ آ`) survive

Nothing covers harakat. A normalisation step that stripped diacritics while
leaving `ة` and hamza intact would pass the entire existing suite.

### The complication

NFC is not a no-op on diacritics. Unicode canonical ordering reorders combining
marks by combining class, so a base letter carrying **stacked** marks — shadda
plus a vowel, for instance — may legitimately come out of NFC in a different byte
order than it went in. A naive byte-identity assertion on such a token would fail
for a *correct* implementation.

That makes "what should the fixture assert?" a real question rather than a
formality, and its answer is a claim about Arabic orthography.

## Decision

**Assert byte-identity on single-mark tokens only.**

New fixture O03:

```yaml
- id: O03
  doc_type: cv
  group: 8
  text: "مُهَنْدِسَة"
  assert_type: normalisation
  expected_text_norm: "مُهَنْدِسَة"
  confidence: settled
```

`مُهَنْدِسَة` carries exactly one mark per base letter — damma, fatha, sukun,
kasra, fatha — with no stacking anywhere. NFC is therefore the identity function
on it, and byte-equality is the correct assertion.

## Consequences

### The gap this leaves, stated plainly

This decision **avoids** the combining-mark reordering question rather than
answering it. O03 proves that diacritics are not *stripped*. It does not prove
that a token with stacked marks round-trips correctly, because no such token is
tested.

A stacked-mark fixture is still owed. Its `expected_text_norm` is a claim about
correct Arabic orthography under Unicode canonical ordering and must be authored
by the fixture author, not derived by an implementer from whatever the code
returns — that would be exactly the assert-current-behaviour pattern CLAUDE.md
forbids.

**Recorded as an open item.** It does not block Phase 1. It should be closed
before the freeze, because `text_norm` feeds every downstream measurement.

### Scope

Real ArabJobs text is largely undiacriticised, so the practical exposure is low —
but "low exposure" is not "tested", and the freeze covers the normalisation
function regardless.

## Related

[[004-fixture-group-key-and-scoped-never-edit-rule]] authorises adding this
fixture: the author specified both the token and the assertion form, so no
protected field is being invented by an implementer.
