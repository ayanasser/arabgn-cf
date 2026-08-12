"""Data contracts for ArabGN-CF.

Implements ``docs/architecture.md`` §3.2 (``DocRecord``) and §4.5 (``TaggedCue``),
with the enums of ``docs/linguistic-spec.md`` §6 (abstain triggers).

This module enters the freeze manifest (ADR 007): it defines output shape, so a
change here changes results. It is pure — no I/O, no side effects, no model
loading — and must stay that way.

Determinism (CLAUDE.md prohibition 6) shapes two choices here:

* ``rat_candidates`` is a ``frozenset``, serialised in a fixed sorted order.
  Architecture §4.5 types it ``set``, which would make output order
  implementation-defined.
* Every enum has an explicit, stable string value. Nothing derives an output
  value from declaration order or from ``hash()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Canonical ordering for serialising rationality candidate sets. Explicit rather
# than sorted() on the enum, so the wire order is a stated decision and cannot
# drift if the enum is reordered.
_RAT_ORDER = ("r", "i", "n")


class DocType(str, Enum):
    """Document type. Required — pro-drop defaults differ (spec §5.2).

    ``تخرجت من جامعة القاهرة`` has no overt subject. In a CV the subject is the
    applicant; in an ad it may be the company (``الشركة تبحث``).
    """

    AD = "ad"
    CV = "cv"


class Country(str, Enum):
    """ArabJobs coverage (architecture §3.2)."""

    EG = "EG"
    JO = "JO"
    SA = "SA"
    AE = "AE"


class Seniority(str, Enum):
    """Architecture §3.2."""

    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    UNSPECIFIED = "unspecified"


class Gender(str, Enum):
    """Grammatical gender.

    ``gen`` is functional gender; ``form_gen`` is surface gender. They diverge on
    broken plurals — ``طلبة`` is form-feminine but functionally masculine plural —
    which is what AB5 catches (spec §7.4).

    Binary because Arabic agreement morphology is binary (architecture §1.3), not
    as a claim about gender.
    """

    M = "m"
    F = "f"


class Rationality(str, Enum):
    """The ``rat`` feature: Alkuhlani & Habash (2011), exposed by CAMeL Tools.

    ``R`` human, ``I`` non-human, ``N`` not applicable — typically verbs and
    adjectives, which inherit rationality from their agreement target.

    Rationality is the primary evidence for applicant-reference but is **not
    identical to it** (spec §2). ``خبرة واسعة`` is feminine twice over and refers
    to a thing.
    """

    R = "r"
    I = "i"  # noqa: E741 — the feature is named `i` in the literature and the DB
    N = "n"


class Tier(str, Enum):
    """Referent-classification tier (spec §5).

    A tier names **how** reference is resolved — lexically, by abstaining on
    lexical ambiguity, or by syntactic inheritance. It is **not** a linguistic
    claim about the cue and must never be read as one in any output or table
    (ADR 002). Linguistic class lives in :attr:`TaggedCue.morph_class`.

    Architecture §8.1 requires tier-wise metrics, so the tier must be recorded on
    every emitted cue and never re-inferred after the fact.
    """

    A = "A"  # lexical resolution
    B = "B"  # lexical ambiguity -> abstain
    C = "C"  # syntactic resolution (agreement inheritance)


class Referent(str, Enum):
    """Whether the marking refers to the job applicant (spec §2).

    ``ABSTAIN`` is a first-class outcome, never a missing value. Abstained cues
    are reported as their own category and are never dropped from a metric or
    silently assigned to a class (CLAUDE.md prohibition 3).
    """

    APPLICANT = "applicant"
    NON_APPLICANT = "non_applicant"
    ABSTAIN = "ABSTAIN"


class AbstainTrigger(str, Enum):
    """The complete trigger list, spec §6.

    Architecture §4.4 previously listed only four of these; it was reconciled to
    six on 12 Aug 2026 (register D12). Every abstained cue records its trigger —
    adjudication is stratified by it (spec §8.3).
    """

    AB1 = "AB1"  # rationality does not resolve under §4.2            (Tier B)
    AB2 = "AB2"  # agreement target not identifiable                  (Tier C)
    AB3 = "AB3"  # agreement target itself abstains                   (Tier C)
    AB4 = "AB4"  # candidates disagree on `gen` after disambiguation  (any)
    AB5 = "AB5"  # gen != form_gen (functional/form divergence)       (any)
    AB6 = "AB6"  # rational cue whose role test is indeterminate      (Tier A)


@dataclass(frozen=True, slots=True)
class DocRecord:
    """One normalised source document. Architecture §3.2.

    Renamed from ``AdRecord`` per ADR 003: the contract holds CVs as well as
    advertisements, and Tier C is undefined without :attr:`doc_type`.

    ``text_norm`` is NFC only. Ta-marbuta, hamza forms and diacritics are all
    preserved — see :func:`arabgn.analysis.text.normalise` and CLAUDE.md
    prohibition 1.
    """

    doc_id: str
    doc_type: DocType
    text_raw: str
    text_norm: str
    country: Country
    occupation: str
    seniority: Seniority
    source_checksum: str


@dataclass(frozen=True, slots=True)
class TaggedCue:
    """One gender cue and its referent classification. Architecture §4.5.

    A gender cue is a token whose morphological analysis carries ``gen ∈ {m, f}``
    and whose POS is a content class (spec §2, §3.1). Function words are excluded:
    ``على`` returns ``rat={n, na, r}`` and would flood the abstain queue.

    A token may carry more than one gender marking — ``خبرتها`` marks both the
    experience and its possessor. Each is a separate ``TaggedCue`` with its own
    span; they are never collapsed (spec §3.3).
    """

    cue_id: str
    doc_id: str
    token: str
    char_span: tuple[int, int]
    sentence_context: str

    pos: str
    #: Raw CAMeL ``stemcat`` of the **selected analysis**, e.g. ``"N/ap"``.
    #:
    #: Recorded so architecture §8.1 can be reported as a tier x morphological-
    #: class cross-tabulation instead of stratifying by a lexicon artifact
    #: (ADR 002).
    #:
    #: Nullable by design. The probe
    #: (``docs/decisions/002-appendix-morph-class-feasibility.md``) found that
    #: ``stemcat`` does not separate every case — ``مسؤول`` carries both an
    #: ``adj``/rat=n and a ``noun``/rat=r reading inside ``Nall`` — so the mapping
    #: from ``stemcat`` to a human-readable class is a frozen, author-validated
    #: table built from values observed in the sweep. Until that table exists this
    #: field carries the raw ``stemcat`` and the mapped class stays ``None``
    #: rather than being guessed.
    morph_class: str | None

    gen: Gender
    form_gen: Gender
    #: Subset of {r, i, n}. ``frozenset``, not ``set``: prohibition 6 forbids
    #: iterating a set for output. Serialise with :meth:`rat_candidates_sorted`.
    rat_candidates: frozenset[Rationality]

    tier: Tier
    referent: Referent
    abstain_reason: AbstainTrigger | None

    #: Tier C only — the agreement target whose rationality was inherited.
    head_token: str | None

    #: Provenance travels with the data, not only with a source hash. ADR 007
    #: keeps model loading outside the freeze, so these pin model identity.
    toolkit_version: str
    db_version: str

    def rat_candidates_sorted(self) -> tuple[str, ...]:
        """Deterministic serialisation of :attr:`rat_candidates`.

        Ordered by ``_RAT_ORDER`` (r, i, n), never by set iteration — two cues
        built from the same candidates in different insertion order must
        serialise identically (CLAUDE.md prohibition 6).
        """
        return tuple(
            r for r in _RAT_ORDER if Rationality(r) in self.rat_candidates
        )

    def __post_init__(self) -> None:
        # Abstention must be self-describing: adjudication is stratified by
        # trigger (spec §8.3), so an abstained cue with no trigger cannot be
        # routed and would silently vanish from the strata.
        if self.referent is Referent.ABSTAIN and self.abstain_reason is None:
            raise ValueError(
                f"cue {self.cue_id!r}: referent=ABSTAIN requires an "
                f"abstain_reason (spec §6)"
            )
        if self.referent is not Referent.ABSTAIN and self.abstain_reason is not None:
            raise ValueError(
                f"cue {self.cue_id!r}: abstain_reason={self.abstain_reason} set "
                f"on a non-abstained cue (referent={self.referent})"
            )
        # head_token is Tier C only (architecture §4.5).
        if self.head_token is not None and self.tier is not Tier.C:
            raise ValueError(
                f"cue {self.cue_id!r}: head_token is Tier C only, got tier="
                f"{self.tier}"
            )
