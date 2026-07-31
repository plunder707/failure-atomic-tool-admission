# Reproducibility Artifact

`run_fault_injection.py` compares sequential admission with the candidate
failure-atomic protocol. It uses fake local effects and does not touch files,
services, or networks.

`run_framework_surface_probe.py` probes five pinned executable paths with the
same valid-then-malformed action batch. It also records one separately
interpreted LlamaIndex typed-boundary result. It executes only in-memory test
tools.

Released outputs are under `artifact/results/`. Each framework result records
the package version, tested surface, source-relative path, SHA-256 digest,
injection boundary, API status, malformed-input representability, state
location, and replay-authority boundary. The complete installed environment is
recreated from `framework_surface_probe_lock.txt`. The smaller
`framework_surface_probe_requirements.txt` is for fresh-resolution compatibility
testing, not exact replay.

`results/framework_surface_probe_replay_receipt.json` is written only after the
installed packages match the lock, the probe exits successfully, and its
temporary output matches the committed result byte-for-byte. The receipt binds
the requirements, resolved environment, probe source, reference output, and
ephemeral replay digest.

The deterministic harness is the primary reproducible artifact. The framework
probe is a bounded convenience sample. It reports observed behavior and should
not be interpreted as a population estimate or vulnerability determination.
