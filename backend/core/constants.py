from enum import Enum


class JobStatus(str, Enum):
    SAVED = "saved"
    PLANNED = "planned"
    APPLIED = "applied"
    WRITTEN_TEST = "written_test"
    INTERVIEW_1 = "interview_1"
    INTERVIEW_2 = "interview_2"
    OFFER = "offer"
    REJECTED = "rejected"
    ABANDONED = "abandoned"


JOB_STATUS_VALUES = tuple(status.value for status in JobStatus)
