"""Cryptographic freeze. Architecture §6.3.

Pure — enters its own manifest.

The hash covers: run config, every analysis module's source, corpus checksums,
model version pins and the dependency lockfile. Confirmatory analysis **refuses to
run** if the hash does not match.

The manifest is explicit, not a glob
------------------------------------
ADR 007. A directory glob silently changes the hash when a file is added, and
silently *fails* to notice a freeze-relevant file added outside the directory.
Both are the opposite of what a freeze is for. An explicit path list makes any
change to the frozen set a reviewable diff.

What a hash does and does not prove
-----------------------------------
Architecture §6.3, stated plainly because it is the weakest link in C4:

> "A hash you compute and print in your own paper proves the config did not drift.
> It does not prove the analysis predates unblinding, because you control both the
> artifact and the clock."

:func:`external_anchor_required` exists to keep that from being forgotten. The
freeze is necessary and **not sufficient**; an external time anchor (OSF,
AsPredicted, OpenTimestamps) is what makes C4 independently verifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Mapping, Sequence

__all__ = [
    "FreezeManifest",
    "FreezeRecord",
    "compute_freeze_hash",
    "verify_freeze",
    "FreezeMismatch",
    "external_anchor_required",
]


class FreezeMismatch(Exception):
    """Raised when the computed hash does not match the frozen one."""


@dataclass(frozen=True, slots=True)
class FreezeManifest:
    """The explicit set of things the freeze covers.

    ``sources`` are repo-relative paths; ``config``, ``corpus_checksums`` and
    ``model_pins`` are already-resolved values. Nothing is discovered by scanning.
    """

    sources: tuple[str, ...]
    lockfile: str
    config: Mapping[str, object]
    corpus_checksums: Mapping[str, str]
    model_pins: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError(
                "freeze manifest has no sources — architecture §6.3 requires "
                "every analysis module's source to be covered"
            )
        duplicates = [p for p in set(self.sources) if self.sources.count(p) > 1]
        if duplicates:
            raise ValueError(
                f"duplicate paths in manifest: {sorted(duplicates)}. Each path "
                f"must appear once or the hash depends on list order."
            )


@dataclass(frozen=True, slots=True)
class FreezeRecord:
    """A computed freeze, with the per-item digests that produced it.

    Keeping the components is what makes a mismatch diagnosable: without them a
    reviewer sees only "hash differs" and cannot tell whether the config drifted,
    a module changed, or the lockfile moved.
    """

    freeze_hash: str
    components: Mapping[str, str]

    def diff(self, other: "FreezeRecord") -> tuple[str, ...]:
        """Which components differ. Sorted, for a stable report."""
        keys = sorted(set(self.components) | set(other.components))
        return tuple(
            k
            for k in keys
            if self.components.get(k) != other.components.get(k)
        )


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _canonical(value: object) -> str:
    """Deterministic serialisation of config-like values.

    Mappings are emitted in **sorted key order** — prohibition 6 forbids relying
    on dict ordering for output, and a config hash that depended on insertion
    order would not reproduce across Python versions or edits.
    """
    if isinstance(value, Mapping):
        inner = ",".join(
            f"{k}={_canonical(value[k])}" for k in sorted(value, key=str)
        )
        return "{" + inner + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def compute_freeze_hash(
    manifest: FreezeManifest, *, read_source
) -> FreezeRecord:
    """Hash the manifest. ``read_source(path) -> bytes`` supplies file contents.

    File reading is injected rather than done here so this module stays I/O-free
    and inside the freeze boundary (ADR 007). The caller — which is itself not
    frozen — does the reading.

    Components are hashed in **declared order for sources** and **sorted order for
    mappings**, so the result is reproducible.
    """
    components: dict[str, str] = {}

    for path in manifest.sources:
        components[f"source:{path}"] = _digest(read_source(path))

    components[f"lockfile:{manifest.lockfile}"] = _digest(
        read_source(manifest.lockfile)
    )
    components["config"] = _digest(_canonical(manifest.config).encode("utf-8"))
    components["corpus"] = _digest(
        _canonical(manifest.corpus_checksums).encode("utf-8")
    )
    components["models"] = _digest(
        _canonical(manifest.model_pins).encode("utf-8")
    )

    combined = "\n".join(f"{k}={components[k]}" for k in sorted(components))
    return FreezeRecord(
        freeze_hash=_digest(combined.encode("utf-8")),
        components=dict(sorted(components.items())),
    )


def verify_freeze(current: FreezeRecord, frozen_hash: str) -> None:
    """Raise unless ``current`` matches ``frozen_hash``.

    Architecture §6.3: "Confirmatory analysis refuses to run if the hash does not
    match." This raises rather than warning — a warning a caller can ignore is not
    a freeze.
    """
    if current.freeze_hash != frozen_hash:
        raise FreezeMismatch(
            f"freeze hash mismatch — confirmatory analysis refuses to run.\n"
            f"  expected: {frozen_hash}\n"
            f"  computed: {current.freeze_hash}\n"
            f"Compare component digests to locate the drift."
        )


def external_anchor_required(anchor: Mapping[str, str] | None) -> None:
    """Refuse to treat a freeze as pre-registration evidence without an anchor.

    Architecture §6.3 calls this a required design change, not an optional extra:
    a self-computed hash proves the config did not drift, but not that the
    analysis predates unblinding, "because you control both the artifact and the
    clock."

    Costs roughly an hour (OSF Registries, AsPredicted, or an OpenTimestamps proof
    anchored to a public blockchain). Without it C4's central claim is not
    independently verifiable — so this raises rather than warns.
    """
    if not anchor or not anchor.get("service") or not anchor.get("reference"):
        raise FreezeMismatch(
            "no external time anchor recorded. A self-computed hash proves the "
            "config did not drift; it does not prove the analysis predates "
            "unblinding, because the author controls both the artifact and the "
            "clock (architecture §6.3). Register with OSF, AsPredicted or "
            "OpenTimestamps and record {'service': ..., 'reference': ...}."
        )
