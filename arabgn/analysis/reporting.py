"""Guarded reporting layer. Architecture §7.4, CLAUDE.md prohibition 4.

Pure — enters the freeze manifest.

Four hard constraints, each enforced here rather than left to a careful author:

1. **Refuses to emit the phrase "no bias" in any output.** "It is not a bug. No
   test can license the claim, so no output may make it."
2. **Every interval reported with its clustering structure named.**
3. **Equivalence claims blocked unless the achieved margin is met.**
4. **Any cell with achieved power below the pre-registered floor is labelled
   inconclusive, not null.**

The point of putting these in code is that they hold when someone is tired, in a
hurry, or responding to a reviewer who wants a cleaner headline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from arabgn.analysis.inference import TOSTResult
from arabgn.analysis.variance import ClusterRobustResult

__all__ = [
    "ForbiddenClaim",
    "assert_no_forbidden_claim",
    "format_interval",
    "CellVerdict",
    "verdict_for_cell",
    "render_report",
]


class ForbiddenClaim(Exception):
    """Raised when output would make a claim no test can license."""


#: Phrasings of the claim prohibition 4 forbids. Matched case-insensitively with
#: flexible whitespace and optional hyphenation, because the constraint is on the
#: *claim*, not on one exact string — "no  bias", "No-Bias" and "NO BIAS" are all
#: the same assertion.
_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bno[\s\-_]+bias\b", '"no bias"'),
    (r"\bbias[\s\-_]+free\b", '"bias free"'),
    (r"\bunbiased\b", '"unbiased"'),
    (r"\bno[\s\-_]+evidence[\s\-_]+of[\s\-_]+bias\b", '"no evidence of bias"'),
    (r"\bfair\b(?![\s\-]*(ness|ly))", '"fair" as a verdict'),
)


def assert_no_forbidden_claim(text: str) -> None:
    """Raise if ``text`` makes a claim no test can license.

    ``"no evidence of bias"`` is included deliberately. It reads as a hedge, but
    in a paper reporting a null it functions as the same claim — and the whole
    C3 argument is that these designs are underpowered to license it.

    The intended replacement is the language architecture §7.4 requires:
    *inconclusive*, with the achieved power stated.
    """
    for pattern, description in _FORBIDDEN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise ForbiddenClaim(
                f"output contains {description}, which no test in this design "
                f"can license (architecture §7.4, CLAUDE.md prohibition 4). "
                f"If the cell is underpowered, the word is 'inconclusive' and "
                f"the achieved power must be stated."
            )


def format_interval(result: ClusterRobustResult, *, z: float = 1.96) -> str:
    """Render an interval **with its clustering named**. Architecture §7.4.

    There is no code path that formats an interval without the clustering, which
    is the point: an interval whose clustering is unstated is not reportable, and
    making that structural means it cannot be forgotten under deadline.
    """
    low, high = result.confidence_interval(z)
    return (
        f"{result.mean_difference:+.4f} "
        f"[{low:+.4f}, {high:+.4f}] "
        f"(SE {result.se:.4f}; {result.clustering}; "
        f"n={result.n_observations} over {result.n_ad_clusters} ads x "
        f"{result.n_pair_clusters} pairs)"
    )


@dataclass(frozen=True, slots=True)
class CellVerdict:
    """The verdict for one cell, with the reasoning that produced it."""

    label: str
    verdict: str
    achieved_power: float
    power_floor: float
    reason: str

    @property
    def is_inconclusive(self) -> bool:
        return self.verdict == "inconclusive"


def verdict_for_cell(
    label: str,
    *,
    achieved_power: float,
    power_floor: float,
    tost_result: TOSTResult | None = None,
    difference_significant: bool = False,
) -> CellVerdict:
    """Decide a cell's verdict under architecture §7.4's constraints.

    Order matters, and it is the order §7.4 states:

    1. **Power first.** Below the pre-registered floor the cell is
       ``inconclusive`` — *not* null, and not equivalent — whatever the p-values
       say. An underpowered null is uninformative, and labelling it null is the
       error the paper exists to document.
    2. **Equivalence only via TOST**, and only if the achieved margin is met.
    3. Otherwise report the direction, or ``inconclusive``.

    There is no code path returning "no bias", "null" or "unbiased".
    """
    if not 0.0 <= achieved_power <= 1.0:
        raise ValueError(f"achieved_power={achieved_power} not in [0, 1]")

    if achieved_power < power_floor:
        return CellVerdict(
            label=label,
            verdict="inconclusive",
            achieved_power=achieved_power,
            power_floor=power_floor,
            reason=(
                f"achieved power {achieved_power:.3f} is below the "
                f"pre-registered floor {power_floor:.3f}; this cell is "
                f"inconclusive, not null (architecture §7.4)"
            ),
        )

    if tost_result is not None and tost_result.equivalent:
        return CellVerdict(
            label=label,
            verdict="equivalent-within-margin",
            achieved_power=achieved_power,
            power_floor=power_floor,
            reason=(
                f"TOST p={tost_result.p_value:.5f} <= alpha "
                f"{tost_result.alpha} against margin ±{tost_result.margin}"
            ),
        )

    if difference_significant:
        return CellVerdict(
            label=label,
            verdict="difference-detected",
            achieved_power=achieved_power,
            power_floor=power_floor,
            reason="interval excludes zero at the declared alpha",
        )

    return CellVerdict(
        label=label,
        verdict="inconclusive",
        achieved_power=achieved_power,
        power_floor=power_floor,
        reason=(
            "powered, but neither a difference nor equivalence was "
            "demonstrated; a non-significant difference does not license an "
            "equivalence claim"
        ),
    )


def render_report(
    intervals: Mapping[str, ClusterRobustResult],
    verdicts: Sequence[CellVerdict],
    *,
    abstention_rate: float | None = None,
) -> str:
    """Render a report, then check it against every guard before returning it.

    The output is validated by :func:`assert_no_forbidden_claim` on the way out,
    so a forbidden phrase introduced by a caller-supplied label is caught too —
    the guard applies to the *rendered text*, not just to this module's own
    strings.

    ``abstention_rate`` is required whenever abstentions exist: prohibition 3
    says any metric taking abstentions must report the rate alongside.
    """
    lines = ["# Results", ""]

    lines.append("## Intervals")
    for label in sorted(intervals):
        lines.append(f"- **{label}**: {format_interval(intervals[label])}")
    lines.append("")

    lines.append("## Cell verdicts")
    for verdict in verdicts:
        lines.append(
            f"- **{verdict.label}**: {verdict.verdict} "
            f"(power {verdict.achieved_power:.3f} vs floor "
            f"{verdict.power_floor:.3f}) — {verdict.reason}"
        )
    lines.append("")

    if abstention_rate is not None:
        lines.append(
            f"## Abstentions\n\nAbstention rate: {abstention_rate:.4f}. "
            f"Abstained cues are reported as their own category and are never "
            f"dropped from a metric or assigned to a class "
            f"(CLAUDE.md prohibition 3)."
        )
        lines.append("")

    report = "\n".join(lines)
    assert_no_forbidden_claim(report)
    return report
