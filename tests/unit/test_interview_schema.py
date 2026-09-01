import pytest
from pydantic import ValidationError

from backend.schemas.interview import InterviewPreparationResponse


def test_interview_preparation_schema_validates_nested_content() -> None:
    response = InterviewPreparationResponse.model_validate(
        {
            "target_position": "Python Intern",
            "focus_areas": [
                {
                    "topic": "Python backend",
                    "importance": "high",
                    "reason": "Required by the JD",
                }
            ],
            "likely_questions": [
                {
                    "question": "How did you structure the API?",
                    "category": "technical",
                    "why_asked": "Checks backend design",
                    "answer_points": ["Explain the service layers"],
                }
            ],
            "project_questions": [],
            "risk_questions": [],
            "knowledge_gaps": [
                {
                    "topic": "Docker",
                    "priority": "high",
                    "preparation": "Learn container basics",
                }
            ],
            "questions_for_interviewer": ["How is mentoring organized?"],
        }
    )

    assert response.focus_areas[0].importance == "high"
    assert response.likely_questions[0].answer_points == [
        "Explain the service layers"
    ]
    assert response.knowledge_gaps[0].topic == "Docker"


def test_interview_answer_points_are_limited_to_five() -> None:
    with pytest.raises(ValidationError):
        InterviewPreparationResponse.model_validate(
            {
                "target_position": "Python Intern",
                "likely_questions": [
                    {
                        "question": "Question",
                        "category": "technical",
                        "why_asked": "Reason",
                        "answer_points": ["point"] * 6,
                    }
                ],
            }
        )
