from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_fault_result_matches_paper_claims() -> None:
    result = load_json("artifact/results/fault_injection.json")
    summary = result["summary"]
    assert summary["byte_fault_positions_tested"] == 107
    assert summary["byte_fault_baseline_partial_effect_count"] == 107
    assert summary["byte_fault_baseline_history_contamination_count"] == 107
    assert summary["byte_fault_candidate_partial_effect_count"] == 0
    assert summary["byte_fault_candidate_history_contamination_count"] == 0
    assert summary["candidate_content_retention_rate_content_then_malformed"] == 1.0
    assert summary["candidate_unknown_execution_truthful_rate"] == 1.0
    assert result["source_binding"]["repository_path"] == (
        "evidence/reference_runtime_ordering.py"
    )


def test_framework_result_matches_bounded_claim() -> None:
    result = load_json("artifact/results/framework_prevalence.json")
    assert result["framework_surfaces"] == 6
    assert result["vulnerable_partial_admission_count"] == 5
    assert result["structural_rejection_count"] == 1
    assert result["harness_error_count"] == 0
    assert result["claim_boundary"].startswith("Pinned released Python surfaces only.")
    assert "provider adapters remain unresolved" in result["claim_boundary"]
    for row in result["results"]:
        source = row["source_binding"]
        assert not source["package_relative_path"].startswith("/")
        assert len(source["sha256"]) == 64


@pytest.mark.parametrize(
    "name",
    [
        "admission_boundary",
        "protocol_state_machine",
        "fault_matrix",
        "framework_prevalence",
    ],
)
def test_publication_figures_exist_in_three_formats(name: str) -> None:
    for suffix in ("svg", "png", "pdf"):
        path = ROOT / "figures" / f"{name}.{suffix}"
        assert path.is_file()
        assert path.stat().st_size > 1_000


def test_manuscript_identity_and_claim_boundary() -> None:
    paper = (ROOT / "paper/paper.md").read_text(encoding="utf-8")
    assert "**Andrew Gracey**" in paper
    assert "Public artifact version 0.1.0" in paper
    assert "not an estimate over all framework deployments" in paper
    assert "does not make a sequence of valid external actions" in paper
    assert (ROOT / "paper/paper.pdf").stat().st_size > 50_000


def test_public_tree_has_no_private_absolute_paths() -> None:
    forbidden = (
        "/home/" + "plunder",
        "/tmp/" + "atomic-actuation",
        "Knight" + "2",
        "chat" + "ai2.py",
        "gracey_andrew" + "@yahoo.com",
    )
    suffixes = {".md", ".json", ".py", ".toml", ".yml", ".yaml", ".cff", ".txt"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix not in suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for value in forbidden:
            assert value not in text, f"{value!r} leaked through {path.relative_to(ROOT)}"


def test_license_mapping_and_citation() -> None:
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Attribution 4.0 International" in (
        ROOT / "LICENSES/CC-BY-4.0.txt"
    ).read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "family-names: Gracey" in citation
    assert "version: 0.1.0" in citation


def test_evidence_manifest_matches_files() -> None:
    manifest = load_json("evidence_manifest.json")
    assert manifest["version"] == "0.1.0"
    assert manifest["files"]
    for record in manifest["files"]:
        path = ROOT / record["path"]
        raw = path.read_bytes()
        assert len(raw) == record["bytes"]
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
