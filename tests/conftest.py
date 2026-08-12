"""Fixture loading for the ArabGN-CF test suite.

``tests/fixtures/tagger_fixtures.yaml`` is **ground truth authored by a human**.
Never edit a fixture to make a test pass. If code disagrees with a fixture, either
the code is wrong or the fixture needs author review — raise it, do not resolve it
(CLAUDE.md, and the fixture file's own header).

The file holds four shapes, distinguished by ``assert_type`` and
``expected_cue_emitted``:

===================================  =========================================
cue-label (no ``assert_type``)       expects a label, tier, maybe an abstain id
``expected_cue_emitted: false``      negative control — no cue may be emitted
``assert_type: normalisation``       expects ``text`` -> ``expected_text_norm``
``assert_type: twin_symmetry``       expects structural identity over a pair
===================================  =========================================

REVIEW fixtures
---------------
``confidence: REVIEW`` marks an **open question, not a target**. Ten fixtures are
currently unresolved. They are skipped with a reason naming the blocking
decision, never failed and never quietly treated as binding.

Determinism
-----------
Every accessor returns a deterministically ordered tuple. Nothing here iterates a
``set`` or relies on dict insertion order to produce test order
(CLAUDE.md prohibition 6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tagger_fixtures.yaml"

#: Why each REVIEW fixture is unresolved, so a skip reason points at the
#: blocking decision rather than saying "REVIEW". Keyed by fixture id.
#: Sourced from the fixtures' own AUTHOR DECISION notes and the register.
REVIEW_BLOCKERS: dict[str, str] = {
    "B01": "spec §5.1 — role test may resolve this via the preceding مهندسة (register D7)",
    "B02": "masculine twin of B01; blocked on the same decision (register D7)",
    "C04": "attachment of ممتازة (مهارات vs تواصل) unconfirmed — head_token assertion depends on it",
    "C05": "spec §5.2 — pro-drop default by document type (register D8)",
    "C06": "spec §5.2 — pro-drop default by document type (register D8)",
    "C07": "spec §5.2 — pro-drop default by document type (register D8)",
    "E01": "spec §7.1 — framing of the مطلوبة error class; human gold label unconfirmed",
    "E02": "spec §7.2 — accept AB2 abstain, or add an applicant-lexicon pre-pass?",
    "E03": "spec §7.3 — institution-name list source (register D9)",
    "T02": "verb-agreement twin; depends on Tier C, which is Phase 5",
}


def _load() -> dict[str, Any]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


_DATA = _load()
_FIXTURES: tuple[dict[str, Any], ...] = tuple(_DATA["fixtures"])


def _by_id(fixture_id: str) -> dict[str, Any]:
    for fixture in _FIXTURES:
        if fixture["id"] == fixture_id:
            return fixture
    raise KeyError(f"no fixture with id {fixture_id!r}")


def settled(fixtures: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Only the fixtures the author has signed off as binding."""
    return tuple(f for f in fixtures if f["confidence"] == "settled")


def in_group(group: int) -> tuple[dict[str, Any], ...]:
    """All fixtures in a numbered group, in file order.

    Groups come from the ``group:`` key, added per ADR 004. They were previously
    section comments only and could not be read from the data — and could not be
    derived from the id prefix either, since groups 1 and 2 are both A-prefixed.
    """
    return tuple(f for f in _FIXTURES if f.get("group") == group)


def of_type(assert_type: str | None) -> tuple[dict[str, Any], ...]:
    """All fixtures of one shape. ``None`` selects cue-label fixtures."""
    return tuple(f for f in _FIXTURES if f.get("assert_type") == assert_type)


def skip_if_review(fixture: dict[str, Any]) -> None:
    """Skip a REVIEW fixture, naming the decision that blocks it.

    A REVIEW fixture is an open question. Treating one as binding would let an
    unresolved linguistic decision be settled by whatever the code happens to do —
    which is the failure mode ``docs/decision_register.md`` exists to prevent.
    """
    if fixture["confidence"] == "REVIEW":
        blocker = REVIEW_BLOCKERS.get(fixture["id"], "author sign-off required")
        pytest.skip(f"{fixture['id']}: REVIEW — {blocker}")


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixture_meta() -> dict[str, Any]:
    """The ``meta:`` block — spec version and the pinned toolkit identity."""
    return _DATA["meta"]


@pytest.fixture(scope="session")
def all_fixtures() -> tuple[dict[str, Any], ...]:
    return _FIXTURES


@pytest.fixture(scope="session")
def normalisation_fixtures() -> tuple[dict[str, Any], ...]:
    """Group 8 — the orthographic-integrity guards (O01, O02, O03)."""
    return of_type("normalisation")


@pytest.fixture(scope="session")
def twin_symmetry_fixtures() -> tuple[dict[str, Any], ...]:
    """Group 9 — twin pairs (T01, T02). Phase 3."""
    return of_type("twin_symmetry")


@pytest.fixture
def get_fixture():
    """Look a fixture up by id, e.g. ``get_fixture("O01")``."""
    return _by_id


def pytest_report_header(config) -> list[str]:
    """Surface the REVIEW count in the header.

    An open question that is merely skipped is easy to forget. Printing the count
    on every run keeps ten unresolved decisions visible instead of letting a green
    suite imply full coverage.
    """
    review = tuple(f for f in _FIXTURES if f["confidence"] == "REVIEW")
    ids = ", ".join(f["id"] for f in review)
    return [
        f"arabgn fixtures: {len(_FIXTURES)} total, "
        f"{len(_FIXTURES) - len(review)} settled, {len(review)} REVIEW (skipped)",
        f"  REVIEW (open questions, not failures): {ids}",
    ]
