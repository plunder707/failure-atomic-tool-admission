from artifact.run_fault_injection import (
    AssistantResponse,
    BATCH_TERMINATOR,
    MALFORMED,
    VALID_A,
    _run_byte_position_faults,
    run_failure_atomic_candidate,
    run_sequential_baseline,
    run_terminator_candidate,
)


def test_candidate_rejects_whole_batch_before_any_effect() -> None:
    response = AssistantResponse("", "length", (VALID_A, MALFORMED))

    baseline = run_sequential_baseline(response)
    candidate = run_failure_atomic_candidate(response)

    assert baseline.crashed is True
    assert len(baseline.effects) == 1
    assert candidate.crashed is False
    assert candidate.effects == []
    assert candidate.record is not None
    assert candidate.record.state == "rejected"
    assert candidate.record.admitted_calls == 0


def test_candidate_preserves_content_without_malformed_action_frame() -> None:
    response = AssistantResponse(
        "The completed analysis remains useful.",
        "length",
        (MALFORMED,),
    )

    candidate = run_failure_atomic_candidate(response)

    assert candidate.history == [
        {"role": "assistant", "content": "The completed analysis remains useful."}
    ]
    assert candidate.record is not None
    assert candidate.record.preserved_content is True
    assert candidate.record.malformed_payload_in_history is False


def test_identical_retry_escalates_to_smaller_complete_calls() -> None:
    response = AssistantResponse("", "length", (MALFORMED,))
    first = run_failure_atomic_candidate(response)
    assert first.record is not None

    second = run_failure_atomic_candidate(
        response,
        prior_failed_hashes=(first.record.batch_hash,),
    )

    assert second.record is not None
    assert second.record.escalation == "require_smaller_complete_calls"
    assert "smaller complete calls" in second.record.recovery_message


def test_valid_batch_is_admitted_and_executed_in_order() -> None:
    response = AssistantResponse(
        "",
        "tool_calls",
        (
            VALID_A,
            type(VALID_A)("call-b", "write_file", '{"path":"b","content":"B"}'),
        ),
    )

    candidate = run_failure_atomic_candidate(response)

    assert candidate.record is not None
    assert candidate.record.state == "completed"
    assert candidate.record.admitted_calls == 2
    assert candidate.record.committed_calls == 2
    assert len(candidate.effects) == 2


def test_unknown_finish_reason_rejects_fully_parseable_batch() -> None:
    response = AssistantResponse("", "transport_unknown", (VALID_A,))

    candidate = run_failure_atomic_candidate(response)

    assert candidate.effects == []
    assert candidate.history == []
    assert candidate.record is not None
    assert candidate.record.state == "rejected"
    assert candidate.record.error_kind == "NonterminalTurn"


def test_every_nonterminal_argument_byte_cut_is_failure_atomic() -> None:
    result = _run_byte_position_faults()

    assert result["cut_positions_tested"] == result["argument_bytes"] - 1
    assert result["baseline_partial_effect_count"] == result["cut_positions_tested"]
    assert (
        result["baseline_history_contamination_count"]
        == result["cut_positions_tested"]
    )
    assert result["candidate_partial_effect_count"] == 0
    assert result["candidate_history_contamination_count"] == 0


def test_terminator_rejects_well_formed_prefix_with_terminal_stop() -> None:
    response = AssistantResponse("", "tool_calls", (VALID_A,))

    terminal_reason_only = run_failure_atomic_candidate(response)
    terminator = run_terminator_candidate(response)

    assert len(terminal_reason_only.effects) == 1
    assert terminator.effects == []
    assert terminator.record is not None
    assert terminator.record.error_kind == "MissingBatchTerminator"


def test_terminator_is_not_dispatched_as_an_action() -> None:
    response = AssistantResponse("", "tool_calls", (VALID_A, BATCH_TERMINATOR))

    state = run_terminator_candidate(response)

    assert state.record is not None
    assert state.record.state == "completed"
    assert state.record.admitted_calls == 1
    assert state.record.committed_calls == 1
    assert len(state.effects) == 1
