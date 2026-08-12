"""Phase 9 — HMAC cell blinding and the freeze. Architecture §6.

Assertions trace to architecture §6.1 (blinding), §6.3 (freeze) or a prohibition.
No model needed: both modules are pure.
"""

from __future__ import annotations

import pytest

from arabgn.analysis.blinding import (
    BlindingError,
    CellIdentity,
    blind_cell,
    blind_order,
    verify_no_ordering_leak,
)
from arabgn.analysis.freeze import (
    FreezeManifest,
    FreezeMismatch,
    compute_freeze_hash,
    external_anchor_required,
    verify_freeze,
)

KEY = b"a-32-byte-key-held-outside-repo!"


def cell(register="R1", polarity="f", pair_id="p1"):
    return CellIdentity(register=register, polarity=polarity, pair_id=pair_id)


# ---------------------------------------------------------------------------
# Architecture §6.1 — the token must hide cell identity
# ---------------------------------------------------------------------------


def test_token_leaks_no_field_of_the_cell():
    """A blind token that contains the register is not blind.

    Only multi-character secrets are substring-checked: `f` and `m` are hex
    digits and appear in any digest by chance, so a substring test on them would
    fail on a perfectly good token. Polarity is covered by the avalanche test
    below, which is the property that actually matters.
    """
    token = blind_cell(cell(register="R3", polarity="f", pair_id="pair-42"), KEY)
    for secret in ("R3", "pair-42"):
        assert secret not in token.token


def test_polarity_change_avalanches_across_the_token():
    """Flipping polarity must change the token globally, not in one position.

    If `f` and `m` tokens differed in a predictable place, a preparer could read
    polarity straight off the token — which is exactly what §6.1 forbids. A
    good HMAC changes roughly half the hex digits.
    """
    f = blind_cell(cell(polarity="f"), KEY).token
    m = blind_cell(cell(polarity="m"), KEY).token
    differing = sum(1 for a, b in zip(f, m) if a != b)
    assert differing > len(f) * 0.3, (
        f"only {differing}/{len(f)} hex digits changed when polarity flipped — "
        f"polarity may be readable from token position"
    )


def test_token_is_fixed_width_regardless_of_input():
    """Length must not distinguish `R1` from a long pair id.

    A variable-width token leaks through its size alone.
    """
    short = blind_cell(cell(pair_id="p"), KEY)
    long = blind_cell(cell(pair_id="p" * 200), KEY)
    assert len(short.token) == len(long.token) == 32


def test_blinding_is_deterministic():
    """Prohibition 6, and a practical requirement: unblinding must re-derive."""
    assert blind_cell(cell(), KEY) == blind_cell(cell(), KEY)


def test_different_cells_give_different_tokens():
    """Otherwise two cells collide and the blinding destroys the design."""
    tokens = {
        blind_cell(cell(register=r, polarity=p), KEY).token
        for r in ("R1", "R2", "R3", "R4", "R5")
        for p in ("f", "m")
    }
    assert len(tokens) == 10


def test_polarity_alone_changes_the_token():
    """Twin polarity is the single most sensitive field (architecture §6.1)."""
    f = blind_cell(cell(polarity="f"), KEY)
    m = blind_cell(cell(polarity="m"), KEY)
    assert f != m


def test_different_keys_give_different_tokens():
    """The key is what makes the small cell space unenumerable."""
    other = b"a-different-32-byte-key-for-test"
    assert blind_cell(cell(), KEY) != blind_cell(cell(), other)


def test_empty_key_is_rejected():
    """An unkeyed digest over a handful of cells is reversible by enumeration."""
    with pytest.raises(BlindingError, match="empty"):
        blind_cell(cell(), b"")


def test_short_key_is_rejected():
    """The cell space is tiny; a short key is brute-forceable."""
    with pytest.raises(BlindingError, match="brute-force"):
        blind_cell(cell(), b"short")


# ---------------------------------------------------------------------------
# Architecture §6.1 — ordering leaks, "the most common failure mode here"
# ---------------------------------------------------------------------------


def test_grouped_ordering_is_detected_as_a_leak():
    """All the female twins first. Labels opaque, position not.

    This is the naive failure: blind the labels, emit in generation order.
    """
    cells = [cell(polarity="f") for _ in range(5)] + [
        cell(polarity="m") for _ in range(5)
    ]
    assert not verify_no_ordering_leak(cells, attribute="polarity")


def test_alternating_ordering_is_detected_as_a_leak():
    """f, m, f, m… — position parity predicts polarity exactly."""
    cells = [cell(polarity="f" if i % 2 == 0 else "m") for i in range(10)]
    assert not verify_no_ordering_leak(cells, attribute="polarity")


