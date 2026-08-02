#!/usr/bin/env python3
"""Compare sequential parsing with failure-atomic tool admission.

The baseline mirrors the source-bound public reconstruction in
``evidence/reference_runtime_ordering.py``: append the assistant response,
then parse and execute each tool call in sequence. The candidate validates the
complete batch before admitting any tool call to history or dispatch.

This harness does not claim to be an end-to-end runtime evaluation. It isolates
the admission boundary and deterministically exercises its invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


TERMINAL_FINISH_REASONS = frozenset({"stop", "tool_calls"})
BATCH_TERMINATOR_NAME = "__batch_complete__"
BATCH_TERMINATOR_VERSION = 1


class AmbiguousExecutionError(RuntimeError):
    """The action may have committed before its acknowledgement failed."""


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str | None
    arguments: str | None


@dataclass(frozen=True)
class AssistantResponse:
    content: str
    finish_reason: str
    tool_calls: tuple[ToolCall, ...]


@dataclass
class AdmissionRecord:
    state: str
    batch_hash: str
    batch_width: int
    admitted_calls: int = 0
    committed_calls: int = 0
    unknown_calls: int = 0
    malformed_call_index: int | None = None
    error_position: int | None = None
    error_kind: str | None = None
    preserved_content: bool = False
    malformed_payload_in_history: bool = False
    recovery_message: str = ""
    escalation: str = ""


@dataclass
class RunState:
    history: list[dict[str, Any]] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    record: AdmissionRecord | None = None
    crashed: bool = False
    exception: str | None = None


def batch_hash(response: AssistantResponse) -> str:
    payload = {
        "finish_reason": response.finish_reason,
        "tool_calls": [asdict(call) for call in response.tool_calls],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def response_for_history(response: AssistantResponse) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": call.call_id,
                "function": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
            }
            for call in response.tool_calls
        ],
    }


def content_only_history(response: AssistantResponse) -> dict[str, Any]:
    return {"role": "assistant", "content": response.content}


def parse_call(call: ToolCall) -> tuple[str, dict[str, Any]]:
    if not call.call_id:
        raise ValueError("missing_call_id")
    if not isinstance(call.name, str) or not call.name:
        raise ValueError("missing_tool_name")
    if not isinstance(call.arguments, str):
        raise ValueError("arguments_not_string")
    decoded = json.loads(call.arguments)
    if not isinstance(decoded, dict):
        raise TypeError("arguments_not_object")
    return call.name, decoded


def make_executor(
    effects: list[str],
    ambiguous_names: frozenset[str] = frozenset(),
) -> Callable[[str, dict[str, Any]], None]:
    def execute(name: str, args: dict[str, Any]) -> None:
        effects.append(f"{name}:{json.dumps(args, sort_keys=True)}")
        if name in ambiguous_names:
            raise AmbiguousExecutionError(f"acknowledgement_lost:{name}")

    return execute


def run_sequential_baseline(
    response: AssistantResponse,
    *,
    ambiguous_names: frozenset[str] = frozenset(),
) -> RunState:
    """Mirror history admission followed by sequential parse and dispatch."""

    state = RunState()
    state.history.append(response_for_history(response))
    execute = make_executor(state.effects, ambiguous_names)
    try:
        for call in response.tool_calls:
            name, args = parse_call(call)
            execute(name, args)
    except Exception as exc:  # The baseline incident escaped the tool loop.
        state.crashed = True
        state.exception = f"{type(exc).__name__}:{exc}"
    state.record = AdmissionRecord(
        state="crashed" if state.crashed else "completed",
        batch_hash=batch_hash(response),
        batch_width=len(response.tool_calls),
        admitted_calls=len(response.tool_calls),
        committed_calls=len(state.effects),
        malformed_payload_in_history=bool(state.crashed and response.tool_calls),
        preserved_content=bool(response.content),
    )
    return state


def _validation_failure_record(
    response: AssistantResponse,
    *,
    index: int,
    exc: Exception,
) -> AdmissionRecord:
    position = exc.pos if isinstance(exc, json.JSONDecodeError) else None
    return AdmissionRecord(
        state="rejected",
        batch_hash=batch_hash(response),
        batch_width=len(response.tool_calls),
        malformed_call_index=index,
        error_position=position,
        error_kind=type(exc).__name__,
        preserved_content=bool(response.content),
        recovery_message=(
            "The previous action batch was rejected before admission. "
            "No action from that batch was dispatched. Reissue a complete "
            "action batch if the operation is still required."
        ),
    )


def run_failure_atomic_candidate(
    response: AssistantResponse,
    *,
    ambiguous_names: frozenset[str] = frozenset(),
    prior_failed_hashes: tuple[str, ...] = (),
    max_identical_failures: int = 2,
) -> RunState:
    """Validate the complete batch before history admission or dispatch.

    Admission requires a terminal stop reason AND a fully valid batch.
    Validation alone is not sufficient. Truncation is a property of the turn,
    not of the individual calls: generation can stop on a valid structural
    boundary, in which case every surviving call parses and a parse-keyed gate
    admits a silently incomplete plan. Only the stop reason distinguishes a
    finished batch from a cut one.
    """

    state = RunState()
    truncated = response.finish_reason == "length"
    nonterminal = response.finish_reason not in TERMINAL_FINISH_REASONS

    # Validation still runs when the turn is truncated, so the record keeps the
    # frame-level diagnostics. Only the admission decision short-circuits.
    parsed: list[tuple[str, dict[str, Any]]] = []
    record: AdmissionRecord | None = None
    for index, call in enumerate(response.tool_calls):
        try:
            parsed.append(parse_call(call))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            record = _validation_failure_record(response, index=index, exc=exc)
            break

    if record is None and nonterminal:
        # Every frame parsed but the runtime has no recognized terminal signal.
        # Without that signal this is indistinguishable from an incomplete batch.
        error_kind = "TruncatedTurn" if truncated else "NonterminalTurn"
        record = AdmissionRecord(
            state="rejected",
            batch_hash=batch_hash(response),
            batch_width=len(response.tool_calls),
            error_kind=error_kind,
            recovery_message=(
                "Generation did not end with a recognized terminal signal, so "
                "the action batch may be incomplete. No operation was admitted. "
                "Reissue the intended operations as one complete batch."
            ),
        )

    if record is not None:
        if truncated:
            record.error_kind = record.error_kind or "TruncatedTurn"
        record.preserved_content = bool(response.content)
        if response.content:
            state.history.append(content_only_history(response))
        identical_failures = (
            sum(1 for digest in prior_failed_hashes if digest == record.batch_hash) + 1
        )
        if identical_failures >= max_identical_failures:
            record.escalation = "require_smaller_complete_calls"
            record.recovery_message = (
                "The same invalid action batch was rejected again before "
                "admission. Reissue the operation as smaller complete calls."
            )
        state.record = record
        return state

    state.history.append(response_for_history(response))
    state.record = AdmissionRecord(
        state="admitted",
        batch_hash=batch_hash(response),
        batch_width=len(response.tool_calls),
        admitted_calls=len(parsed),
        preserved_content=bool(response.content),
    )
    execute = make_executor(state.effects, ambiguous_names)
    for name, args in parsed:
        try:
            execute(name, args)
            state.record.committed_calls += 1
        except AmbiguousExecutionError as exc:
            state.record.state = "execution_unknown"
            state.record.unknown_calls += 1
            state.exception = f"{type(exc).__name__}:{exc}"
            state.record.recovery_message = (
                "An admitted action has unknown execution state. Do not repeat "
                "it automatically. Inspect the target system before deciding "
                "whether another action is safe."
            )
            return state
        except Exception as exc:
            state.record.state = "execution_failed"
            state.exception = f"{type(exc).__name__}:{exc}"
            state.record.recovery_message = (
                "An admitted action failed during execution. Previously "
                "committed actions remain committed."
            )
            return state
    state.record.state = "completed"
    return state


def run_terminator_candidate(
    response: AssistantResponse,
    *,
    ambiguous_names: frozenset[str] = frozenset(),
) -> RunState:
    """Experimental suffix-completeness gate using a terminator-last frame.

    This detects a well-formed prefix whose suffix, including the terminator,
    was removed even if a provider reports a terminal stop. It cannot prove
    intent completeness when an interior action is silently omitted but the
    terminator survives.
    """

    full_hash = batch_hash(response)
    if not response.tool_calls or response.tool_calls[-1].name != BATCH_TERMINATOR_NAME:
        state = RunState()
        if response.content:
            state.history.append(content_only_history(response))
        state.record = AdmissionRecord(
            state="rejected",
            batch_hash=full_hash,
            batch_width=len(response.tool_calls),
            error_kind="MissingBatchTerminator",
            preserved_content=bool(response.content),
            recovery_message=(
                "The action batch did not end with its required completion "
                "terminator. No action was admitted."
            ),
        )
        return state

    terminator = response.tool_calls[-1]
    try:
        name, arguments = parse_call(terminator)
        if name != BATCH_TERMINATOR_NAME:
            raise ValueError("invalid_batch_terminator_name")
        if arguments != {"version": BATCH_TERMINATOR_VERSION}:
            raise ValueError("invalid_batch_terminator_payload")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        state = RunState()
        if response.content:
            state.history.append(content_only_history(response))
        state.record = _validation_failure_record(
            response,
            index=len(response.tool_calls) - 1,
            exc=exc,
        )
        state.record.error_kind = "InvalidBatchTerminator"
        return state

    action_response = AssistantResponse(
        content=response.content,
        finish_reason=response.finish_reason,
        tool_calls=response.tool_calls[:-1],
    )
    state = run_failure_atomic_candidate(
        action_response,
        ambiguous_names=ambiguous_names,
    )
    assert state.record is not None
    state.record.batch_hash = full_hash
    state.record.batch_width = len(response.tool_calls)
    return state


VALID_A = ToolCall("call-a", "write_file", '{"path":"a","content":"A"}')
VALID_B = ToolCall("call-b", "write_file", '{"path":"b","content":"B"}')
MALFORMED = ToolCall("call-bad", "write_file", '{"path":"broken","content":"')
SCALAR_ARGS = ToolCall("call-scalar", "write_file", '"not-an-object"')
MISSING_NAME = ToolCall("call-name", None, "{}")
AMBIGUOUS = ToolCall("call-unknown", "network_write", '{"target":"remote"}')
BATCH_TERMINATOR = ToolCall(
    "batch-end",
    BATCH_TERMINATOR_NAME,
    json.dumps({"version": BATCH_TERMINATOR_VERSION}, separators=(",", ":")),
)


CASES: dict[str, AssistantResponse] = {
    "malformed_only_length": AssistantResponse("", "length", (MALFORMED,)),
    "valid_then_malformed": AssistantResponse("", "length", (VALID_A, MALFORMED)),
    "malformed_then_valid": AssistantResponse("", "length", (MALFORMED, VALID_A)),
    "two_valid_calls": AssistantResponse("", "tool_calls", (VALID_A, VALID_B)),
    "content_then_malformed": AssistantResponse(
        "The audit found a reproducible boundary failure.",
        "length",
        (MALFORMED,),
    ),
    "scalar_arguments": AssistantResponse("", "tool_calls", (SCALAR_ARGS,)),
    "missing_tool_name": AssistantResponse("", "tool_calls", (MISSING_NAME,)),
    "malformed_non_length": AssistantResponse("", "tool_calls", (MALFORMED,)),
    # Boundary truncation. Generation stopped at the output limit between two
    # complete calls, so every surviving call parses and no parser reports a
    # fault. A validation-keyed gate admits this batch and silently executes a
    # plan the model had not finished proposing. Reported by a public reviewer
    # after v0.1.0; see CHANGELOG.
    "boundary_truncation_all_parse": AssistantResponse(
        "", "length", (VALID_A, VALID_B)
    ),
    "unknown_finish_all_parse": AssistantResponse(
        "", "transport_unknown", (VALID_A, VALID_B)
    ),
    "ambiguous_after_dispatch": AssistantResponse(
        "Submitting the remote update.",
        "tool_calls",
        (AMBIGUOUS,),
    ),
}


def summarize_state(state: RunState) -> dict[str, Any]:
    assert state.record is not None
    return {
        "crashed": state.crashed,
        "exception": state.exception,
        "history_entries": len(state.history),
        "effects": list(state.effects),
        "record": asdict(state.record),
    }


def _run_byte_position_faults() -> dict[str, Any]:
    """Cut one representative argument at every nonterminal byte position."""
    complete = (
        '{"path":"artifact.txt","content":"Alpha beta with an escaped '
        'quote \\" and newline \\\\n tail","mode":"append"}'
    ).encode("utf-8")
    trials: list[dict[str, Any]] = []
    for cut_position in range(1, len(complete)):
        prefix = complete[:cut_position].decode("utf-8")
        response = AssistantResponse(
            "",
            "length",
            (
                VALID_A,
                ToolCall("byte-cut", "write_file", prefix),
            ),
        )
        baseline = run_sequential_baseline(response)
        candidate = run_failure_atomic_candidate(response)
        trials.append({
            "cut_position": cut_position,
            "argument_bytes": len(complete),
            "baseline": summarize_state(baseline),
            "candidate": summarize_state(candidate),
        })
    return {
        "argument_sha256": hashlib.sha256(complete).hexdigest(),
        "argument_bytes": len(complete),
        "cut_positions_tested": len(trials),
        "baseline_partial_effect_count": sum(
            1 for trial in trials if trial["baseline"]["effects"]
        ),
        "baseline_history_contamination_count": sum(
            1
            for trial in trials
            if trial["baseline"]["record"]["malformed_payload_in_history"]
        ),
        "candidate_partial_effect_count": sum(
            1 for trial in trials if trial["candidate"]["effects"]
        ),
        "candidate_history_contamination_count": sum(
            1
            for trial in trials
            if trial["candidate"]["record"]["malformed_payload_in_history"]
        ),
        "trials": trials,
    }


def run_experiment(source_path: Path) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    trials: list[dict[str, Any]] = []
    for case_name, response in CASES.items():
        ambiguous = (
            frozenset({"network_write"})
            if case_name == "ambiguous_after_dispatch"
            else frozenset()
        )
        baseline = run_sequential_baseline(
            response, ambiguous_names=ambiguous
        )
        candidate = run_failure_atomic_candidate(
            response, ambiguous_names=ambiguous
        )
        trials.append(
            {
                "case": case_name,
                "baseline": summarize_state(baseline),
                "candidate": summarize_state(candidate),
            }
        )

    repeated_response = CASES["malformed_only_length"]
    first = run_failure_atomic_candidate(repeated_response)
    assert first.record is not None
    second = run_failure_atomic_candidate(
        repeated_response,
        prior_failed_hashes=(first.record.batch_hash,),
    )
    trials.append(
        {
            "case": "identical_retry_escalation",
            "baseline": None,
            "candidate": summarize_state(second),
        }
    )

    malformed_cases = {
        "malformed_only_length",
        "valid_then_malformed",
        "malformed_then_valid",
        "content_then_malformed",
        "scalar_arguments",
        "missing_tool_name",
        "malformed_non_length",
    }
    candidate_malformed_trials = [
        trial
        for trial in trials
        if trial["case"] in malformed_cases
    ]
    baseline_malformed_trials = [
        trial
        for trial in trials
        if trial["case"] in malformed_cases
    ]
    valid_then_malformed = [
        trial for trial in trials if trial["case"] == "valid_then_malformed"
    ]
    content_then_malformed = [
        trial for trial in trials if trial["case"] == "content_then_malformed"
    ]
    ambiguous_trials = [
        trial for trial in trials if trial["case"] == "ambiguous_after_dispatch"
    ]

    byte_position_faults = _run_byte_position_faults()
    summary = {
        "deterministic_case_count": len(CASES),
        "trial_count": len(trials),
        "baseline_malformed_crash_rate": (
            sum(1 for t in baseline_malformed_trials if t["baseline"]["crashed"])
            / len(baseline_malformed_trials)
        ),
        "baseline_malformed_history_contamination_rate": (
            sum(
                1
                for t in baseline_malformed_trials
                if t["baseline"]["record"]["malformed_payload_in_history"]
            )
            / len(baseline_malformed_trials)
        ),
        "baseline_partial_effect_rate_valid_then_malformed": (
            sum(1 for t in valid_then_malformed if t["baseline"]["effects"])
            / len(valid_then_malformed)
        ),
        "candidate_malformed_crash_rate": (
            sum(1 for t in candidate_malformed_trials if t["candidate"]["crashed"])
            / len(candidate_malformed_trials)
        ),
        "candidate_malformed_history_contamination_rate": (
            sum(
                1
                for t in candidate_malformed_trials
                if t["candidate"]["record"]["malformed_payload_in_history"]
            )
            / len(candidate_malformed_trials)
        ),
        "candidate_partial_effect_rate_valid_then_malformed": (
            sum(1 for t in valid_then_malformed if t["candidate"]["effects"])
            / len(valid_then_malformed)
        ),
        "candidate_content_retention_rate_content_then_malformed": (
            sum(
                1
                for t in content_then_malformed
                if t["candidate"]["record"]["preserved_content"]
                and t["candidate"]["history_entries"] == 1
            )
            / len(content_then_malformed)
        ),
        "candidate_unknown_execution_truthful_rate": (
            sum(
                1
                for t in ambiguous_trials
                if t["candidate"]["record"]["state"] == "execution_unknown"
                and "unknown execution state"
                in t["candidate"]["record"]["recovery_message"]
            )
            / len(ambiguous_trials)
        ),
        "candidate_identical_retry_escalated": (
            second.record is not None
            and second.record.escalation == "require_smaller_complete_calls"
        ),
        "byte_fault_positions_tested": byte_position_faults[
            "cut_positions_tested"
        ],
        "byte_fault_baseline_partial_effect_count": byte_position_faults[
            "baseline_partial_effect_count"
        ],
        "byte_fault_candidate_partial_effect_count": byte_position_faults[
            "candidate_partial_effect_count"
        ],
        "byte_fault_baseline_history_contamination_count": byte_position_faults[
            "baseline_history_contamination_count"
        ],
        "byte_fault_candidate_history_contamination_count": byte_position_faults[
            "candidate_history_contamination_count"
        ],
    }
    return {
        "format": "tool_admission_atomicity_fault_injection/v2",
        "source_binding": {
            "repository_path": source_path.relative_to(
                Path(__file__).resolve().parents[1]
            ).as_posix(),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "baseline_ordering": [
                "assistant_history_append",
                "per_call_json_parse",
                "per_call_dispatch",
            ],
        },
        "scope": {
            "claim": "admission-boundary fault isolation",
            "end_to_end_runtime_evaluation": False,
            "model_quality_evaluation": False,
            "universal_side_effect_rollback": False,
        },
        "summary": summary,
        "trials": trials,
        "byte_position_faults": byte_position_faults,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "evidence"
            / "reference_runtime_ordering.py"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "results"
            / "fault_injection.json"
        ),
    )
    args = parser.parse_args()
    payload = run_experiment(args.source.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
