# Release v0.2.2

This release adds a bounded terminator-last experiment while preserving the
deployed completion-aware admission gate from v0.2.1.

## Terminator-Last Experiment

The stop reason remains the primary runtime signal. A provider can, however,
report a terminal stop for a well-formed response that contains only a prefix
of the intended calls. The new experimental arm requires the action list to end
with a non-executable `__batch_complete__` frame.

The deterministic result separates three cases:

- a terminal, well-formed suffix cut is rejected because the terminator is
  absent;
- a complete but noncompliant batch is also rejected, making the false-reject
  tradeoff explicit;
- a silently omitted interior action remains undetectable when the terminator
  survives.

The experiment therefore detects suffix completeness, not model-intent
completeness. It is not deployed as a production requirement.

## Corrected Admission Condition

`v0.2.0` rejected `finish_reason=length`, closing the silent boundary-cut case.
The production implementation revealed the stricter condition the protocol
actually needs:

```text
admit(A) iff F is a recognized terminal reason AND every V(a_i) passes
```

The production candidate recognizes `stop` and `tool_calls` as terminal. Unknown,
missing, and output-limit finish reasons fail closed. A new deterministic case
contains two fully valid calls with an unknown finish reason. The sequential
baseline executes both calls; the candidate admits neither.

## Production-Bound Evidence

`artifact/results/production_admission_canary.json` records three canary cases
against the deployed streaming adapter and admission policy:

- valid prefix plus malformed sibling: rejected, zero fixture effects;
- two complete calls plus `finish_reason=length`: rejected, zero fixture effects;
- complete terminal two-call batch: accepted, two fixture effects.

A separate live read-only request recorded one admitted call and one dispatched
call. The focused regression set passed 310 tests. A 20,000-iteration local
microbenchmark measured about 31.5 microseconds per valid two-call admission
decision.

The private application runtime is not distributed. The receipt binds the
tested source snapshot and upstream canary by commit and SHA-256. This moves the
claim beyond a reference harness, but it is not exhaustive live-model fault
replay and does not establish recovery quality across long tasks.

## Preserved Results

- 107 of 107 nonterminal byte cuts caused partial effects in the sequential
  baseline; zero did so under failure-atomic admission.
- All five pinned executable framework paths tested showed partial admission.
- The separately tested LlamaIndex typed core rejected raw malformed arguments;
  provider-adapter behavior remains unresolved.

No framework is classified as vulnerable. The observed behavior may reflect an
intentional per-call contract, and the probe remains a bounded convenience
sample rather than an ecosystem prevalence estimate.
