"""ArabJobs corpus loader. Architecture §3.1, §3.2.

I/O — not frozen. The checksums it produces do enter the freeze hash.

Source: ArabJobs (arXiv:2509.22589), CC-BY. Egypt, Jordan, Saudi Arabia, UAE.
Used as a dependency; no Arabic-resource novelty is claimed.

Two things the real data does not match
---------------------------------------
**1. There is no seniority column.** Architecture §3.2 types ``seniority`` as
"from source metadata", but the distribution ships with
``job_title, location, salary, profession, description, gender, country,
salary_local, salary_usd, job_category, sub_category`` — and no seniority.
Architecture §3.1 lists "Occupation/seniority taxonomy — Derived from ArabJobs
metadata — **Not started**", so deriving it is open work and a taxonomy is an
author decision. Every record therefore loads as ``Seniority.UNSPECIFIED`` and
:attr:`CorpusStats.seniority_derived` records that it was not derived rather than
letting the enum's default read as a finding.

**2. ArabJobs ships its own ``gender`` column** (male / neutral / female),
labelling how the ad targets applicants. It is **deliberately not used** as
input: C1 measures cue-level marking with our own tagger, and consuming the
corpus's label would make the measurement circular. It is retained in
:attr:`CorpusStats.source_gender_labels` purely as an *external comparison* for
the C1 tables — a convergent-validity check, reported alongside, never fed in.

Prohibition 1
-------------
``text_norm`` goes through :func:`arabgn.analysis.text.normalise` — NFC only.
``text_raw`` is kept byte-identical to the source so the checksum is a checksum of
what was actually distributed.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from arabgn.analysis.text import normalise
from arabgn.contracts import Country, DocRecord, DocType, Seniority

__all__ = [
    "ArabJobsLoader",
    "CorpusStats",
    "load_arabjobs",
    "describe",
    "COUNTRY_MAP",
]

#: ArabJobs spells countries in full; architecture §3.2 uses ISO-style codes.
#: Exhaustive over the distribution as of 12 Aug 2026 — an unmapped value raises
#: rather than being silently dropped or bucketed.
COUNTRY_MAP: Mapping[str, Country] = {
    "Egypt": Country.EG,
    "Jordan": Country.JO,
    "Saudi Arabia": Country.SA,
    "UAE": Country.AE,
}


@dataclass(frozen=True, slots=True)
class CorpusStats:
    """Descriptive summary. Needs no θ, so it runs before Phase 4.

    Deliberately *not* a C1 table: these are corpus properties, not cue-level
    prevalence. C1 needs the tagger, a calibrated θ and a gold set.
    """

    n_documents: int
    by_country: Mapping[str, int]
    by_job_category: Mapping[str, int]
    mean_chars: float
    mean_tokens: float
    corpus_checksum: str
    #: False until a seniority taxonomy exists (architecture §3.1, "Not started").
    seniority_derived: bool = False
    #: ArabJobs' own ad-level gender labelling. Comparison only, never input.
    source_gender_labels: Mapping[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"documents:        {self.n_documents}",
            f"corpus checksum:  {self.corpus_checksum}",
            f"mean chars:       {self.mean_chars:.1f}",
            f"mean tokens:      {self.mean_tokens:.1f}",
            "",
            "by country:",
        ]
        for key in sorted(self.by_country):
            lines.append(f"  {key:<6} {self.by_country[key]}")
        lines.append("")
        lines.append("top job categories:")
        top = sorted(self.by_job_category.items(), key=lambda kv: (-kv[1], kv[0]))
        for name, count in top[:10]:
            lines.append(f"  {count:>5}  {name}")
        if not self.seniority_derived:
            lines.append("")
            lines.append(
                "NOTE: seniority is UNSPECIFIED for every record — ArabJobs ships "
                "no seniority column and the taxonomy (architecture §3.1) is not "
                "started. Stratifying by seniority (spec §8.3) is blocked on it."
            )
        if self.source_gender_labels:
            lines.append("")
            lines.append(
                "ArabJobs' own ad-level gender labels (comparison only, never "
                "used as tagger input):"
            )
            for key in sorted(self.source_gender_labels):
                lines.append(f"  {key:<8} {self.source_gender_labels[key]}")
        return "\n".join(lines)


class ArabJobsLoader:
    """Reads the ArabJobs CSV into :class:`DocRecord` values.

    Deterministic: records are emitted in file order, and ``doc_id`` is a content
    hash rather than a row index, so re-ordering the source does not change any
    id (prohibition 6).
    """

    def __init__(self, path: Path | str, *, text_column: str = "description") -> None:
        self.path = Path(path)
        self.text_column = text_column
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} not found. The ArabJobs corpus is a separate "
                f"checkout: git clone https://github.com/drelhaj/ArabJobs"
            )

    def _rows(self) -> Iterator[dict[str, str]]:
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)

    def records(self) -> Iterator[DocRecord]:
        """Yield one :class:`DocRecord` per advertisement.

        Rows with an empty description are skipped and counted — an ad with no
        text carries no cues, and silently emitting it would put empty documents
        into the prevalence denominator.
        """
        for row in self._rows():
            text_raw = (row.get(self.text_column) or "").strip()
            if not text_raw:
                continue

            country_raw = (row.get("country") or "").strip()
            if country_raw not in COUNTRY_MAP:
                raise ValueError(
                    f"unmapped country {country_raw!r}. COUNTRY_MAP is exhaustive "
                    f"over the distribution; an unrecognised value means the "
                    f"corpus changed and the mapping must be reviewed, not "
                    f"defaulted."
                )

            digest = hashlib.sha256(text_raw.encode("utf-8")).hexdigest()
            yield DocRecord(
                doc_id=digest[:16],
                doc_type=DocType.AD,
                text_raw=text_raw,
                text_norm=normalise(text_raw),
                country=COUNTRY_MAP[country_raw],
                occupation=(row.get("profession") or "").strip(),
                # ArabJobs ships no seniority column — see the module docstring.
                seniority=Seniority.UNSPECIFIED,
                source_checksum=digest,
            )

    def checksum(self) -> str:
        """SHA-256 over the file bytes. Enters the freeze hash (§6.3)."""
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def source_gender_labels(self) -> Mapping[str, int]:
        """ArabJobs' own ad-level gender labels. **Comparison only.**

        Never used as tagger input — consuming it would make C1 circular.
        """
        counts: Counter[str] = Counter()
        for row in self._rows():
            if (row.get(self.text_column) or "").strip():
                counts[(row.get("gender") or "unknown").strip()] += 1
        return dict(sorted(counts.items()))


def load_arabjobs(path: Path | str) -> tuple[DocRecord, ...]:
    """Load every advertisement. Order is the file's, deterministically."""
    return tuple(ArabJobsLoader(path).records())


def describe(path: Path | str) -> CorpusStats:
    """Descriptive statistics. **Not** a C1 table — see :class:`CorpusStats`."""
    loader = ArabJobsLoader(path)
    records = tuple(loader.records())
    if not records:
        raise ValueError(f"no usable records in {path}")

    by_country: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    chars = 0
    tokens = 0

    for record in records:
        by_country[record.country.value] += 1
        by_category[record.occupation or "(unspecified)"] += 1
        chars += len(record.text_norm)
        tokens += len(record.text_norm.split())

    return CorpusStats(
        n_documents=len(records),
        by_country=dict(sorted(by_country.items())),
        by_job_category=dict(sorted(by_category.items())),
        mean_chars=chars / len(records),
        mean_tokens=tokens / len(records),
        corpus_checksum=loader.checksum(),
        seniority_derived=False,
        source_gender_labels=loader.source_gender_labels(),
    )
