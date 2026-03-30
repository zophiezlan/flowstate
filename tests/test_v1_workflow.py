from tap_station.constants import WorkflowStages, get_workflow_transitions


def test_workflow_stage_normalization_v1():
    assert WorkflowStages.normalize("entered") == "ENTERED"
    assert WorkflowStages.normalize("service_start") == "FIRST_CONTACT"
    assert WorkflowStages.normalize("exit") == "COMPLETED"


def test_v1_transition_rules():
    transitions = get_workflow_transitions()
    assert transitions.is_valid_transition("ENTERED", "FIRST_CONTACT")
    assert transitions.is_valid_transition("FIRST_CONTACT", "SAMPLE_LOGGED")
    assert not transitions.is_valid_transition("ENTERED", "TESTING")

    first = transitions.validate_sequence([], "ENTERED")
    assert first["valid"] is True

    invalid_first = transitions.validate_sequence([], "TESTING")
    assert invalid_first["valid"] is False
