# Reproducibility Artifact

`run_fault_injection.py` compares sequential admission with the candidate
failure-atomic protocol. It uses fake local effects and does not touch files,
services, or networks.

`run_framework_prevalence.py` probes six pinned released Python surfaces with
the same valid-then-malformed action batch. It executes only in-memory test
tools.

Released outputs are under `artifact/results/`. Each framework result records
the package version, tested surface, source-relative path, and SHA-256 digest.
The complete installed environment is recorded in
`framework_prevalence_lock.txt`.

The deterministic harness is the primary reproducible artifact. The framework
probe is a bounded convenience sample and should not be interpreted as a
population estimate.
