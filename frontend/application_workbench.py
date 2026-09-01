from typing import Any


PENDING_STATUSES = frozenset({"saved", "planned"})
FOLLOW_UP_STATUSES = frozenset(
    {
        "applied",
        "written_test",
        "interview_1",
        "interview_2",
        "offer",
        "rejected",
        "abandoned",
    }
)
STATUS_OPTIONS = [
    "saved",
    "planned",
    "applied",
    "written_test",
    "interview_1",
    "interview_2",
    "offer",
    "rejected",
    "abandoned",
]
STATUS_LABELS = {
    "saved": "已保存",
    "planned": "计划投递",
    "applied": "已投递",
    "written_test": "笔试",
    "interview_1": "一面",
    "interview_2": "二面",
    "offer": "Offer",
    "rejected": "未通过",
    "abandoned": "已放弃",
}
NEXT_STATUS_OPTIONS = {
    "applied": ["written_test", "interview_1", "rejected", "abandoned"],
    "written_test": ["interview_1", "rejected", "abandoned"],
    "interview_1": ["interview_2", "offer", "rejected", "abandoned"],
    "interview_2": ["offer", "rejected", "abandoned"],
    "offer": [],
    "rejected": [],
    "abandoned": [],
}


def split_queue_items(
    queue: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pending = [item for item in queue if item["status"] in PENDING_STATUSES]
    follow_up = [
        item for item in queue if item["status"] in FOLLOW_UP_STATUSES
    ]
    return pending, follow_up
