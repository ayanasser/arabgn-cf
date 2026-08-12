"""Build the blind annotation pool. Spec §8.2, §8.3. I/O — not frozen (ADR 007).

Turns the corpus into two files:

``items.jsonl``
    What annotators open. Blind by construction — built through
    :func:`arabgn.adjudication.items.blind`, which drops every field the tagger
    decided (spec §8.2).

``manifest.jsonl``
    The ``item_id -> cue_id`` join plus the tagger's prediction, needed to score
    precision after annotation. **This file must never be opened by an
    annotator.** Keeping it separate is what makes the leak require a deliberate
    join rather than a careless glance.

Scope: Tiers A, B, and Tier C's adjective branch
------------------------------------------------
**Verbs are counted and skipped** — the subject may be pro-dropped and the
default by document type is register D8, unsettled. That is the branch carrying
``تخرجت`` and ``عملت``, the markings the paper is centrally about, so the report
states the number rather than letting the pool read as complete.

Adjectives resolve. Tier C inherits rationality from the agreement target, and
the role test governs *rational* targets only (spec §5.1) — so ``خبرة واسعة``
resolves to ``non_applicant`` with no author decision involved, and that is the
common case in real advertisements.

The agreement search is bounded to the cue's **segment**. ``punc`` is skippable
when looking back for a head, so an unbounded search would let a sentence-initial
adjective attach to the previous sentence's noun. Tokens are grouped by host
segment and the resolver is handed only its own segment's, which makes the bound
structural rather than a rule it has to respect.

No cue in this pool can carry ``referent = applicant``
------------------------------------------------------
D7 is open, so the role test is indeterminate for every rational cue — in Tier A
directly, and in Tier C whenever the agreement target is rational. All of them
abstain under AB6 (spec §5.1). That is not a defect in this module: it is what an
unresolved D7 *means*, made visible. The annotation is still worth doing — the
human labels are what D7 needs — but nobody should read the resulting label
distribution as the tagger's output.

θ is provisional
----------------
``θ_high`` / ``θ_low`` are calibrated against the gold set at the Phase 4 gate,
and this pool exists in order to build that gold set. Every artifact written here
therefore records the provisional θ it was drawn under and says plainly that it is
not the pre-registered value. If θ later moves, the drawn *labels* stay valid —
annotators never saw θ — but stratum membership shifts, so the sample would need
redrawing to remain proportional.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from arabgn.adjudication.items import blind
from arabgn.analysis.agreement_target import (
    TargetCandidate,
    VerbBranchNotImplemented,
)
from arabgn.analysis.cues import CandidateAnalysis, selected_analysis
from arabgn.analysis.sampling import (
    DEFAULT_ABSTAIN_OVERSAMPLE,
    SamplingPlan,
    stratified_sample,
)
from arabgn.analysis.segment import segment, segment_for_span
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.analysis.tiers import classify
from arabgn.contracts import (
    DocRecord,
    DocType,
    Gender,
    Rationality,
    TaggedCue,
)

__all__ = ["PoolCounts", "PoolResult", "extract_cues", "build_pool", "write_pool"]

#: Rationality values the contract models. CAMeL also emits ``na``, which is not
#: a rationality reading and is dropped rather than coerced into one.
_RAT_VALUES = frozenset({"r", "i", "n"})


@dataclass(frozen=True, slots=True)
class PoolCounts:
    """Everything the build saw. Reported in full — prohibition 3 in spirit:
    a category that is inconvenient is still a category."""

    docs: int
    tokens: int
    cues_detected: int
    #: Cues that reached a classification. Tiers A, B and C — the name no longer
    #: says "tier_ab", because Tier C's adjective branch now resolves.
    cues_classified: int
    #: Verbs dropped at the agreement step, blocked on register D8 (pro-drop).
    #: **Not all verbs**: one whose candidates disagree on gender abstains under
    #: AB4 before the agreement step is reached, and that decision needs no
    #: pro-drop default, so it is kept.
    cues_verb_branch_skipped: int
    cues_no_segment: int
    cues_form_gen_absent: int
    #: Cues collapsed because ArabJobs repeats an advertisement verbatim and
    #: ``doc_id`` is a content hash. Identical text, identical offsets, identical
    #: cue — but the count matters to §8.5's postings-based denominator.
    cues_duplicate_documents: int
    by_pos: Mapping[str, int]
    by_tier: Mapping[str, int]
    by_referent: Mapping[str, int]
    by_trigger: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class PoolResult:
    cues: tuple[TaggedCue, ...]
    plan: SamplingPlan
    #: ``item_id -> cue_id``, in presentation order.
    item_ids: tuple[tuple[str, str], ...]
    counts: PoolCounts
    theta: ThresholdConfig
    seed: int
    #: ``cue_id -> DocType``. Carried explicitly because ``TaggedCue`` holds
    #: ``doc_id`` and not ``doc_type`` (see :func:`blind`), and spec §8.2 permits
    #: — and Tier C pro-drop makes meaningful — showing the type to an annotator.
    doc_types: Mapping[str, DocType]


def _rat_candidates(candidates: Sequence[CandidateAnalysis]) -> frozenset[Rationality]:
    return frozenset(
        Rationality(c.rat) for c in candidates if c.rat in _RAT_VALUES
    )


def extract_cues(
    record: DocRecord,
    analysed,
    config: ThresholdConfig,
    *,
    toolkit_version: str,
    db_version: str,
) -> tuple[list[TaggedCue], dict[str, int]]:
    """Tag one document. Returns its Tier A/B cues and a count of what was skipped.

    ``analysed`` is the disambiguator's output for the **whole document**, not for
    a segment — see :mod:`arabgn.analysis.segment` for why the two are separated.
    """
    segments = segment(record.text_norm)
    cues: list[TaggedCue] = []
    skipped = {"verb_branch": 0, "no_segment": 0, "form_gen_absent": 0}

    # Tier C searches backwards for an agreement target, and `punc` is skippable,
    # so an unbounded search would let a sentence-initial adjective attach to the
    # last noun of the *previous* sentence. Grouping tokens by host segment bounds
    # the search structurally: the resolver cannot reach past what it is handed.
    #
    # This makes segmentation load-bearing for a measurement, not only for
    # display — see the note in `arabgn.analysis.segment` and register D15.
    by_segment: dict[int, list] = defaultdict(list)
    position: dict[int, tuple[int, int]] = {}
    for token in analysed:
        host = segment_for_span(segments, token.char_start, token.char_end)
        if host is None:
            continue
        index = segments.index(host)
        position[id(token)] = (index, len(by_segment[index]))
        by_segment[index].append(token)

    def targets_for(segment_index: int) -> tuple[TargetCandidate, ...]:
        return tuple(
            TargetCandidate(
                index=offset,
                token=member.token,
                pos=member.top_pos,
                gen=(
                    member.gender().value
                    if member.gender() is not None
                    else None
                ),
                candidates=member.candidates,
            )
            for offset, member in enumerate(by_segment[segment_index])
        )

    for token in analysed:
        if not token.is_cue():
            continue

        pos = token.top_pos
        selected = selected_analysis(token.candidates)
        if selected is None:  # not a cue; is_cue() already implies otherwise
            continue

        host = segment_for_span(segments, token.char_start, token.char_end)
        if host is None:
            skipped["no_segment"] += 1
            continue

        # `form_gen` is typed non-nullable on TaggedCue, but CAMeL does not always
        # supply one. Falling back to `gen` changes no decision — AB5 already
        # declines to fire unless *both* are real genders — but it does record a
        # value the analysis did not assert, so every instance is counted and
        # reported. If this count is large, `form_gen` should become nullable like
        # `morph_class` did (ADR 002); that is an author call, not one to make by
        # writing a default.
        form_gen = selected.form_gen
        if form_gen not in ("m", "f"):
            skipped["form_gen_absent"] += 1
            form_gen = selected.gen

        segment_index, offset = position[id(token)]
        try:
            classification = classify(
                token.token,
                pos,
                token.candidates,
                config,
                gen=selected.gen,
                form_gen=selected.form_gen,
                # D7 is open. `None` is "indeterminate" -> AB6, never a default to
                # applicant (spec §5.1). Applies to Tier A and to Tier C cues
                # whose agreement target is rational.
                role_test_passes=None,
                cue_index=offset,
                tokens=targets_for(segment_index),
            )
        except VerbBranchNotImplemented:
            # Verbs only. The subject may be pro-dropped and the default by
            # document type is register D8 — the branch carrying تخرجت / عملت,
            # which is what the paper is centrally about.
            skipped["verb_branch"] += 1
            continue

        cues.append(
            TaggedCue(
                # The id keeps the document offset, so a cue stays locatable in
                # the source even though the span below does not index it.
                cue_id=f"{record.doc_id}:{token.char_start}",
                doc_id=record.doc_id,
                token=token.token,
                # Rebased onto `sentence_context`, which is the convention the
                # contract requires: `blind()` copies this span straight into
                # `AnnotationItem`, whose `cue` property slices `sentence`. A
                # document-relative span would highlight the wrong word for every
                # cue outside the first sentence — silently, since the offsets
                # stay in range and still produce a plausible Arabic substring.
                char_span=(
                    token.char_start - host.start,
                    token.char_end - host.start,
                ),
                sentence_context=host.text,
                pos=pos,
                # Raw stemcat: the stemcat -> class table is unauthored, so the
                # mapped class stays absent rather than guessed (ADR 002).
                morph_class=selected.stemcat,
                gen=Gender(selected.gen),
                form_gen=Gender(form_gen),
                rat_candidates=_rat_candidates(token.candidates),
                tier=classification.tier,
                referent=classification.referent,
                abstain_reason=classification.abstain_reason,
                head_token=classification.head_token,
                toolkit_version=toolkit_version,
                db_version=db_version,
            )
        )

    return cues, skipped


def _presentation_order(cue_ids: Sequence[str], seed: int) -> tuple[str, ...]:
    """Shuffle drawn cues for display.

    The sampler returns cue ids sorted, and draws strata in sorted key order, so
    unshuffled presentation would group a stratum together — an annotator would
    meet twenty ``مطلوبة`` cues in a row and calibrate to them. The shuffle seed is
    derived from the run seed by hashing rather than by arithmetic, so
    presentation order carries no relationship to draw order, and is derived with
    SHA-256 rather than ``hash()`` because the latter is salted per process
    (prohibition 6).
    """
    digest = hashlib.sha256(f"presentation:{seed}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    shuffled = list(cue_ids)
    rng.shuffle(shuffled)
    return tuple(shuffled)


def build_pool(
    records: Sequence[DocRecord],
    disambiguator,
    *,
    n: int,
    seed: int,
    config: ThresholdConfig,
    abstain_oversample: float = DEFAULT_ABSTAIN_OVERSAMPLE,
    progress=None,
) -> PoolResult:
    """Tag ``records``, stratify, and draw ``n`` cues for annotation."""
    all_cues: list[TaggedCue] = []
    meta: dict[str, DocRecord] = {}
    totals = {"verb_branch": 0, "no_segment": 0, "form_gen_absent": 0}
    tokens = 0
    # `doc_id` is a content hash, so the 849 advertisements ArabJobs repeats
    # verbatim share one. Their cues therefore share a `cue_id` and would collide
    # in `meta` — silently, since the colliding cues are genuinely identical.
    # Collapsing is right for annotation (nobody should label the same sentence
    # twice) but the count has to surface: §8.5's denominator is postings, so
    # whoever computes prevalence needs to know how many were folded away.
    duplicate_cue_ids = 0

    by_pos: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_referent: dict[str, int] = {}
    by_trigger: dict[str, int] = {}

    for index, record in enumerate(records):
        analysed = disambiguator.analyse(record.text_norm)
        tokens += len(analysed)
        cues, skipped = extract_cues(
            record,
            analysed,
            config,
            toolkit_version=disambiguator.toolkit_version,
            db_version=disambiguator.db_version,
        )
        for key, value in skipped.items():
            totals[key] += value
        for cue in cues:
            if cue.cue_id in meta:
                duplicate_cue_ids += 1
                continue
            meta[cue.cue_id] = record
            by_pos[cue.pos] = by_pos.get(cue.pos, 0) + 1
            by_tier[cue.tier.value] = by_tier.get(cue.tier.value, 0) + 1
            by_referent[cue.referent.value] = by_referent.get(cue.referent.value, 0) + 1
            if cue.abstain_reason is not None:
                key = cue.abstain_reason.value
                by_trigger[key] = by_trigger.get(key, 0) + 1
            all_cues.append(cue)
        if progress is not None:
            progress(index + 1, len(records), len(all_cues))

    rows = [
        {
            "cue_id": cue.cue_id,
            "token": cue.token,
            "pos": cue.pos,
            "tier": cue.tier.value,
            "abstain_reason": (
                cue.abstain_reason.value if cue.abstain_reason else None
            ),
            "country": meta[cue.cue_id].country.value,
            "seniority": meta[cue.cue_id].seniority.value,
        }
        for cue in all_cues
    ]

    plan = stratified_sample(
        rows, n=n, seed=seed, abstain_oversample=abstain_oversample
    )
    ordered = _presentation_order(plan.cue_ids, seed)
    item_ids = tuple(
        (f"IT{position:04d}", cue_id) for position, cue_id in enumerate(ordered, 1)
    )

    counts = PoolCounts(
        docs=len(records),
        tokens=tokens,
        cues_detected=(
            len(all_cues)
            + totals["verb_branch"]
            + totals["no_segment"]
            + duplicate_cue_ids
        ),
        cues_classified=len(all_cues),
        cues_verb_branch_skipped=totals["verb_branch"],
        cues_no_segment=totals["no_segment"],
        cues_form_gen_absent=totals["form_gen_absent"],
        cues_duplicate_documents=duplicate_cue_ids,
        by_pos=dict(sorted(by_pos.items())),
        by_tier=dict(sorted(by_tier.items())),
        by_referent=dict(sorted(by_referent.items())),
        by_trigger=dict(sorted(by_trigger.items())),
    )
    return PoolResult(
        cues=tuple(all_cues),
        plan=plan,
        item_ids=item_ids,
        counts=counts,
        theta=config,
        seed=seed,
        doc_types={
            cue_id: record.doc_type for cue_id, record in meta.items()
        },
    )


def write_pool(result: PoolResult, out_dir: str | Path) -> dict[str, Path]:
    """Write ``items.jsonl`` and ``manifest.jsonl``.

    The two files are written separately and named for their audience. ``items``
    is passed through :func:`blind`, so no tagger field can reach it even if this
    function is later edited carelessly — the leak would have to be added to
    :class:`AnnotationItem` itself, which the test suite forbids.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {cue.cue_id: cue for cue in result.cues}

    items_path = out_dir / "items.jsonl"
    with items_path.open("w", encoding="utf-8") as handle:
        for item_id, cue_id in result.item_ids:
            cue = by_id[cue_id]
            item = blind(
                cue, item_id=item_id, doc_type=result.doc_types[cue_id]
            )
            handle.write(
                json.dumps(
                    {
                        "item_id": item.item_id,
                        "sentence": item.sentence,
                        "cue_start": item.cue_start,
                        "cue_end": item.cue_end,
                        "doc_type": item.doc_type.value,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    manifest_path = out_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as handle:
        for item_id, cue_id in result.item_ids:
            cue = by_id[cue_id]
            handle.write(
                json.dumps(
                    {
                        "item_id": item_id,
                        "cue_id": cue.cue_id,
                        "doc_id": cue.doc_id,
                        "token": cue.token,
                        "pos": cue.pos,
                        "morph_class": cue.morph_class,
                        "gen": cue.gen.value,
                        "rat_candidates": list(cue.rat_candidates_sorted()),
                        "tier": cue.tier.value,
                        "referent": cue.referent.value,
                        "abstain_reason": (
                            cue.abstain_reason.value if cue.abstain_reason else None
                        ),
                        "toolkit_version": cue.toolkit_version,
                        "db_version": cue.db_version,
                        "theta_high": result.theta.theta_high,
                        "theta_low": result.theta.theta_low,
                        # Pre-registered, and the re-weighting factor for any
                        # prevalence figure computed from these cues.
                        "abstain_oversample": result.plan.abstain_oversample,
                        "PROVISIONAL": "theta is not the pre-registered value; "
                        "calibrated at the Phase 4 gate",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {"items": items_path, "manifest": manifest_path}
