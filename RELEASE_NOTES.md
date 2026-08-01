# Release v0.2.0

This release adds a stop-reason admission gate. Admission now requires a
terminal finish reason in addition to full batch validation.

## What Changed

Validation alone is not sufficient. Generation can stop at the output limit on
a valid structural boundary, between two complete calls rather than inside one.
Every surviving frame then parses, no parser reports a fault, and a gate keyed
only on validation admits a batch the model had not finished proposing.

The sequential baseline executes both calls and records a completed turn with
no error, which makes this case silent rather than loud. It is more dangerous
than the parse failure the original release described.

The admission condition is now `F != length AND all V(a_i)`. Validation still
runs on truncated turns so the admission record keeps frame-level diagnostics.

The `boundary_truncation_all_parse` fault case covers it. The 107-position byte
sweep could not have produced it, because that sweep cuts inside a single
argument and never between calls. That limitation is now stated in the paper.

This gap was identified by a public reviewer after v0.1.0 and is credited in
the manuscript acknowledgements.

## Primary Result

A sequential tool executor produced a partial effect and malformed executable
history at every one of 107 nonterminal truncation positions. Whole-batch
prevalidation reduced both counts to zero while preserving completed narrative
content. Deterministic case count is now 10.

## Framework-Surface Probe

All five pinned executable paths tested partially admitted one valid call
paired with malformed JSON. A separately tested LlamaIndex typed core boundary
structurally rejected raw malformed arguments. It is not part of the same
denominator, and LlamaIndex provider-adapter behavior remains unresolved.

The probe reports exact source-bound behavior. It does not determine whether
per-call partial success is intended, defective, or exploitable. Several tested
paths are internal, and the CrewAI path is deprecated.

## Changes From v0.1.1

- Pinned Python 3.11.14 in the exact replay instructions and GitHub workflow.
- Preserved the environment lock, source bindings, and result bytes from
  v0.1.1.
- Regenerated versioned manuscript, figures, manifest, receipt, and citation
  metadata.

v0.1.1 remains the claim-correction release. It replaced vulnerability
terminology, fixed the non-comparable denominator, documented alternative
per-call semantics, and introduced the mechanically earned replay receipt.

## Evidence Boundary

The release contains an isolated deterministic counterexample, not a completed
production-runtime evaluation. It does not claim arbitrary rollback or
ecosystem-wide prevalence. It does not classify any tested framework as a
security vulnerability.
