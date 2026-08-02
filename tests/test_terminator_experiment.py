from artifact.run_terminator_experiment import run_experiment


def test_terminator_experiment_preserves_claim_boundary() -> None:
    result = run_experiment()

    assert result["findings"] == {
        "well_formed_suffix_cut_detected": True,
        "middle_omission_detected": False,
        "noncompliant_complete_batch_false_rejected": True,
        "stop_reason_still_required": True,
    }
    cases = {row["case"]: row for row in result["cases"]}
    middle = cases["middle_action_silently_omitted"]["terminator_candidate"]
    assert middle["record"]["state"] == "completed"
    assert len(middle["effects"]) == 1
