"""Rationality resolution by probability mass, and the θ separability gate.

Implements ``docs/linguistic-spec.md`` §4.2 and §4.2.1, decided in ADR 001
(register D1). Pure — enters the freeze manifest.

The rule
--------
Compute the probability mass of each rationality value across candidate analyses,
then::

    mass(r) >= θ_high and mass(i) < θ_low  ->  rational
    mass(i) >= θ_high and mass(r) < θ_low  ->  irrational
    otherwise                              ->  ABSTAIN (AB1)

**θ_high and θ_low have no defaults and are never chosen here.** They are
calibrated once against the gold set at the Phase 4 gate, then frozen and declared
in the pre-registration. :class:`ThresholdConfig` requires both explicitly so a
caller cannot fall back to a guess.

Why not the alternatives
------------------------
Both threshold-free formulations were tested and both fail on *settled* fixtures,
in opposite directions (ADR 001):

* raw candidate-set membership abstains on A01 ``المرشحة`` and A02 ``مهندس`` —
  the two cleanest positives;
* rank-based (top-1 vs top-2) resolves B01 ``حاصلة`` to irrational, the exact
  error AB1 exists to catch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, NamedTuple

from arabgn.contracts import Rationality

__all__ = [
    "ThresholdConfig",
    "RationalityOutcome",
    "resolve_rationality",
    "SeparabilityCase",
    "SeparabilityReport",
    "sweep_feasible_region",
]


class RationalityOutcome(NamedTuple):
    """Result of applying §4.2. ``value`` is ``None`` when the cue abstains."""

    value: Rationality | None
    abstains: bool


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    """θ_high / θ_low. Both required — there is no default and no fallback.

    Raises if either is missing or out of range, rather than substituting a
    plausible number. A silently-defaulted θ would be a pre-registered constant
    nobody chose.
    """

    theta_high: float
    theta_low: float

    def __post_init__(self) -> None:
        for name, value in (
            ("theta_high", self.theta_high),
            ("theta_low", self.theta_low),
        ):
            if value is None:
                raise ValueError(
                    f"{name} is required (spec §4.2). It is calibrated against "
                    f"the gold set at the Phase 4 gate and frozen; it must not "
                    f"be defaulted."
                )
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}={value!r} is not a probability mass")
        if self.theta_low > self.theta_high:
            raise ValueError(
                f"theta_low ({self.theta_low}) > theta_high ({self.theta_high}); "
                f"the rule requires a dominant mass above theta_high and a "
                f"competing mass below theta_low"
            )


def resolve_rationality(
    mass: Mapping[Rationality, float], config: ThresholdConfig
) -> RationalityOutcome:
    """Apply the §4.2 probability-mass rule.

    Parameters
    ----------
    mass:
        Probability mass per rationality value, from the candidate analyses'
        log-probabilities. Missing keys are treated as zero.
    config:
        Calibrated thresholds. Never defaulted.

    Examples
    --------
    Masses measured 12 Aug 2026 and recorded in ADR 001.

    ``خبرة`` — i = 0.904, resolves irrational (fixture A04):

    >>> cfg = ThresholdConfig(theta_high=0.70, theta_low=0.30)
    >>> resolve_rationality({Rationality.I: 0.904, Rationality.R: 0.096}, cfg).value
    <Rationality.I: 'i'>

    ``حاصلة`` — i = 0.676, r = 0.324, abstains (fixture B01):

    >>> resolve_rationality({Rationality.I: 0.676, Rationality.R: 0.324}, cfg).abstains
    True
    """
    mass_r = mass.get(Rationality.R, 0.0)
    mass_i = mass.get(Rationality.I, 0.0)

    if mass_r >= config.theta_high and mass_i < config.theta_low:
        return RationalityOutcome(Rationality.R, abstains=False)
    if mass_i >= config.theta_high and mass_r < config.theta_low:
        return RationalityOutcome(Rationality.I, abstains=False)
    return RationalityOutcome(None, abstains=True)


# ---------------------------------------------------------------------------
# The separability gate — spec §4.2.1, ADR 001
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeparabilityCase:
    """One gold-labelled cue: its measured masses and the outcome required.

    ``expected`` is ``Rationality.R``, ``Rationality.I``, or ``None`` meaning the
    cue **must** abstain.
    """

    label: str
    mass_r: float
    mass_i: float
    expected: Rationality | None


@dataclass(frozen=True, slots=True)
class SeparabilityReport:
    """Outcome of a joint sweep.

    ``feasible`` is every (θ_high, θ_low) on the grid satisfying **all** cases.
    Empty means no θ exists and AB1 must be redesigned, not tuned.
    """

    feasible: tuple[tuple[float, float], ...]
    grid_size: int
    failures_by_case: Mapping[str, int]

    @property
    def separable(self) -> bool:
        return bool(self.feasible)

    @property
    def theta_high_range(self) -> tuple[float, float] | None:
        if not self.feasible:
            return None
        highs = [h for h, _ in self.feasible]
        return (min(highs), max(highs))

    @property
    def theta_low_range(self) -> tuple[float, float] | None:
        if not self.feasible:
            return None
        lows = [low for _, low in self.feasible]
        return (min(lows), max(lows))


def sweep_feasible_region(
    cases: Iterable[SeparabilityCase],
    *,
    grid: Iterable[float],
) -> SeparabilityReport:
    """Sweep θ_high and θ_low **jointly** and return the feasible region.

    Sweeping jointly is not an optimisation — it is required for correctness.
    ADR 001 shows the constraint that forces `حاصلة` to abstain is a
    **disjunction**::

        (θ_high > 0.676)  OR  (θ_low <= 0.324)

    so two independent routes to a feasible configuration exist. A sweep over
    θ_high alone would report "no feasible θ exists" while a valid θ_low region
    sat unexamined.

    Deterministic: the grid is consumed in sorted order and the result is a
    sorted tuple, never a set (prohibition 6).
    """
    cases = tuple(cases)
    grid = tuple(sorted(set(grid)))

    feasible: list[tuple[float, float]] = []
    failures: dict[str, int] = {case.label: 0 for case in cases}
    considered = 0

    for theta_high in grid:
        for theta_low in grid:
            if theta_low > theta_high:
                continue
            considered += 1
            config = ThresholdConfig(theta_high=theta_high, theta_low=theta_low)
            ok = True
            for case in cases:
                outcome = resolve_rationality(
                    {Rationality.R: case.mass_r, Rationality.I: case.mass_i},
                    config,
                )
                actual = None if outcome.abstains else outcome.value
                if actual is not case.expected:
                    failures[case.label] += 1
                    ok = False
            if ok:
                feasible.append((theta_high, theta_low))

    return SeparabilityReport(
        feasible=tuple(feasible),
        grid_size=considered,
        failures_by_case=dict(sorted(failures.items())),
    )
