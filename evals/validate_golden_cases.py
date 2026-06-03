import json
from pathlib import Path


VALID_INTERVENTIONS = {
    "install_speed_camera",
    "add_warning_signage",
    "repaint_lane_markings",
    "improve_lighting",
    "add_speed_bumps",
    "increase_enforcement",
    "review_signal_timing",
    "redesign_intersection",
    "no_action_monitor",
}

VALID_PRIORITIES = {
    "low",
    "medium",
    "high",
}


def load_cases() -> list[dict]:
    path = Path(__file__).parent / "golden_recommender_cases.json"

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_case(case: dict) -> None:
    assert "case_id" in case
    assert "input" in case
    assert "expected" in case

    input_data = case["input"]
    expected = case["expected"]

    assert "detection" in input_data
    assert "hotspot" in input_data
    assert "metadata" in input_data

    assert "acceptable_primary_interventions" in expected
    assert "minimum_priority" in expected
    assert "must_use_evidence" in expected
    assert "must_not_claim" in expected

    for intervention in expected["acceptable_primary_interventions"]:
        assert intervention in VALID_INTERVENTIONS, (
            f"{case['case_id']} has invalid intervention: {intervention}"
        )

    assert expected["minimum_priority"] in VALID_PRIORITIES

    assert isinstance(expected["must_use_evidence"], list)
    assert isinstance(expected["must_not_claim"], list)


def main() -> None:
    cases = load_cases()

    assert len(cases) > 0, "No golden cases found."

    for case in cases:
        validate_case(case)

    print(f"Validated {len(cases)} golden recommender cases.")


if __name__ == "__main__":
    main()