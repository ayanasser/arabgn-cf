"""Five-register ad typology and its machine-checked invariants. Architecture §5.1.

Pure — enters the freeze manifest. Takes :class:`TaggedCue` values as **data** and
never runs the tagger (ADR 007).

| Register | Description | Invariant |
|---|---|---|
| R1 | As-found generic masculine | ≥1 applicant-referring masculine cue |
| R2 | Dual / inclusive | Both gendered forms present for each applicant cue |
| R3 | Agreement-free | Zero applicant-referring gender cues |
| R4 | Syntax-matched masculine placebo | Matches R2 in length and structure, no inclusive semantics |
| R5 | Cross-lingual English | No grammatical gender agreement |

R4 exists to separate "the model responds to inclusive framing" from "the model
responds to longer or more complex text" (§5.1). Its invariant is therefore
*relational* — it is checked against the R2 document it is a placebo for, not on
its own.

Why R3 refuses to certify in the presence of abstentions
--------------------------------------------------------
R3's invariant is "zero applicant-referring gender cues", and the naive reading —
count cues labelled ``applicant`` and check the count is zero — is **certification
theatre**. An abstained cue is one the tagger could not resolve; it may well be
applicant-referring. Counting it as "not applicant" is exactly the silent
reassignment prohibition 3 forbids, and it would let a document full of
unresolved gender marking be certified agreement-free.

So R3 requires zero applicant cues **and** zero abstentions among gendered cues.
An abstention makes the register *uncertifiable*, which is a third outcome
distinct from pass and fail, and :attr:`RegisterReport.certifiable` carries it.

This has a consequence today worth stating plainly: **while register D7 is open,
no R3 document can be certified at all.** The role test is indeterminate for every
rational cue, so they all abstain under AB6. That is the honest position — the
alternative is an R3 register certified by a tagger incapable of finding the thing
it certifies the absence of, which would be worse than having no R3 at all.
Asserted by ``test_r3_cannot_be_certified_while_cues_abstain``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from arabgn.analysis.twins import TwinToken
from arabgn.contracts import Gender, Referent, TaggedCue

__all__ = [
    "Register",
    "RegisterDocument",
    "RegisterReport",
    "check_r1",
    "check_r2",
    "check_r3",
    "check_r4",
    "check_r5",
]


class Register(str, Enum):
    """Architecture §5.1's typology.

    Defined here rather than in ``contracts.py`` because the registers are a
    property of the *generator*, not of any emitted record — no ``TaggedCue`` or
    ``DocRecord`` field carries one.
    """

    R1 = "R1"  # as-found generic masculine
    R2 = "R2"  # dual / inclusive
    R3 = "R3"  # agreement-free
    R4 = "R4"  # syntax-matched masculine placebo
    R5 = "R5"  # cross-lingual English


@dataclass(frozen=True, slots=True)
class RegisterDocument:
    """A generated advertisement, its tagged cues, and its tokens.

    ``cues`` come from the Layer 2 tagger; ``tokens`` carry POS so content words
    can be counted without re-tagging. Both are supplied by the caller.
    """

    text: str
    cues: tuple[TaggedCue, ...]
    tokens: tuple[TwinToken, ...] = ()

    @property
    def applicant_cues(self) -> tuple[TaggedCue, ...]:
        return tuple(c for c in self.cues if c.referent is Referent.APPLICANT)

    @property
    def abstained_cues(self) -> tuple[TaggedCue, ...]:
        return tuple(c for c in self.cues if c.referent is Referent.ABSTAIN)

    @property
    def content_word_count(self) -> int:
        return sum(1 for token in self.tokens if token.is_content)


@dataclass(frozen=True, slots=True)
class RegisterReport:
    """Outcome of one register's invariant.

    Three outcomes, not two. ``certifiable`` is ``False`` when abstentions leave
    the question open — distinct from a clean failure, and never collapsed into
    one (prohibition 3).
    """

    register: Register
    satisfied: bool
    certifiable: bool
    reasons: tuple[str, ...]
    #: Counts behind the verdict, reported whether or not it passed.
    counts: Mapping[str, int]

    def explain(self) -> str:
        if self.satisfied:
            return f"{self.register.value}: invariant holds"
        if not self.certifiable:
            return f"{self.register.value}: NOT CERTIFIABLE — " + "; ".join(
                self.reasons
            )
        return f"{self.register.value}: " + "; ".join(self.reasons)


def _counts(document: RegisterDocument) -> dict[str, int]:
    applicant = document.applicant_cues
    return {
        "cues": len(document.cues),
        "applicant": len(applicant),
        "applicant_masculine": sum(1 for c in applicant if c.gen is Gender.M),
        "applicant_feminine": sum(1 for c in applicant if c.gen is Gender.F),
        "abstained": len(document.abstained_cues),
    }


def check_r1(document: RegisterDocument) -> RegisterReport:
    """R1 — as-found generic masculine: ≥1 applicant-referring masculine cue.

    The register the corpus supplies unmodified. Its invariant is a floor, not a
    ceiling: an R1 advertisement may carry many masculine cues, and may also
    carry feminine ones referring to other people.
    """
    counts = _counts(document)
    reasons = []
    if counts["applicant_masculine"] < 1:
        reasons.append(
            "no applicant-referring masculine cue "
            f"({counts['applicant']} applicant cues, "
            f"{counts['abstained']} abstained)"
        )
    return RegisterReport(
        register=Register.R1,
        satisfied=not reasons,
        certifiable=True,
        reasons=tuple(reasons),
        counts=counts,
    )


def check_r2(
    document: RegisterDocument,
    *,
    declared_inclusive_pairs: frozenset[tuple[str, str]],
) -> RegisterReport:
    """R2 — dual/inclusive: both gendered forms present for each applicant cue.

    ``declared_inclusive_pairs`` are ``(masculine, feminine)`` surfaces the
    generator emitted as a pair, e.g. ``("مطلوب", "مطلوبة")``. As in
    :mod:`arabgn.analysis.twins`, the generator declares them rather than this
    module inferring them morphologically — an inferred rule would be an
    unreviewed linguistic decision entering the freeze.

    An applicant cue whose surface belongs to no declared pair is a **bare**
    gendered form, which is precisely what R2 must not contain.
    """
    counts = _counts(document)
    reasons = []

    for cue in document.applicant_cues:
        partners = [
            pair for pair in declared_inclusive_pairs if cue.token in pair
        ]
        if not partners:
            reasons.append(
                f"applicant cue {cue.token!r} is a bare gendered form — it "
                f"belongs to no declared inclusive pair"
            )
            continue
        for masculine, feminine in partners:
            counterpart = feminine if cue.token == masculine else masculine
            if counterpart not in document.text:
                reasons.append(
                    f"applicant cue {cue.token!r} is declared paired with "
                    f"{counterpart!r}, which is absent from the text"
                )

    return RegisterReport(
        register=Register.R2,
        satisfied=not reasons,
        certifiable=True,
        reasons=tuple(reasons),
        counts=counts,
    )


def check_r3(document: RegisterDocument) -> RegisterReport:
    """R3 — agreement-free: zero applicant-referring gender cues.

    Certified by the Layer 2 tagger, which is the dependency architecture §5.1
    names as a second reason to build Layer 2 first.

    **Abstentions make this uncertifiable rather than passing.** See the module
    docstring: an abstained cue may be applicant-referring, and counting it as
    "not applicant" is the silent reassignment prohibition 3 forbids.
    """
    counts = _counts(document)
    reasons = []
    certifiable = True

    if counts["abstained"]:
        certifiable = False
        tokens = sorted({c.token for c in document.abstained_cues})
        reasons.append(
            f"{counts['abstained']} cue(s) abstained, so the absence of "
            f"applicant-referring marking cannot be certified: {tokens}. "
            f"An abstention is 'unresolved', not 'not applicant' "
            f"(prohibition 3)."
        )
    if counts["applicant"]:
        reasons.append(
            f"{counts['applicant']} applicant-referring cue(s) present: "
            f"{sorted({c.token for c in document.applicant_cues})}"
        )

    return RegisterReport(
        register=Register.R3,
        satisfied=not reasons,
        certifiable=certifiable,
        reasons=tuple(reasons),
        counts=counts,
    )


def check_r4(
    placebo: RegisterDocument,
    reference: RegisterDocument,
    *,
    char_tolerance: int,
) -> RegisterReport:
    """R4 — syntax-matched masculine placebo, checked against its R2 reference.

    §5.1: R4 "exists to separate 'the model responds to inclusive framing' from
    'the model responds to longer or more complex text'." A placebo that does not
    actually match the R2 document in size cannot do that job, so the invariant is
    relational and ``reference`` is required.

    "Matches in length and structure" is operationalised as identical content-word
    count plus a character-length delta within a **declared** tolerance — the same
    two measures :mod:`arabgn.analysis.twins` uses, so R4 and the twin pairs are
    matched on comparable terms. §5.1 does not define "structure" further; that
    gap is register D19, not a decision made here.

    "No inclusive semantics" is operationalised as: no feminine applicant-referring
    cue. A masculine placebo that mentions the applicant in the feminine is not a
    placebo.
    """
    if char_tolerance < 0:
        raise ValueError(
            f"char_tolerance must be non-negative, got {char_tolerance}"
        )

    counts = _counts(placebo)
    counts["reference_content_words"] = reference.content_word_count
    counts["content_words"] = placebo.content_word_count
    char_delta = abs(len(placebo.text) - len(reference.text))
    counts["char_delta"] = char_delta

    reasons = []
    if placebo.content_word_count != reference.content_word_count:
        reasons.append(
            f"content-word count {placebo.content_word_count} does not match "
            f"the R2 reference's {reference.content_word_count}"
        )
    if char_delta > char_tolerance:
        reasons.append(
            f"character-length delta {char_delta} exceeds the declared "
            f"tolerance {char_tolerance}"
        )
    if counts["applicant_feminine"]:
        reasons.append(
            f"{counts['applicant_feminine']} feminine applicant-referring "
            f"cue(s) — a masculine placebo must carry none"
        )

    return RegisterReport(
        register=Register.R4,
        satisfied=not reasons,
        certifiable=True,
        reasons=tuple(reasons),
        counts=counts,
    )


def check_r5(document: RegisterDocument) -> RegisterReport:
    """R5 — cross-lingual English: no grammatical gender agreement.

    Operationalised as: the tagger found no gender cues at all. English carries no
    agreement morphology, so any cue at all means Arabic text leaked into the
    register — which is the failure mode worth catching, since a generated English
    advertisement may legitimately contain an Arabic proper noun that the tagger
    would then analyse.
    """
    counts = _counts(document)
    reasons = []
    if counts["cues"]:
        reasons.append(
            f"{counts['cues']} gender cue(s) detected: "
            f"{sorted({c.token for c in document.cues})} — English carries no "
            f"agreement morphology, so Arabic text has leaked in"
        )
    return RegisterReport(
        register=Register.R5,
        satisfied=not reasons,
        certifiable=True,
        reasons=tuple(reasons),
        counts=counts,
    )
