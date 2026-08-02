#!/usr/bin/env python3
"""Measure what a terminator-last action protocol can and cannot detect."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from artifact.run_fault_injection import (  # noqa: E402
    AssistantResponse,
    BATCH_TERMINATOR,
    MALFORMED,
    VALID_A,
    VALID_B,
    run_failure_atomic_candidate,
    run_sequential_baseline,
    run_terminator_candidate,
    summarize_state,
)


CASES: dict[str, dict[str, Any]] = {
    "complete_compliant_batch": {
        "response": AssistantResponse(
            "", "tool_calls", (VALID_A, VALID_B, BATCH_TERMINATOR)
        ),
        "expected": "accept_two_actions",
    },
    "well_formed_suffix_cut_terminal_stop": {
        "response": AssistantResponse("", "tool_calls", (VALID_A,)),
        "expected": "reject_missing_terminator",
    },
    "complete_noncompliant_batch": {
        "response": AssistantResponse("", "tool_calls", (VALID_A, VALID_B)),
        "expected": "false_reject_without_terminator",
    },
    "middle_action_silently_omitted": {
        "response": AssistantResponse("", "tool_calls", (VALID_A, BATCH_TERMINATOR)),
        "expected": "undetectable_accept_one_action",
    },
    "nonterminal_with_terminator": {
        "response": AssistantResponse("", "length", (VALID_A, BATCH_TERMINATOR)),
        "expected": "reject_nonterminal_stop",
    },
    "malformed_action_with_terminator": {
        "response": AssistantResponse(
            "", "tool_calls", (VALID_A, MALFORMED, BATCH_TERMINATOR)
        ),
        "expected": "reject_malformed_batch",
    },
}


def run_experiment() -> dict[str, Any]:
    rows = []
    for name, case in CASES.items():
        response = case["response"]
        rows.append(
            {
                "case": name,
                "expected": case["expected"],
                "sequential_baseline": summarize_state(run_sequential_baseline(response)),
                "terminal_reason_candidate": summarize_state(
                    run_failure_atomic_candidate(response)
                ),
                "terminator_candidate": summarize_state(run_terminator_candidate(response)),
            }
        )
    by_name = {row["case"]: row for row in rows}
    return {
        "format": "tool_admission_terminator_experiment/v1",
        "protocol": {
            "terminator_name": BATCH_TERMINATOR.name,
            "terminator_arguments": BATCH_TERMINATOR.arguments,
            "position": "last",
            "status": "experimental_not_production_required",
        },
        "findings": {
            "well_formed_suffix_cut_detected": (
                by_name["well_formed_suffix_cut_terminal_stop"]["terminator_candidate"]
                ["record"]["state"]
                == "rejected"
            ),
            "middle_omission_detected": False,
            "noncompliant_complete_batch_false_rejected": (
                by_name["complete_noncompliant_batch"]["terminator_candidate"]
                ["record"]["state"]
                == "rejected"
            ),
            "stop_reason_still_required": (
                by_name["nonterminal_with_terminator"]["terminator_candidate"]
                ["record"]["state"]
                == "rejected"
            ),
        },
        "claim_boundary": (
            "A terminator-last frame detects suffix loss, including a well-formed prefix "
            "paired with a terminal provider stop. It does not establish intent "
            "completeness when an interior action is omitted and the terminator survives."
        ),
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "terminator_experiment.json",
    )
    args = parser.parse_args()
    payload = run_experiment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["findings"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