def test_register_sorted_ordering_is_detected_as_a_leak():
    """R1×3, R2×3, R3×3 — grouped by register."""
    cells = [cell(register=f"R{1 + i // 3}") for i in range(9)]
    assert not verify_no_ordering_leak(cells, attribute="register")


def test_blind_token_ordering_does_not_leak_polarity():
    """`blind_order` sorts by a value uncorrelated with cell identity.

    Deterministic (so runs reproduce) but carrying no positional information.
    """
    items = [
        {"id": i, "cell": cell(polarity="f" if i % 2 == 0 else "m", pair_id=f"p{i}")}
        for i in range(30)
    ]
    ordered = blind_order(items, KEY, cell_of=lambda item: item["cell"])
    cells_in_order = [item["cell"] for _, item in ordered]
    assert verify_no_ordering_leak(cells_in_order, attribute="polarity")


def test_blind_order_is_deterministic():
    items = [{"id": i, "cell": cell(pair_id=f"p{i}")} for i in range(20)]
    a = blind_order(items, KEY, cell_of=lambda i: i["cell"])
    b = blind_order(list(reversed(items)), KEY, cell_of=lambda i: i["cell"])
    assert [t.token for t, _ in a] == [t.token for t, _ in b]


def test_single_valued_attribute_cannot_leak():
    """Nothing to hide when every cell shares the value."""
    assert verify_no_ordering_leak([cell(polarity="f")] * 5, attribute="polarity")


# ---------------------------------------------------------------------------
# Architecture §6.3 — the freeze
# ---------------------------------------------------------------------------

FILES = {
    "arabgn/analysis/text.py": b"def normalise(t): ...",
    "arabgn/contracts.py": b"class TaggedCue: ...",
    "uv.lock": b"# lock",
}


def manifest(**over):
    base = dict(
        sources=("arabgn/analysis/text.py", "arabgn/contracts.py"),
        lockfile="uv.lock",
        config={"seed": 42, "theta_high": 0.495, "theta_low": 0.285},
        corpus_checksums={"arabjobs": "abc123"},
        model_pins={"camel_tools": "1.6.0", "db": "calima-msa-r13"},
    )
    base.update(over)
    return FreezeManifest(**base)


def reader(files=None):
    files = files or FILES
    return lambda path: files[path]


def test_freeze_hash_is_deterministic():
    """Prohibition 6 — the whole reproducibility claim rests on this."""
    a = compute_freeze_hash(manifest(), read_source=reader())
    b = compute_freeze_hash(manifest(), read_source=reader())
    assert a.freeze_hash == b.freeze_hash


def test_config_key_order_does_not_change_the_hash():
    """A config hash depending on dict insertion order would not reproduce."""
    a = compute_freeze_hash(
        manifest(config={"seed": 42, "theta_high": 0.5}), read_source=reader()
    )
    b = compute_freeze_hash(
        manifest(config={"theta_high": 0.5, "seed": 42}), read_source=reader()
    )
    assert a.freeze_hash == b.freeze_hash


def test_source_change_changes_the_hash():
    """Architecture §6.3 — "every analysis module's source"."""
    before = compute_freeze_hash(manifest(), read_source=reader())
    drifted = dict(FILES, **{"arabgn/analysis/text.py": b"def normalise(t): pass"})
    after = compute_freeze_hash(manifest(), read_source=reader(drifted))
    assert before.freeze_hash != after.freeze_hash


def test_lockfile_change_changes_the_hash():
    """Architecture §6.3 names the dependency lockfile explicitly.

    This is why prohibition 5 exists: adding a dependency changes the freeze.
    """
    before = compute_freeze_hash(manifest(), read_source=reader())
    drifted = dict(FILES, **{"uv.lock": b"# lock + one more package"})
    after = compute_freeze_hash(manifest(), read_source=reader(drifted))
    assert before.freeze_hash != after.freeze_hash


def test_theta_change_changes_the_hash():
    """θ is a pre-registered constant; silently retuning it must be visible."""
    before = compute_freeze_hash(manifest(), read_source=reader())
    after = compute_freeze_hash(
        manifest(config={"seed": 42, "theta_high": 0.60, "theta_low": 0.285}),
        read_source=reader(),
    )
    assert before.freeze_hash != after.freeze_hash


def test_corpus_and_model_pins_are_covered():
    base = compute_freeze_hash(manifest(), read_source=reader())
    corpus = compute_freeze_hash(
        manifest(corpus_checksums={"arabjobs": "different"}), read_source=reader()
    )
    models = compute_freeze_hash(
        manifest(model_pins={"camel_tools": "1.7.0"}), read_source=reader()
    )
    assert len({base.freeze_hash, corpus.freeze_hash, models.freeze_hash}) == 3


