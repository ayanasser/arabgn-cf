"""Blind annotation CLI. Spec §8.

Usage::

    uv run python -m arabgn.adjudication.cli annotate \\
        --items items.jsonl --out annotations.jsonl --annotator A1

    uv run python -m arabgn.adjudication.cli kappa \\
        --annotations annotations.jsonl --a A1 --b A2

Deliberately plain. The annotator sees the sentence with the cue delimited and
the document type, and answers ``a`` / ``n`` / ``u``. Nothing about the tagger's
prediction is loaded, so nothing about it can be displayed (spec §8.2).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arabgn.adjudication.items import AnnotationItem, AnnotationResponse
from arabgn.adjudication.store import AnnotationStore, utc_timestamp
from arabgn.analysis.agreement import (
    GoldSetUnusable,
    assert_gold_set_usable,
    cohens_kappa,
)
from arabgn.contracts import DocType

_ANSWER_KEYS = {
    "a": "applicant",
    "n": "non_applicant",
    "u": "unclear",
}

_PROMPT = """
{sep}
[{index}/{total}]  document type: {doc_type}

  {rendered}

  cue: {cue}

  (a) applicant      — the marking refers to the job applicant
  (n) non-applicant  — it refers to anything else
  (u) unclear        — genuinely indeterminate from the context shown
  (s) skip           (q) quit

  `unclear` is a valid answer. Do not guess.
"""


def _load_items(path: Path) -> tuple[AnnotationItem, ...]:
    items = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record["doc_type"] = DocType(record["doc_type"])
            items.append(AnnotationItem(**record))
    return tuple(items)


def annotate(args: argparse.Namespace) -> int:
    items = _load_items(Path(args.items))
    store = AnnotationStore(args.out)

    already = {
        r.item_id
        for r in store.responses()
        if r.annotator_id == args.annotator
    }
    todo = [i for i in items if i.item_id not in already]

    if not todo:
        print(f"nothing left for annotator {args.annotator!r}")
        return 0

    print(
        f"annotator {args.annotator!r}: {len(todo)} items "
        f"({len(already)} already done)"
    )

    for index, item in enumerate(todo, 1):
        print(
            _PROMPT.format(
                sep="─" * 72,
                index=index,
                total=len(todo),
                doc_type=item.doc_type.value,
                rendered=item.render(),
                cue=item.cue,
            )
        )
        while True:
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nstopped; answers so far are saved")
                return 0
            if choice == "q":
                print("stopped; answers so far are saved")
                return 0
            if choice == "s":
                break
            if choice in _ANSWER_KEYS:
                store.append(
                    AnnotationResponse(
                        item_id=item.item_id,
                        annotator_id=args.annotator,
                        answer=_ANSWER_KEYS[choice],
                        timestamp=utc_timestamp(),
                    )
                )
                break
            print("  please answer a, n, u, s or q")

    print(f"\ndone. unclear rate so far: {store.unclear_rate():.3f}")
    return 0


def kappa(args: argparse.Namespace) -> int:
    store = AnnotationStore(args.annotations)
    grouped = store.by_annotator()

    for who in (args.a, args.b):
        if who not in grouped:
            print(f"no annotations from {who!r}", file=sys.stderr)
            return 2

    shared = store.double_annotated()
    by_a = {r.item_id: r.answer for r in grouped[args.a]}
    by_b = {r.item_id: r.answer for r in grouped[args.b]}
    common = tuple(i for i in shared if i in by_a and i in by_b)

    if not common:
        print("no doubly-annotated items shared by this pair", file=sys.stderr)
        return 2

    result = cohens_kappa([by_a[i] for i in common], [by_b[i] for i in common])

    print(f"n items          : {result.n_items}")
    print(f"observed agree   : {result.observed_agreement:.4f}")
    print(f"expected agree   : {result.expected_agreement:.4f}")
    print(
        f"Cohen's kappa    : "
        f"{'undefined' if result.kappa is None else f'{result.kappa:.4f}'}"
    )
    print(f"unclear rate     : {result.unclear_rate:.4f}")

    try:
        assert_gold_set_usable(result)
    except GoldSetUnusable as exc:
        print(f"\nGATE FAILED (architecture §8.1)\n{exc}", file=sys.stderr)
        return 1

    print("\ngate passed: kappa >= 0.7, gold set is usable")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arabgn.adjudication")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ann = sub.add_parser("annotate", help="blind annotation session")
    p_ann.add_argument("--items", required=True)
    p_ann.add_argument("--out", required=True)
    p_ann.add_argument("--annotator", required=True, help="stable annotator id")
    p_ann.set_defaults(func=annotate)

    p_kap = sub.add_parser("kappa", help="Cohen's kappa over a pair")
    p_kap.add_argument("--annotations", required=True)
    p_kap.add_argument("--a", required=True)
    p_kap.add_argument("--b", required=True)
    p_kap.set_defaults(func=kappa)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
