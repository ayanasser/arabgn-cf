"""Compute and verify the freeze hash for this repository. I/O — not frozen.

:mod:`arabgn.analysis.freeze` is pure and takes file contents through an injected
reader (ADR 007). This module is that reader, plus the repository's actual
manifest.

Usage::

    uv run python -m arabgn.freeze_cli compute
    uv run python -m arabgn.freeze_cli verify --hash <expected>
    uv run python -m arabgn.freeze_cli manifest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arabgn.analysis.freeze import (
    FreezeManifest,
    FreezeMismatch,
    compute_freeze_hash,
    verify_freeze,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The explicit frozen set — ADR 007. **Not a glob.**
#:
#: A directory glob silently changes the hash when a file is added and silently
#: misses freeze-relevant files added elsewhere. Adding a path here is a
#: reviewable diff, which is the point.
#:
#: `arabgn/contracts.py` is included because it defines output shape — a change
#: there changes results — even though it lives outside `analysis/`.
#: `arabgn/tagger/` is deliberately EXCLUDED: it loads models and is pinned
#: instead by `toolkit_version` / `db_version` on every emitted cue.
FROZEN_SOURCES: tuple[str, ...] = (
    "arabgn/contracts.py",
    "arabgn/analysis/__init__.py",
    "arabgn/analysis/agreement.py",
    "arabgn/analysis/agreement_target.py",
    "arabgn/analysis/blinding.py",
    "arabgn/analysis/cues.py",
    "arabgn/analysis/freeze.py",
    "arabgn/analysis/inference.py",
    "arabgn/analysis/reporting.py",
    "arabgn/analysis/sampling.py",
    "arabgn/analysis/symmetry.py",
    "arabgn/analysis/text.py",
    "arabgn/analysis/thresholds.py",
    "arabgn/analysis/tiers.py",
    "arabgn/analysis/variance.py",
)

LOCKFILE = "uv.lock"


def _read(path: str) -> bytes:
    full = REPO_ROOT / path
    if not full.exists():
        raise FileNotFoundError(
            f"{path} is in the freeze manifest but does not exist. Either the "
            f"file was removed without updating FROZEN_SOURCES, or the manifest "
            f"is wrong. Both are freeze-relevant."
        )
    return full.read_bytes()


def build_manifest(
    config: dict | None = None,
    corpus_checksums: dict | None = None,
    model_pins: dict | None = None,
) -> FreezeManifest:
    """The repository's manifest.

    Defaults are placeholders for the parts that are not yet frozen: θ is
    calibrated at Phase 4, and the corpus checksums come from the Phase 7 loader.
    They are explicit ``None``-marked rather than invented values.
    """
    return FreezeManifest(
        sources=FROZEN_SOURCES,
        lockfile=LOCKFILE,
        config=config
        or {
            "theta_high": None,  # UNSET — calibrated at Phase 4 (ADR 001)
            "theta_low": None,  # UNSET — calibrated at Phase 4 (ADR 001)
            "seed": None,  # UNSET — declared in the run config
            "top_n": 100,  # settled, CLAUDE.md
        },
        corpus_checksums=corpus_checksums or {},
        model_pins=model_pins
        or {
            "camel_tools": "1.6.0",
            "morphology_db": "calima-msa-r13",
            "disambiguator": "bert-unfactored-msa",
        },
    )


def cmd_compute(args) -> int:
    record = compute_freeze_hash(build_manifest(), read_source=_read)
    if args.json:
        print(json.dumps({"freeze_hash": record.freeze_hash,
                          "components": dict(record.components)}, indent=2))
    else:
        print(f"freeze hash: {record.freeze_hash}")
        print(f"components:  {len(record.components)}")
        unset = [
            k for k, v in build_manifest().config.items() if v is None
        ]
        if unset:
            print(
                f"\nWARNING: config values still unset: {', '.join(sorted(unset))}.\n"
                f"This hash is NOT a pre-registration freeze — θ is calibrated at\n"
                f"Phase 4 and the seed is declared in the run config."
            )
    return 0


def cmd_verify(args) -> int:
    record = compute_freeze_hash(build_manifest(), read_source=_read)
    try:
        verify_freeze(record, args.hash)
    except FreezeMismatch as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("freeze hash matches")
    return 0


def cmd_manifest(args) -> int:
    print(f"{len(FROZEN_SOURCES)} frozen sources + {LOCKFILE}:")
    for path in FROZEN_SOURCES:
        print(f"  {path}")
    print("\nDeliberately excluded (ADR 007):")
    print("  arabgn/tagger/       — loads models; pinned via db_version on each cue")
    print("  arabgn/adjudication/ — I/O layer")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arabgn.freeze_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("compute", help="compute the freeze hash")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_compute)

    p = sub.add_parser("verify", help="verify against a known hash")
    p.add_argument("--hash", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("manifest", help="list the frozen set")
    p.set_defaults(func=cmd_manifest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
