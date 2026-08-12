"""Model loading and disambiguation. I/O layer — does **not** enter the freeze.

ADR 007 splits the tagger along the I/O boundary. This package loads
``BERTUnfactoredDisambiguator`` and the morphology database; all classification
logic lives in ``arabgn/analysis/``, which takes analyses as data and needs no
model.

Model identity is pinned by ``toolkit_version`` and ``db_version`` recorded on
every emitted ``TaggedCue``, so provenance travels with the data rather than only
with a source hash.

Anything here requires ``camel_data`` — see CLAUDE.md. Tests exercising this
package are marked ``needs_camel_data``.
"""
