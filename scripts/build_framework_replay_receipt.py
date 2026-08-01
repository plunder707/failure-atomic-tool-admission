#!/usr/bin/env python3
"""Replay the framework probe and write a mechanically earned receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "artifact/results/framework_surface_probe_replay_receipt.json"
)
REFERENCE_RESULT = ROOT / "artifact/results/framework_surface_probe.json"
PROBE = ROOT / "artifact/run_framework_surface_probe.py"
LOCK = ROOT / "artifact/framework_surface_probe_lock.txt"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def binding(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    raw = path.read_bytes()
    return {
        "path": relative_path,
        "bytes": len(raw),
        "sha256": digest(raw),
    }


def parse_lock() -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator:
            raise SystemExit(f"unsupported lock entry: {line}")
        packages[name] = version
    return packages


def installed_packages(python: Path) -> dict[str, str]:
    code = """
import json
from importlib.metadata import distributions

def normalize(name):
    return name.lower().replace("_", "-").replace(".", "-")

packages = {
    normalize(dist.metadata["Name"]): dist.version
    for dist in distributions()
    if dist.metadata["Name"]
}
print(json.dumps(packages, sort_keys=True))
"""
    completed = subprocess.run(
        [str(python), "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "failed to inspect replay environment: "
            f"exit={completed.returncode} stderr={completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def verify_environment(python: Path) -> None:
    expected = parse_lock()
    actual = installed_packages(python)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(
            name
            for name in set(actual) & set(expected)
            if actual[name] != expected[name]
        )
        raise SystemExit(
            "replay environment does not match the resolved lock: "
            f"missing={missing} extra={extra} changed={changed}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python",
        type=Path,
        default=ROOT / ".venv-frameworks/bin/python",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    # Preserve the virtual-environment path. Resolving the interpreter symlink
    # would invoke the base Python and inspect the wrong environment.
    python = args.python.absolute()
    if not python.is_file():
        raise SystemExit(
            f"framework replay interpreter not found: {args.python}\n"
            "Create it from artifact/framework_surface_probe_lock.txt."
        )
    verify_environment(python)

    reference_raw = REFERENCE_RESULT.read_bytes()
    with tempfile.TemporaryDirectory(prefix="framework-surface-probe-") as tmp:
        candidate_path = Path(tmp) / "framework_surface_probe.json"
        completed = subprocess.run(
            [
                str(python),
                str(PROBE),
                "--output",
                str(candidate_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise SystemExit(
                "framework replay failed: "
                f"exit={completed.returncode} stderr={completed.stderr.strip()}"
            )
        candidate_raw = candidate_path.read_bytes()
        if candidate_raw != reference_raw:
            raise SystemExit(
                "framework replay differs from committed result: "
                f"reference={digest(reference_raw)} "
                f"candidate={digest(candidate_raw)}"
            )

    result = json.loads(reference_raw)
    payload = {
        "format": "framework_surface_probe_replay_receipt/v2",
        "release": "0.2.1",
        "replay_date": "2026-07-30",
        "verification": {
            "mode": "subprocess_replay_then_byte_compare",
            "probe_exit_status": completed.returncode,
            "environment_lock_match": True,
            "result_byte_match": True,
            "candidate_output": {
                "ephemeral": True,
                "bytes": len(candidate_raw),
                "sha256": digest(candidate_raw),
            },
            "reference_output": binding(
                "artifact/results/framework_surface_probe.json"
            ),
        },
        "environment": {
            "python": result["environment"]["python"],
            "platform": result["environment"]["platform"],
            "interpreter_label": args.python.as_posix(),
            "install_command": (
                "uv pip sync --python .venv-frameworks/bin/python "
                "artifact/framework_surface_probe_lock.txt"
            ),
            "replay_command": (
                "make framework-probe-verify "
                "FRAMEWORK_PYTHON=.venv-frameworks/bin/python"
            ),
        },
        "bindings": {
            "requirements": binding(
                "artifact/framework_surface_probe_requirements.txt"
            ),
            "resolved_environment": binding(
                "artifact/framework_surface_probe_lock.txt"
            ),
            "probe": binding("artifact/run_framework_surface_probe.py"),
        },
        "summary": {
            key: result[key]
            for key in (
                "surfaces_total",
                "executable_paths_tested",
                "partial_admission_observed_count",
                "typed_core_boundaries_tested",
                "typed_core_structural_rejection_count",
                "harness_error_count",
            )
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
