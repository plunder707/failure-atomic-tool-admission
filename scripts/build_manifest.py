#!/usr/bin/env python3
"""Build a deterministic SHA-256 manifest of release evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence_manifest.json"
INCLUDED = (
    "artifact/results/*.json",
    "evidence/*.md",
    "evidence/*.py",
    "figures/*.pdf",
    "figures/*.png",
    "figures/*.svg",
    "paper/paper.md",
    "paper/paper.pdf",
    "paper/references.bib",
)


def main() -> None:
    paths: set[Path] = set()
    for pattern in INCLUDED:
        paths.update(ROOT.glob(pattern))
    records = []
    for path in sorted(paths):
        raw = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    payload = {
        "format": "failure_atomic_tool_admission_manifest/v1",
        "version": "0.2.0",
        "files": records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT} ({len(records)} files)")


if __name__ == "__main__":
    main()
