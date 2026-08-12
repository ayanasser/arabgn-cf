"""ArabJobs corpus loader. Architecture §3.1, §3.2.

The corpus is a separate checkout (`git clone .../ArabJobs`), so tests needing the
real file skip cleanly when it is absent. The contract-level tests run on a
synthetic CSV and always execute.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from arabgn.contracts import Country, DocType, Seniority
from arabgn.corpus.arabjobs import (
    COUNTRY_MAP,
    ArabJobsLoader,
    describe,
    load_arabjobs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARABJOBS = REPO_ROOT / "ArabJobs" / "ArabJobs.csv"

HEADER = [
    "job_title", "location", "salary", "profession", "description",
    "gender", "country", "salary_local", "salary_usd",
    "job_category", "sub_category",
]


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in HEADER})
    return path


def row(description="مطلوب مهندس برمجيات", country="Egypt", **over):
    base = {
        "description": description, "country": country,
        "profession": "برمجة", "gender": "male", "job_category": "تقنية",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Architecture §3.2 — the contract
# ---------------------------------------------------------------------------


def test_records_are_docrecords_of_type_ad(tmp_path):
    path = write_csv(tmp_path / "c.csv", [row()])
    record = load_arabjobs(path)[0]
    assert record.doc_type is DocType.AD
    assert record.country is Country.EG


def test_all_four_countries_map(tmp_path):
    """The distribution's four countries are exactly the §3.2 enum."""
    rows = [row(description=f"ad {i}", country=c)
            for i, c in enumerate(COUNTRY_MAP)]
    records = load_arabjobs(write_csv(tmp_path / "c.csv", rows))
    assert {r.country for r in records} == {
        Country.EG, Country.JO, Country.SA, Country.AE
    }


def test_unmapped_country_raises_rather_than_defaulting(tmp_path):
    """A new country value means the corpus changed and the mapping needs review.

    Silently bucketing it would corrupt every country-stratified statistic.
    """
    path = write_csv(tmp_path / "c.csv", [row(country="Morocco")])
    with pytest.raises(ValueError, match="unmapped country"):
        load_arabjobs(path)


def test_seniority_is_unspecified_because_the_corpus_has_no_such_column(tmp_path):
    """Architecture §3.2 types seniority "from source metadata" — but ArabJobs
    ships no seniority column, and §3.1 lists the taxonomy as "Not started".

    Recorded rather than invented. Stratifying by seniority (spec §8.3) is
    blocked on the taxonomy.
    """
    record = load_arabjobs(write_csv(tmp_path / "c.csv", [row()]))[0]
    assert record.seniority is Seniority.UNSPECIFIED
    assert "seniority" not in HEADER


def test_empty_descriptions_are_skipped(tmp_path):
    """An ad with no text carries no cues; including it would inflate the
    prevalence denominator."""
    rows = [row(description="نص حقيقي"), row(description="  "), row(description="")]
    assert len(load_arabjobs(write_csv(tmp_path / "c.csv", rows))) == 1


# ---------------------------------------------------------------------------
# Prohibition 1 and 6
# ---------------------------------------------------------------------------


def test_text_raw_is_preserved_and_text_norm_is_nfc_only(tmp_path):
    """Prohibition 1 — ta-marbuta and hamza must survive loading."""
    text = "مطلوبة مهندسة حاصلة على بكالوريوس من جامعة أحمد"
    record = load_arabjobs(write_csv(tmp_path / "c.csv", [row(description=text)]))[0]
    assert record.text_raw == text
    assert record.text_norm.count("ة") == text.count("ة")
    assert record.text_norm.count("أ") == text.count("أ")


def test_doc_id_is_content_derived_not_positional(tmp_path):
    """Prohibition 6 — reordering the source must not change any id."""
    a = load_arabjobs(write_csv(tmp_path / "a.csv", [row(description="أ"), row(description="ب")]))
    b = load_arabjobs(write_csv(tmp_path / "b.csv", [row(description="ب"), row(description="أ")]))
    assert {r.doc_id for r in a} == {r.doc_id for r in b}


def test_checksum_is_stable_and_changes_with_content(tmp_path):
    """Corpus checksums enter the freeze hash (architecture §6.3)."""
    one = ArabJobsLoader(write_csv(tmp_path / "a.csv", [row()]))
    two = ArabJobsLoader(write_csv(tmp_path / "b.csv", [row(description="مختلف")]))
    assert one.checksum() == ArabJobsLoader(one.path).checksum()
    assert one.checksum() != two.checksum()


def test_missing_corpus_gives_an_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="git clone"):
        ArabJobsLoader(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# The corpus's own gender labels must not become tagger input
# ---------------------------------------------------------------------------


def test_source_gender_labels_are_reported_but_never_on_the_record(tmp_path):
    """ArabJobs labels each ad male/neutral/female.

    Consuming it as input would make C1 circular — the tagger would be scored
    against a label it had been given. It is retained only as an external
    convergent-validity comparison.
    """
    rows = [row(gender="male"), row(description="x", gender="female")]
    path = write_csv(tmp_path / "c.csv", rows)
    stats = describe(path)
    assert stats.source_gender_labels == {"female": 1, "male": 1}

    record = load_arabjobs(path)[0]
    assert not hasattr(record, "gender")
    assert "female" not in str(record)


# ---------------------------------------------------------------------------
# Descriptive pass — needs no θ, so it runs before Phase 4
# ---------------------------------------------------------------------------


def test_describe_reports_seniority_as_underived(tmp_path):
    stats = describe(write_csv(tmp_path / "c.csv", [row(), row(description="ب")]))
    assert stats.seniority_derived is False
    assert "seniority is UNSPECIFIED" in stats.summary()


def test_describe_rejects_an_empty_corpus(tmp_path):
    with pytest.raises(ValueError, match="no usable records"):
        describe(write_csv(tmp_path / "c.csv", [row(description="")]))


# ---------------------------------------------------------------------------
# The real corpus, when present
# ---------------------------------------------------------------------------

real_corpus = pytest.mark.skipif(
    not ARABJOBS.exists(),
    reason="ArabJobs not checked out (git clone https://github.com/drelhaj/ArabJobs)",
)


@real_corpus
def test_real_corpus_loads_completely():
    """Every row must map; nothing silently dropped except empty descriptions."""
    records = load_arabjobs(ARABJOBS)
    assert len(records) > 8000
    assert all(r.text_raw for r in records)
    assert {r.country for r in records} == {
        Country.EG, Country.JO, Country.SA, Country.AE
    }


@real_corpus
def test_real_corpus_preserves_ta_marbuta():
    """Prohibition 1, over the whole corpus rather than one fixture."""
    records = load_arabjobs(ARABJOBS)
    for record in records[:500]:
        assert record.text_norm.count("ة") == record.text_raw.count("ة")


@real_corpus
def test_real_corpus_doc_ids_are_unique_per_text():
    records = load_arabjobs(ARABJOBS)
    by_id = {}
    for record in records:
        if record.doc_id in by_id:
            assert by_id[record.doc_id] == record.text_raw, (
                "doc_id collision between different texts"
            )
        by_id[record.doc_id] = record.text_raw
