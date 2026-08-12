"""Text normalisation. NFC and nothing else.

Architecture §3.2 calls this "the single most important preprocessing decision in
the system". It is pure and enters the freeze manifest (ADR 007), which is why it
lives under ``arabgn/analysis/`` rather than at the package root.

CLAUDE.md prohibition 1 — never normalise Arabic orthography
------------------------------------------------------------
Standard Arabic preprocessing pipelines strip these as a matter of course. Doing
so here would silently destroy the signal the entire study measures:

===============  ==========================================================
``ة`` -> ``ه``   Ta-marbuta is **the primary feminine marker**. This is the
                 signal. ``حاصلة`` (f) vs ``حاصل`` (m) is the whole paper.
``أإآ`` -> ``ا`` Hamza forms carry lexical identity: ``أحمد``, ``إبراهيم``,
                 ``آدم``.
``ى`` -> ``ي``   Alef maqsura is contrastive.
diacritics       Architecture §3.2 requires them preserved. ``مُهَنْدِسَة``
                 must survive unchanged.
===============  ==========================================================

Guarded by fixtures O01 (ta-marbuta), O02 (hamza) and O03 (harakat) in
``tests/fixtures/tagger_fixtures.yaml``. Those tests must never be weakened or
skipped.
"""

from __future__ import annotations

import unicodedata

__all__ = ["normalise"]

#: Characters whose survival this module exists to guarantee. Used by the
#: defensive check below; the binding assertions live in the O0x fixtures.
_PROTECTED = (
    "ة"  # ة  ta-marbuta       — the primary feminine marker
    "أ"  # أ  alef with hamza above
    "إ"  # إ  alef with hamza below
    "آ"  # آ  alef with madda
    "ى"  # ى  alef maqsura
)


def normalise(text: str) -> str:
    """Return ``text`` under Unicode NFC. No other transformation is applied.

    NFC composes canonically-decomposed sequences and canonically orders
    combining marks. It does **not** fold ``ة`` to ``ه``, ``أ إ آ`` to ``ا``, or
    ``ى`` to ``ي``, and it does not remove diacritics — that is precisely why NFC
    is the only permitted normalisation.

    Examples
    --------
    >>> normalise("حاصلة على بكالوريوس هندسة")   # ta-marbuta survives (O01)
    'حاصلة على بكالوريوس هندسة'
    >>> normalise("أحمد إبراهيم آدم")            # hamza forms survive (O02)
    'أحمد إبراهيم آدم'
    >>> normalise("مُهَنْدِسَة")                      # harakat survive (O03)
    'مُهَنْدِسَة'

    Note on stacked diacritics
    --------------------------
    NFC canonically **reorders** combining marks by combining class. A base letter
    carrying more than one mark (shadda plus a vowel, say) may therefore come out
    in a different byte order than it went in, and that is correct behaviour, not
    a bug. O03 deliberately uses a token with one mark per base letter, so the
    question does not arise there. A stacked-mark fixture is still owed and its
    expected value must be author-supplied — see ADR 005.
    """
    nfc = unicodedata.normalize("NFC", text)
    normalised = nfc

    # Defensive, not decorative. If a future edit ever adds orthographic folding
    # below the NFC call, this fails loudly at the point of damage rather than
    # silently invalidating every downstream measurement.
    #
    # The baseline is the NFC form, NOT the raw input. NFC legitimately *composes*
    # decomposed sequences — bare alef + combining hamza above becomes أ — so
    # comparing against the raw input would flag correct behaviour as a violation.
    # Comparing against `nfc` isolates exactly the risk this guards: a
    # transformation applied after normalisation.
    for char in _PROTECTED:
        if nfc.count(char) != normalised.count(char):
            raise AssertionError(
                f"normalise() altered protected character {char!r} "
                f"({unicodedata.name(char)}): "
                f"{nfc.count(char)} -> {normalised.count(char)} after NFC. "
                f"This violates CLAUDE.md prohibition 1 and would invalidate "
                f"the study."
            )

    return normalised
