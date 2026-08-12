"""HMAC cell blinding. Architecture §6.1.

Pure — enters the freeze manifest. The **key** does not: it is held outside the
analysis repository and supplied by the caller.

What is being hidden
--------------------
Cell identity — which register (R1–R5), which twin polarity (female/male) — from
everyone who prepares or scores material. If a preparer knows which twin is which,
every downstream difference is potentially their expectation rather than the
ranker's behaviour.

Ordering is the leak that actually happens
------------------------------------------
Architecture §6.1: "Tests must confirm no cell identity leaks through file
ordering, filename, or record ordering — **ordering leaks are the most common
failure mode here**."

Blinding the label and then emitting records female-first is not blinding. So
:func:`blind_order` sorts by the *blind token*, which is uncorrelated with cell
identity by construction, rather than by anything derived from the cell.

Unblinding
----------
A separate, logged, one-way operation — see :mod:`arabgn.blinding.unblind`. This
module can blind; it cannot reverse.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping, Sequence

__all__ = [
    "CellIdentity",
    "BlindToken",
    "blind_cell",
    "blind_order",
    "verify_no_ordering_leak",
    "BlindingError",
]


class BlindingError(Exception):
    """Raised when blinding is misused in a way that would leak cell identity."""


@dataclass(frozen=True, slots=True)
class CellIdentity:
    """What must stay hidden: register, twin polarity, and the pair it belongs to.

    ``pair_id`` identifies the twin pair; ``polarity`` is which half. Both are
    secret — knowing the pair without the polarity still lets a preparer group
    twins together, which is enough to bias handling.
    """

    register: str
    polarity: str
    pair_id: str

    def canonical(self) -> str:
        """Stable serialisation for the HMAC message.

        Field order is declared here and must never change: altering it changes
        every blind token and silently invalidates a run in progress.
        """
        return f"register={self.register}|polarity={self.polarity}|pair={self.pair_id}"


@dataclass(frozen=True, slots=True)
class BlindToken:
    """An opaque handle standing in for a cell identity.

    Carries no field from :class:`CellIdentity` — not even a length that could
    distinguish ``R1`` from ``R5``, since the digest is fixed width.
    """

    token: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.token


def blind_cell(cell: CellIdentity, key: bytes, *, length: int = 32) -> BlindToken:
    """HMAC-SHA256 the cell identity under ``key``.

    Parameters
    ----------
    key:
        Held **outside** the analysis repository (architecture §6.1). Passing a
        key that is empty or obviously a placeholder raises rather than producing
        a token that looks blind but is trivially reversible.
    length:
        Hex characters retained. 32 is 128 bits — far beyond what is needed to
        avoid collisions over a few thousand cells, and fixed width so the token
        leaks nothing about the input.

    Deterministic by construction: the same cell and key always give the same
    token, which is what lets a blinded run be re-derived at unblinding time.
    """
    if not key:
        raise BlindingError(
            "blinding key is empty — an unkeyed digest is reversible by "
            "enumeration over the small cell space (architecture §6.1)"
        )
    if len(key) < 16:
        raise BlindingError(
            f"blinding key is {len(key)} bytes; the cell space is small enough "
            f"to brute-force against a short key. Use >= 16 bytes."
        )

    digest = hmac.new(key, cell.canonical().encode("utf-8"), sha256).hexdigest()
    return BlindToken(digest[:length])


def blind_order(
    items: Iterable[Mapping[str, object]],
    key: bytes,
    *,
    cell_of,
) -> tuple[tuple[BlindToken, Mapping[str, object]], ...]:
    """Order records by blind token, destroying any cell-correlated ordering.

    The naive failure: blind the labels, then emit records in the order they were
    generated — which is female-then-male, or R1-through-R5. The labels are
    opaque but the *position* is not, and position is enough.

    Sorting by the blind token gives an order that is deterministic (so runs
    reproduce) but uncorrelated with cell identity (so position carries no
    information).
    """
    tagged = [(blind_cell(cell_of(item), key), item) for item in items]
    return tuple(sorted(tagged, key=lambda pair: pair[0].token))


def verify_no_ordering_leak(
    ordered_cells: Sequence[CellIdentity], *, attribute: str
) -> bool:
    """Is ``attribute`` predictable from position in ``ordered_cells``?

    Returns ``True`` when the ordering carries **no** information about the
    attribute. The check is deliberately crude and conservative: it flags the
    cases that actually occur in practice — fully sorted, fully grouped, or
    strictly alternating — rather than attempting a general independence test.

    A leak here is not subtle. It looks like "all the female twins came first."
    """
    values = [getattr(cell, attribute) for cell in ordered_cells]
    if len(set(values)) < 2:
        return True  # nothing to leak

    # Fully sorted, either direction: adjacent equal-runs count == distinct count.
    runs = 1 + sum(1 for a, b in zip(values, values[1:]) if a != b)
    if runs == len(set(values)):
        return False  # perfectly grouped/sorted — position predicts the value

    # Strictly alternating over two values: position parity predicts the value.
    if len(set(values)) == 2 and all(
        a != b for a, b in zip(values, values[1:])
    ):
        return False

    return True
