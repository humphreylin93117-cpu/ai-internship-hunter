import pytest
from pydantic import ValidationError

from backend.schemas.resume import ResumeOptimizationResponse


def test_resume_optimization_schema_parses_rewrites_and_gaps() -> None:
    response = ResumeOptimizationResponse.model_validate(
        {
            "target_position": "Python Intern",
            "priority_experiences": ["FastAPI project"],
            "keywords_to_emphasize": ["Python", "REST API"],
            "content_to_deemphasize": ["Unrelated coursework"],
            "project_rewrites": [
                {
                    "project": "AI Internship Hunter",
                    "original": "Built a FastAPI endpoint",
                    "suggested": "使用 FastAPI 实现结构化岗位分析接口",
                    "reason": "Directly relevant to the JD",
                }
            ],
            "skill_section_suggestions": ["Move Python to the front"],
            "missing_requirements": ["Docker is not documented"],
            "warnings": ["Do not claim production deployment"],
        }
    )

    assert response.project_rewrites[0].project == "AI Internship Hunter"
    assert response.missing_requirements == ["Docker is not documented"]
    assert response.warnings == ["Do not claim production deployment"]


def test_project_rewrite_requires_non_empty_project() -> None:
    with pytest.raises(ValidationError):
        ResumeOptimizationResponse.model_validate(
            {
                "target_position": "Python Intern",
                "project_rewrites": [
                    {
                        "project": "",
                        "original": "Built an API",
                        "suggested": "",
                        "reason": "Relevant",
                    }
                ],
            }
        )
