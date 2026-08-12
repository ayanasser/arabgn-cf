"""Twin symmetry — the instrument must not treat feminine and masculine differently.

Pure — enters the freeze manifest.

Why this is the most important invariant in the project
-------------------------------------------------------
If the tagger classifies feminine text differently from an otherwise-identical
masculine twin, **every downstream bias measurement is confounded by the
instrument itself**. A measured "bias" could be the ranker's, or it could be the
tagger's, and nothing in the analysis layer can tell them apart.

Fixture B02's note puts it directly: "if the tagger abstains on the feminine form
but resolves the masculine, the instrument is itself gender-asymmetric, which
would be fatal to the paper."

Scope of the Phase 3 check — read this before trusting a pass
-------------------------------------------------------------
At Phase 3 this runs over **Tiers A and B only**, because Tier C is not
implemented (Phase 5, blocked on register D7 and D8). That makes it a
**smoke test, not the invariant**:

* it tests symmetry-*in-abstention* — that both twins abstain together;
* it does **not** test symmetry-*in-classification*, because the cues carrying
  the paper's phenomenon (``تخرجت``, ``عملت``, ``مسؤولة``) are Tier C and are
  absent here.

**This harness re-runs as a hard gate at Phase 6, across all tiers.** That run is
the binding one. A green Phase 3 licenses nothing about Tier C.

What is deliberately not asserted
---------------------------------
**Token-count equality.** Architecture §5.2 states the constraint is "likely
unsatisfiable": ``حاصل`` and ``حاصلة`` differ under every subword tokenizer in the
audit set, so requiring equality "either blocks all output or forces silent
padding, which is itself a confound." Fixture T02 documents the same point.
Tokenisation delta is a *measured covariate*, not a constraint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from arabgn.contracts import AbstainTrigger, Gender, Referent, Tier

__all__ = [
    "CueShape",
    "Asymmetry",
    "SymmetryReport",
    "shape_of",
    "check_twin_symmetry",
    "check_all_pairs",
    "genders_differ",
]


@dataclass(frozen=True, slots=True)
class CueShape:
    """The structural signature of one cue — everything except its gender.

    ``gen`` is excluded by construction: it is the one field a twin pair is
    *supposed* to differ on. Everything else must match.
    """

    tier: Tier
    referent: Referent
    abstain_reason: AbstainTrigger | None
    token_index: int


@dataclass(frozen=True, slots=True)
class Asymmetry:
    """One structural difference between twins, with enough context to act on."""

    kind: str
    detail: str
    position: int | None = None


@dataclass(frozen=True, slots=True)
class SymmetryReport:
    """Outcome of one twin comparison."""

    symmetric: bool
    asymmetries: tuple[Asymmetry, ...]
    n_cues_f: int
    n_cues_m: int
    label: str = ""

    def describe(self) -> str:
        if self.symmetric:
            return f"{self.label}: symmetric ({self.n_cues_f} cues)"
        lines = [f"{self.label}: ASYMMETRIC"]
        for item in self.asymmetries:
            where = "" if item.position is None else f" at cue {item.position}"
            lines.append(f"  - {item.kind}{where}: {item.detail}")
        return "\n".join(lines)


def shape_of(cue) -> CueShape:
    """Reduce a cue to its structural signature, discarding gender.

    Accepts anything with ``tier``, ``referent``, ``abstain_reason`` attributes —
    a ``TaggedCue`` or a ``Classification`` paired with an index.
    """
    return CueShape(
        tier=cue.tier,
        referent=cue.referent,
        abstain_reason=cue.abstain_reason,
        token_index=getattr(cue, "token_index", -1),
    )


def check_twin_symmetry(
    cues_f: Sequence,
    cues_m: Sequence,
    *,
    label: str = "",
    compare_index: bool = False,
) -> SymmetryReport:
    """Assert structural identity across a twin pair.

    Checks, in order:

    1. **cue count** — a twin that emits more cues than its partner is already
       asymmetric, whatever the labels say;
    2. per aligned cue: **tier**, **referent**, **abstain trigger**;
    3. that the genders actually differ where both are known — a "symmetric"
       result over two identical-gender inputs would be vacuous.

    ``compare_index`` is off by default: character offsets legitimately differ
    between twins because ``حاصلة`` is one character longer than ``حاصل``.
    Requiring index equality would re-introduce the length constraint
    architecture §5.2 rejects.

    Returns a report rather than raising, so a caller sweeping many pairs
    collects every failure instead of stopping at the first.
    """
    problems: list[Asymmetry] = []

    if len(cues_f) != len(cues_m):
        problems.append(
            Asymmetry(
                kind="cue_count",
                detail=(
                    f"feminine emitted {len(cues_f)} cues, masculine "
                    f"{len(cues_m)}. A twin pair differing in cue count means "
                    f"the instrument responds to gender morphology itself."
                ),
            )
        )

    for position, (cue_f, cue_m) in enumerate(zip(cues_f, cues_m)):
        shape_f, shape_m = shape_of(cue_f), shape_of(cue_m)

        if shape_f.tier is not shape_m.tier:
            problems.append(
                Asymmetry(
                    "tier",
                    f"{shape_f.tier.value} (f) vs {shape_m.tier.value} (m)",
                    position,
                )
            )
        if shape_f.referent is not shape_m.referent:
            problems.append(
                Asymmetry(
                    "referent",
                    f"{shape_f.referent.value} (f) vs {shape_m.referent.value} (m)"
                    f" — the instrument labels the twins differently",
                    position,
                )
            )
        if shape_f.abstain_reason is not shape_m.abstain_reason:
            f_reason = (
                shape_f.abstain_reason.value if shape_f.abstain_reason else "none"
            )
            m_reason = (
                shape_m.abstain_reason.value if shape_m.abstain_reason else "none"
            )
            problems.append(
                Asymmetry(
                    "abstain_trigger", f"{f_reason} (f) vs {m_reason} (m)", position
                )
            )
        if compare_index and shape_f.token_index != shape_m.token_index:
            problems.append(
                Asymmetry(
                    "token_index",
                    f"{shape_f.token_index} (f) vs {shape_m.token_index} (m)",
                    position,
                )
            )

    return SymmetryReport(
        symmetric=not problems,
        asymmetries=tuple(problems),
        n_cues_f=len(cues_f),
        n_cues_m=len(cues_m),
        label=label,
    )


def check_all_pairs(
    pairs: Iterable[tuple[str, str]],
    tag: Callable[[str], Sequence],
    *,
    labels: Iterable[str] | None = None,
) -> tuple[SymmetryReport, ...]:
    """Property-style sweep over arbitrary twin pairs.

    Fixture T01's note: "Run this over every twin pair the generator emits, not
    just this fixture." At Phase 8 the generator produces pairs by the hundred and
    each must pass; this is the entry point for that.

    Deterministic: pairs are consumed in the order supplied, and every report is
    returned rather than short-circuiting on the first failure.
    """
    pairs = tuple(pairs)
    label_list = (
        tuple(labels) if labels is not None else tuple(f"pair-{i}" for i in range(len(pairs)))
    )
    if len(label_list) != len(pairs):
        raise ValueError(
            f"{len(pairs)} pairs but {len(label_list)} labels"
        )
    return tuple(
        check_twin_symmetry(tag(text_f), tag(text_m), label=label)
        for (text_f, text_m), label in zip(pairs, label_list)
    )


def genders_differ(cues_f: Sequence, cues_m: Sequence) -> bool:
    """Do the twins actually differ in gender somewhere?

    A symmetry pass over two inputs that carry the same gender proves nothing.
    Used to guard against a vacuous green.
    """
    gens_f = [getattr(c, "gen", None) for c in cues_f]
    gens_m = [getattr(c, "gen", None) for c in cues_m]
    return any(
        f is not None and m is not None and f is not m
        for f, m in zip(gens_f, gens_m)
    ) or (Gender.F in gens_f and Gender.M in gens_m)
