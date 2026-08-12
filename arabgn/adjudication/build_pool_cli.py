"""Build the annotation pool from ArabJobs. I/O — not frozen.

Usage::

    uv run python -m arabgn.adjudication.build_pool_cli \\
        --corpus ArabJobs/ArabJobs.csv --out build/pool \\
        --n 200 --seed 20260812 --theta-high 0.495 --theta-low 0.285

θ has **no default**. It is calibrated at the Phase 4 gate against the very gold
set this pool exists to build, so any default would be a fabricated
pre-registration parameter. ``docs/theta-sweep.md`` §3 reports the most robust
configuration over the nine fixtures — (0.495, 0.285), six grid steps of slack in
every direction — which is the sensible provisional value to pass, and is
recorded in every artifact as provisional.

Output goes to ``build/`` by convention because it contains ArabJobs text and
redistribution permission is outstanding (proposal §1.8 risk 3). ``build/`` is
gitignored; do not move these files into the repository.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arabgn.adjudication.pool import build_pool, write_pool
from arabgn.analysis.sampling import DEFAULT_ABSTAIN_OVERSAMPLE
from arabgn.analysis.thresholds import ThresholdConfig
from arabgn.corpus.arabjobs import ArabJobsLoader, load_arabjobs
from arabgn.tagger.analyzer import load_disambiguator


def _report(result, corpus_checksum: str, out_dir: Path) -> str:
    counts = result.counts
    lines = [
        "# Annotation pool — coverage report",
        "",
        "**Provisional.** Drawn under an uncalibrated θ and covering Tiers A and "
        "B only. Not a C1 result.",
        "",
        f"- θ_high = {result.theta.theta_high}, θ_low = {result.theta.theta_low} "
        f"(provisional; calibrated at the Phase 4 gate)",
        f"- seed = {result.seed}",
        f"- abstention over-sampling = ×{result.plan.abstain_oversample} "
        f"(architecture §8.1; pre-registered)",
        "",
        "**The sample is deliberately not representative of the corpus.** "
        "Abstentions are drawn above their base rate, so any prevalence figure "
        "computed from annotated cues must be re-weighted using the per-stratum "
        "draw counts recorded on the sampling plan.",
        "",
        "## Corpus",
        "",
        "| | |",
        "|---|---|",
        f"| documents loaded | {counts.docs} |",
        f"| corpus checksum | `{corpus_checksum[:16]}…` |",
        f"| tokens analysed | {counts.tokens} |",
        "",
        "## Cues",
        "",
        "| | count |",
        "|---|---|",
        f"| detected | {counts.cues_detected} |",
        f"| classified — Tiers A, B and C | {counts.cues_classified} |",
        f"| **verbs skipped at the agreement step (D8)** | "
        f"**{counts.cues_verb_branch_skipped}** |",
        f"| span crossed a segment boundary, skipped | {counts.cues_no_segment} |",
        f"| collapsed — advertisement repeated verbatim | "
        f"{counts.cues_duplicate_documents} |",
        f"| form_gen absent, fell back to gen | {counts.cues_form_gen_absent} |",
        "",
        "## Distribution over Tier A/B cues",
        "",
        f"- by POS: {counts.by_pos}",
        f"- by tier: {counts.by_tier}",
        f"- by referent: {counts.by_referent}",
        f"- by abstain trigger: {counts.by_trigger}",
        "",
        "## Sample",
        "",
        f"- requested {result.plan.requested}, drawn {len(result.plan.cue_ids)}",
        f"- strata fields: {list(result.plan.strata_fields)}",
        f"- non-empty strata: {sum(1 for v in result.plan.per_stratum.values() if v)}",
        f"- **strata short of quota: {len(result.plan.shortfalls)}**",
        "",
    ]
    if result.plan.shortfalls:
        lines += [
            "Shortfalls are strata smaller than their quota. They are listed "
            "because a silently shortfallen stratum reads as covered when it is "
            "not.",
            "",
            "| stratum | quota | available |",
            "|---|---|---|",
        ]
        for key, (quota, available) in sorted(
            result.plan.shortfalls.items(), key=lambda kv: str(kv[0])
        )[:40]:
            lines.append(f"| `{key}` | {quota} | {available} |")
        if len(result.plan.shortfalls) > 40:
            lines.append(f"| … {len(result.plan.shortfalls) - 40} more | | |")
        lines.append("")

    lines += [
        "## Known gaps in this pool",
        "",
        "1. **Seniority is `unspecified` for every document.** ArabJobs ships no "
        "seniority column, so the axis architecture §8.5 requires cannot be "
        "reported and contributes nothing to stratification (register D16).",
        "2. **No cue can carry `referent = applicant`.** D7 is open, so the role "
        "test is indeterminate and every rational cue abstains under AB6.",
        "3. **Tier C's verb branch is absent** (register D8, pro-drop) — the "
        "branch carrying `تخرجت` and `عملت`. The adjective branch resolves. A "
        "verb whose candidates disagree on gender still enters the pool under "
        "AB4, since that decision needs no pro-drop default.",
        f"4. **θ is provisional**, so stratum membership will shift if "
        f"calibration moves it. Annotator labels stay valid; the draw would need "
        f"repeating.",
        "",
        f"Files: `{out_dir}/items.jsonl` (annotator-facing), "
        f"`{out_dir}/manifest.jsonl` (**must not** be opened by an annotator).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="ArabJobs/ArabJobs.csv")
    parser.add_argument("--out", default="build/pool")
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--theta-high", type=float, required=True)
    parser.add_argument("--theta-low", type=float, required=True)
    parser.add_argument(
        "--abstain-oversample",
        type=float,
        default=DEFAULT_ABSTAIN_OVERSAMPLE,
        help=(
            "Multiplier on abstained strata (architecture §8.1). 1.0 restores "
            "proportional sampling. Pre-registered parameter."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Tag only the first N documents (by doc_id). For smoke runs.",
    )
    args = parser.parse_args(argv)

    records = load_arabjobs(args.corpus)
    corpus_checksum = ArabJobsLoader(args.corpus).checksum()
    if args.limit:
        records = records[: args.limit]
    print(f"loaded {len(records)} documents", file=sys.stderr)

    disambiguator = load_disambiguator()

    def progress(done: int, total: int, cues: int) -> None:
        if done % 200 == 0 or done == total:
            print(f"  {done}/{total} docs, {cues} cues", file=sys.stderr)

    result = build_pool(
        records,
        disambiguator,
        n=args.n,
        seed=args.seed,
        config=ThresholdConfig(
            theta_high=args.theta_high, theta_low=args.theta_low
        ),
        abstain_oversample=args.abstain_oversample,
        progress=progress,
    )

    out_dir = Path(args.out)
    paths = write_pool(result, out_dir)
    report = _report(result, corpus_checksum, out_dir)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    print(report)
    print(f"wrote {paths['items']} and {paths['manifest']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