def test_verify_refuses_to_run_on_drift():
    """Architecture §6.3 — "refuses to run if the hash does not match"."""
    record = compute_freeze_hash(manifest(), read_source=reader())
    verify_freeze(record, record.freeze_hash)
    with pytest.raises(FreezeMismatch, match="refuses to run"):
        verify_freeze(record, "0" * 64)


def test_mismatch_is_diagnosable():
    """"Hash differs" is not actionable; the component diff is."""
    before = compute_freeze_hash(manifest(), read_source=reader())
    drifted = dict(FILES, **{"arabgn/contracts.py": b"class TaggedCue: pass"})
    after = compute_freeze_hash(manifest(), read_source=reader(drifted))
    assert before.diff(after) == ("source:arabgn/contracts.py",)


# ---------------------------------------------------------------------------
# ADR 007 — explicit manifest, not a glob
# ---------------------------------------------------------------------------


def test_empty_manifest_is_rejected():
    """A freeze covering nothing would pass every check and prove nothing."""
    with pytest.raises(ValueError, match="no sources"):
        manifest(sources=())


def test_duplicate_paths_are_rejected():
    """A repeated path makes the hash depend on list order."""
    with pytest.raises(ValueError, match="duplicate"):
        manifest(sources=("a.py", "a.py"))


def test_adding_a_source_changes_the_hash():
    """The point of an explicit manifest: growing the frozen set is visible.

    Under a directory glob this change would be silent.
    """
    two = compute_freeze_hash(manifest(), read_source=reader())
    three = compute_freeze_hash(
        manifest(sources=("arabgn/analysis/text.py", "arabgn/contracts.py", "uv.lock")),
        read_source=reader(),
    )
    assert two.freeze_hash != three.freeze_hash


# ---------------------------------------------------------------------------
# Architecture §6.3 — the hash is necessary and NOT sufficient
# ---------------------------------------------------------------------------


def test_external_anchor_is_required():
    """"You control both the artifact and the clock."

    A self-computed hash proves the config did not drift, not that the analysis
    predates unblinding. Without an anchor C4's central claim is not
    independently verifiable — so this raises rather than warns.
    """
    with pytest.raises(FreezeMismatch, match="external time anchor"):
        external_anchor_required(None)
    with pytest.raises(FreezeMismatch, match="external time anchor"):
        external_anchor_required({})
    with pytest.raises(FreezeMismatch, match="external time anchor"):
        external_anchor_required({"service": "OSF"})  # no reference


def test_complete_anchor_is_accepted():
    external_anchor_required({"service": "OSF", "reference": "10.17605/OSF.IO/XXXXX"})


# ---------------------------------------------------------------------------
# The repository's real manifest — ADR 007
# ---------------------------------------------------------------------------


def test_repo_manifest_covers_every_pure_analysis_module():
    """The frozen set must not drift behind `arabgn/analysis/`.

    Adding a module there without adding it to FROZEN_SOURCES would leave
    freeze-relevant source outside the hash — the exact failure an explicit
    manifest exists to make visible.
    """
    from pathlib import Path

    from arabgn.freeze_cli import FROZEN_SOURCES, REPO_ROOT

    on_disk = {
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / "arabgn" / "analysis").glob("*.py")
    }
    missing = on_disk - set(FROZEN_SOURCES)
    assert not missing, (
        f"pure analysis modules missing from the freeze manifest: "
        f"{sorted(missing)}"
    )


def test_repo_manifest_excludes_the_model_loading_layer():
    """ADR 007 — `tagger/` is pinned by db_version on each cue, not by hash."""
    from arabgn.freeze_cli import FROZEN_SOURCES

    assert not [p for p in FROZEN_SOURCES if p.startswith("arabgn/tagger/")]
    assert not [p for p in FROZEN_SOURCES if p.startswith("arabgn/adjudication/")]


def test_repo_freeze_hash_computes_and_is_stable():
    """End-to-end over the real repository, twice."""
    from arabgn.freeze_cli import _read, build_manifest

    a = compute_freeze_hash(build_manifest(), read_source=_read)
    b = compute_freeze_hash(build_manifest(), read_source=_read)
    assert a.freeze_hash == b.freeze_hash
    assert len(a.freeze_hash) == 64


def test_missing_frozen_source_fails_loudly():
    """A manifest path that does not exist is itself freeze-relevant."""
    from arabgn.freeze_cli import _read

    with pytest.raises(FileNotFoundError, match="freeze manifest"):
        _read("arabgn/analysis/does_not_exist.py")
