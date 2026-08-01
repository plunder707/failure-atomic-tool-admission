# Changelog

## 0.2.0 - 2026-08-01

- Added a stop-reason admission gate. Admission now requires a terminal finish
  reason in addition to full batch validation. Truncation is a property of the
  turn, not of the individual calls, so a parse-keyed gate alone admits batches
  that were cut on a valid structural boundary.
- Added the `boundary_truncation_all_parse` fault case, in which two complete
  calls carry a length finish reason and every frame parses. The sequential
  baseline executes both calls and records a completed turn with no error. The
  candidate admits nothing.
- Documented that the 107-position byte sweep cuts inside a single argument and
  therefore cannot generate a boundary truncation, which is why the case was
  absent from v0.1.0.
- Updated the abstract, threat model, admission condition, and protocol section
  to state the stop-reason gate separately from validation.
- Credited the public reviewer who identified the gap after v0.1.0.

## 0.1.2 - 2026-07-30

- Pinned Python 3.11.14 for exact local and GitHub framework replays.
- Kept the v0.1.1 behavior result and scientific claim boundary unchanged.
- Regenerated versioned release artifacts and metadata.

## 0.1.1 - 2026-07-30

- Preserved the deterministic 107-cut result while narrowing the ecosystem
  claim to observed behavior on exact tested surfaces.
- Replaced vulnerability language with neutral partial-admission terminology.
- Separated five executable paths from the non-comparable LlamaIndex typed
  construction boundary.
- Added adapter comparability metadata and intentional-semantics discussion.
- Added clean-environment replay evidence and byte-comparing framework CI.
- Regenerated the paper, figures, evidence manifest, and release metadata.

## 0.1.0 - 2026-07-30

- Published the initial manuscript and deterministic fault-injection artifact.
- Added exhaustive truncation at 107 nonterminal byte positions.
- Added the initial six-surface framework probe.
- Added publication figures in SVG, PNG, and PDF formats.
- Added a reproducible manuscript build and evidence manifest.
- Added explicit authorship, citation, and dual-license metadata.
