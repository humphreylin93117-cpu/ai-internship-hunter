from frontend.application_workbench import (
    NEXT_STATUS_OPTIONS,
    split_queue_items,
)


def test_saved_and_planned_are_pending_while_applied_is_follow_up() -> None:
    queue = [
        {"job_id": 1, "status": "saved"},
        {"job_id": 2, "status": "planned"},
        {"job_id": 3, "status": "applied"},
        {"job_id": 4, "status": "interview_1"},
        {"job_id": 5, "status": "rejected"},
    ]

    pending, follow_up = split_queue_items(queue)

    assert [item["job_id"] for item in pending] == [1, 2]
    assert [item["job_id"] for item in follow_up] == [3, 4, 5]


def test_follow_up_statuses_offer_valid_next_stages() -> None:
    assert NEXT_STATUS_OPTIONS["applied"] == [
        "written_test",
        "interview_1",
        "rejected",
        "abandoned",
    ]
    assert NEXT_STATUS_OPTIONS["written_test"][0] == "interview_1"
    assert NEXT_STATUS_OPTIONS["interview_1"][0] == "interview_2"
    assert NEXT_STATUS_OPTIONS["interview_2"][0] == "offer"
    assert NEXT_STATUS_OPTIONS["offer"] == []
