"""Append-only annotation store. Spec §8.

JSON Lines, opened ``"a"``, one response per line. There is no update path and no
delete path — an annotation that could be revised in place is an annotation whose
history cannot be audited, and κ would silently change under it.

Not frozen (ADR 007): this is I/O.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from arabgn.adjudication.items import AnnotationResponse

__all__ = ["AnnotationStore", "utc_timestamp"]


def utc_timestamp() -> str:
    """ISO-8601 UTC, second precision.

    The one sanctioned wall-clock read in the project. Prohibition 6 forbids
    wall-clock in *derived values*; this is recorded provenance about an
    annotation and never enters a computation or the freeze hash.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AnnotationStore:
    """Append-only JSONL store of :class:`AnnotationResponse`.

    Example
    -------
    >>> store = AnnotationStore(path)             # doctest: +SKIP
    >>> store.append(response)                    # doctest: +SKIP
    >>> len(list(store.responses()))              # doctest: +SKIP
    1
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, response: AnnotationResponse) -> None:
        """Append one response. Never overwrites, never rewrites."""
        record = asdict(response)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def responses(self) -> Iterator[AnnotationResponse]:
        """Read back in append order. Order is the file's, never re-sorted."""
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"{self.path}:{line_no} is not valid JSON: {exc}"
                    ) from exc
                yield AnnotationResponse(**record)

    def by_annotator(self) -> dict[str, list[AnnotationResponse]]:
        """Group responses by annotator, preserving append order within each.

        Keys are returned in sorted order for determinism (prohibition 6).
        """
        grouped: dict[str, list[AnnotationResponse]] = {}
        for response in self.responses():
            grouped.setdefault(response.annotator_id, []).append(response)
        return {k: grouped[k] for k in sorted(grouped)}

    def double_annotated(self) -> tuple[str, ...]:
        """Item ids answered by two or more distinct annotators — the κ subset.

        Sorted, so the κ computation is order-stable.
        """
        seen: dict[str, set[str]] = {}
        for response in self.responses():
            seen.setdefault(response.item_id, set()).add(response.annotator_id)
        return tuple(sorted(i for i, who in seen.items() if len(who) >= 2))

    def unclear_rate(self) -> float:
        """Proportion of all responses answered ``unclear``.

        Spec §8.1: "the rate of ``unclear`` is itself reported". Never dropped,
        never coerced.
        """
        responses = list(self.responses())
        if not responses:
            return 0.0
        return sum(1 for r in responses if r.answer == "unclear") / len(responses)
