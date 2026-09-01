from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, OpenAIError

from backend.ai.gateway import LLMGateway, LLMGatewayError
from backend.core.config import Settings
from backend.schemas.interview import InterviewPreparationResponse
from backend.schemas.job import JobAnalysisResponse, JobIdentityExtraction
from backend.schemas.resume import ResumeOptimizationResponse


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.request = None
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        self.request = kwargs
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice])


class SequenceCompletions:
    def __init__(self, outcomes) -> None:
        self.outcomes = iter(outcomes)
        self.calls = 0
        self.requests = []

    def create(self, **kwargs):
        self.calls += 1
        self.requests.append(kwargs)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            outcome, finish_reason = outcome
        else:
            finish_reason = "stop"
        message = SimpleNamespace(content=outcome)
        choice = SimpleNamespace(
            message=message,
            finish_reason=finish_reason,
        )
        return SimpleNamespace(choices=[choice])


class RaisingCompletions:
    def create(self, **kwargs):
        raise OpenAIError("provider unavailable")


class EmptyChoicesCompletions:
    def create(self, **kwargs):
        return SimpleNamespace(choices=[])


def test_deepseek_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("RESUME_OPTIMIZATION_MAX_TOKENS", raising=False)
    monkeypatch.delenv("INTERVIEW_PREPARATION_MAX_TOKENS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.deepseek_api_key is None
    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.resume_optimization_max_tokens == 4_096
    assert settings.interview_preparation_max_tokens == 4_096


def test_gateway_requests_and_validates_json_job_analysis() -> None:
    expected = JobAnalysisResponse(
        match_score=88,
        strengths=["技术方向明确"],
        weaknesses=["工作内容较宽泛"],
        suggestions=["突出后端开发经验"],
    )
    completions = FakeCompletions(expected.model_dump_json())
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway = LLMGateway(client=client, model="test-model")

    result = gateway.analyze_job_description(
        job_description="Python 后端实习岗位",
        candidate_profile="掌握 Python 和 FastAPI",
        candidate_projects="开发过 AI 求职助手",
    )

    assert result == expected
    assert completions.request["model"] == "test-model"
    system_message = completions.request["messages"][0]
    assert "候选人与该岗位的综合匹配度" in system_message["content"]
    assert "禁止假设候选人具有资料中没有出现" in system_message["content"]
    user_message = completions.request["messages"][1]
    assert user_message["role"] == "user"
    assert "Python 后端实习岗位" in user_message["content"]
    assert "掌握 Python 和 FastAPI" in user_message["content"]
    assert "开发过 AI 求职助手" in user_message["content"]
    assert completions.request["response_format"] == {
        "type": "json_object"
    }
    assert completions.request["max_tokens"] == 1_500
    assert completions.calls == 1


def test_gateway_extracts_job_identity_from_cleaned_text() -> None:
    expected = JobIdentityExtraction(
        company="示例智能科技有限公司",
        position="数据策略实习生",
    )
    completions = FakeCompletions(expected.model_dump_json())
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = LLMGateway(
        client=client,
        model="test-model",
    ).extract_job_identity(
        "职位描述：建设指标体系。\n公司简介：示例智能科技提供数据服务。"
    )

    assert result == expected
    request = completions.request
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 300
    assert "禁止猜测或补全" in request["messages"][0]["content"]
    assert "职位描述：建设指标体系" in request["messages"][1]["content"]


def test_gateway_logs_and_rejects_invalid_json_job_analysis(caplog) -> None:
    raw_content = '{"match_score": 101}'
    completions = FakeCompletions(raw_content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway = LLMGateway(
        client=client,
        model="test-model",
        base_url="https://api.deepseek.test",
    )

    with caplog.at_level("ERROR", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError):
            gateway.analyze_job_description(
                job_description="Python 后端实习岗位",
                candidate_profile="掌握 Python",
                candidate_projects="开发过脚本",
            )

    assert "LLM response validation failed" in caplog.text
    assert "validation_error=" in caplog.text
    assert raw_content in caplog.text
    assert "model=test-model" in caplog.text
    assert "base_url=https://api.deepseek.test" in caplog.text
    assert completions.calls == 1


def test_gateway_logs_openai_error_without_secrets(caplog) -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=RaisingCompletions()),
    )
    gateway = LLMGateway(
        client=client,
        model="test-model",
        base_url="https://api.deepseek.test",
    )
    gateway._api_key = "must-not-appear"

    with caplog.at_level("ERROR", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError):
            gateway.analyze_job_description(
                job_description="Python 后端实习岗位",
                candidate_profile="掌握 Python",
                candidate_projects="开发过脚本",
            )

    assert "exception_type=OpenAIError" in caplog.text
    assert "error=provider unavailable" in caplog.text
    assert "model=test-model" in caplog.text
    assert "base_url=https://api.deepseek.test" in caplog.text
    assert "must-not-appear" not in caplog.text
    assert "Authorization" not in caplog.text


def test_gateway_logs_empty_choices(caplog) -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=EmptyChoicesCompletions()),
    )
    gateway = LLMGateway(client=client, model="test-model")

    with caplog.at_level("ERROR", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError):
            gateway.analyze_job_description(
                job_description="Python 后端实习岗位",
                candidate_profile="掌握 Python",
                candidate_projects="开发过脚本",
            )

    assert "LLM provider returned no choices" in caplog.text


def test_gateway_fails_after_three_empty_responses(
    caplog,
    monkeypatch,
) -> None:
    completions = FakeCompletions(None)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway = LLMGateway(client=client, model="test-model")
    delays = []
    monkeypatch.setattr("backend.ai.gateway.time.sleep", delays.append)

    with caplog.at_level("WARNING", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError):
            gateway.analyze_job_description(
                job_description="Python 后端实习岗位",
                candidate_profile="掌握 Python",
                candidate_projects="开发过脚本",
            )

    assert "LLM provider returned empty message content" in caplog.text
    assert completions.calls == 3
    assert delays == [0.5, 1.0]
    assert "LLM request retry 1/2" in caplog.text
    assert "LLM request retry 2/2" in caplog.text


def test_gateway_retries_empty_content_then_succeeds(
    caplog,
    monkeypatch,
) -> None:
    expected = JobAnalysisResponse(
        match_score=86,
        strengths=["Python"],
        weaknesses=[],
        suggestions=["Prepare examples"],
    )
    completions = SequenceCompletions([None, expected.model_dump_json()])
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway = LLMGateway(client=client, model="test-model")
    delays = []
    monkeypatch.setattr("backend.ai.gateway.time.sleep", delays.append)

    with caplog.at_level("WARNING", logger="backend.ai.gateway"):
        result = gateway.analyze_job_description(
            job_description="Python backend internship",
            candidate_profile="Python experience",
            candidate_projects="Backend project",
        )

    assert result == expected
    assert completions.calls == 2
    assert delays == [0.5]
    assert "LLM request retry 1/2" in caplog.text
    assert "LLM request retry 2/2" not in caplog.text


def test_gateway_retries_temporary_connection_error(monkeypatch) -> None:
    expected = JobAnalysisResponse(
        match_score=80,
        strengths=[],
        weaknesses=[],
        suggestions=[],
    )
    request = httpx.Request("POST", "https://api.deepseek.test/chat")
    completions = SequenceCompletions(
        [
            APIConnectionError(request=request),
            expected.model_dump_json(),
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    delays = []
    monkeypatch.setattr("backend.ai.gateway.time.sleep", delays.append)

    result = LLMGateway(client=client).analyze_job_description(
        job_description="Python JD",
        candidate_profile="Python",
        candidate_projects="Project",
    )

    assert result == expected
    assert completions.calls == 2
    assert delays == [0.5]


def test_gateway_does_not_retry_client_parameter_error(monkeypatch) -> None:
    request = httpx.Request("POST", "https://api.deepseek.test/chat")
    response = httpx.Response(400, request=request)
    completions = SequenceCompletions(
        [BadRequestError("invalid parameter", response=response, body=None)]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    monkeypatch.setattr(
        "backend.ai.gateway.time.sleep",
        lambda delay: pytest.fail("client error must not retry"),
    )

    with pytest.raises(LLMGatewayError):
        LLMGateway(client=client).analyze_job_description(
            job_description="Python JD",
            candidate_profile="Python",
            candidate_projects="Project",
        )

    assert completions.calls == 1


def test_gateway_preserves_complete_resume_optimization_structure(
    caplog,
) -> None:
    expected = ResumeOptimizationResponse(
        target_position="Python Intern",
        priority_experiences=["FastAPI project"],
        keywords_to_emphasize=["Python"],
        content_to_deemphasize=[],
        project_rewrites=[
            {
                "project": "AI Internship Hunter",
                "original": "Built a FastAPI endpoint",
                "suggested": "使用 FastAPI 实现岗位分析接口",
                "reason": "Relevant to the JD",
            }
        ],
        skill_section_suggestions=["Put Python first"],
        missing_requirements=["Docker"],
        warnings=["Do not claim production deployment"],
    )
    completions = FakeCompletions(expected.model_dump_json())
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway = LLMGateway(client=client, model="test-model")

    with caplog.at_level("DEBUG", logger="backend.ai.gateway"):
        result = gateway.optimize_resume_for_job(
            target_position="Python Intern",
            job_description="Build FastAPI services",
            candidate_profile="Candidate knows Python",
            candidate_projects="Built an AI internship helper",
        )

    assert result == expected
    assert completions.calls == 1
    request = completions.request
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 4_096
    assert "资深技术招聘顾问和简历优化顾问" in request["messages"][0][
        "content"
    ]
    assert "不得捏造指标" in request["messages"][0]["content"]
    assert "后续计划" in request["messages"][0]["content"]
    assert "priority_experiences 最多 3 项" in request["messages"][0][
        "content"
    ]
    assert "keywords_to_emphasize 最多 8 项" in request["messages"][0][
        "content"
    ]
    assert "content_to_deemphasize 最多 3 项" in request["messages"][0][
        "content"
    ]
    assert "project_rewrites 最多 2 个项目" in request["messages"][0][
        "content"
    ]
    assert "suggested 最多约 180 个中文字符" in request["messages"][0][
        "content"
    ]
    assert "reason 最多约 80 个中文字符" in request["messages"][0][
        "content"
    ]
    assert "skill_section_suggestions 最多 4 项" in request["messages"][0][
        "content"
    ]
    assert "missing_requirements 最多 5 项" in request["messages"][0][
        "content"
    ]
    assert "warnings 最多 4 项" in request["messages"][0]["content"]
    assert "不要写成长篇职业分析报告" in request["messages"][0]["content"]
    user_content = request["messages"][1]["content"]
    assert "Python Intern" in user_content
    assert "Build FastAPI services" in user_content
    assert "Candidate knows Python" in user_content
    assert "Built an AI internship helper" in user_content
    assert "LLM resume optimization raw response" in caplog.text
    assert "finish_reason=stop" in caplog.text
    assert "max_tokens=4096" in caplog.text
    assert f"content_length={len(expected.model_dump_json())}" in caplog.text
    assert "LLM resume optimization cleaned JSON" in caplog.text
    assert "cleaned_json=" in caplog.text
    assert "LLM resume optimization validated JSON" in caplog.text
    assert "validated_json=" in caplog.text
    assert expected.model_dump_json() in caplog.text


def test_resume_optimization_retries_empty_content_then_succeeds(
    monkeypatch,
) -> None:
    expected = ResumeOptimizationResponse(
        target_position="Python Intern",
        project_rewrites=[],
    )
    completions = SequenceCompletions([None, expected.model_dump_json()])
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    delays = []
    monkeypatch.setattr("backend.ai.gateway.time.sleep", delays.append)

    result = LLMGateway(client=client).optimize_resume_for_job(
        target_position="Python Intern",
        job_description="Build APIs",
        candidate_profile="Python",
        candidate_projects="API project",
    )

    assert result == expected
    assert completions.calls == 2
    assert delays == [0.5]
    assert [request["max_tokens"] for request in completions.requests] == [
        4_096,
        4_096,
    ]


def test_resume_optimization_retries_truncation_in_compact_mode(
    caplog,
) -> None:
    expected = ResumeOptimizationResponse(
        target_position="Python Intern",
        priority_experiences=["FastAPI project"],
        project_rewrites=[],
    )
    completions = SequenceCompletions(
        [
            ('{"target_position":"Python Intern","project_rewrites":[', "length"),
            (expected.model_dump_json(), "stop"),
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    with caplog.at_level("INFO", logger="backend.ai.gateway"):
        result = LLMGateway(client=client).optimize_resume_for_job(
            target_position="Python Intern",
            job_description="Build APIs",
            candidate_profile="Python",
            candidate_projects="API project",
        )

    assert result == expected
    assert completions.calls == 2
    assert [request["max_tokens"] for request in completions.requests] == [
        4_096,
        4_096,
    ]
    compact_prompt = completions.requests[1]["messages"][0]["content"]
    assert "当前为精简模式" in compact_prompt
    assert "keywords_to_emphasize 最多 6 条" in compact_prompt
    assert "project_rewrites 最多 1 个项目" in compact_prompt
    assert "suggested 最多约 120 个中文字符" in compact_prompt
    assert "reason 最多约 60 个中文字符" in compact_prompt
    assert "skill_section_suggestions 最多 3 条" in compact_prompt
    assert "missing_requirements 最多 4 条" in compact_prompt
    assert "warnings 最多 3 条" in compact_prompt
    assert "禁止重复 JD 和候选人背景" in compact_prompt
    assert result.model_dump().keys() == {
        "target_position",
        "priority_experiences",
        "keywords_to_emphasize",
        "content_to_deemphasize",
        "project_rewrites",
        "skill_section_suggestions",
        "missing_requirements",
        "warnings",
    }
    assert "finish_reason=length" in caplog.text
    assert "LLM response truncated due to token limit" in caplog.text
    assert "LLM truncated response retry 1/1" in caplog.text
    assert "mode=compact" in caplog.text


def test_resume_optimization_fails_after_second_truncated_response(
    caplog,
) -> None:
    truncated_content = '{"target_position":"Python Intern","warnings":["cut'
    completions = SequenceCompletions(
        [
            (truncated_content, "length"),
            (truncated_content, "length"),
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    with caplog.at_level("INFO", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError) as error:
            LLMGateway(client=client).optimize_resume_for_job(
                target_position="Python Intern",
                job_description="Build APIs",
                candidate_profile="Python",
                candidate_projects="API project",
            )

    assert "response was truncated" in str(error.value)
    assert completions.calls == 2
    assert [request["max_tokens"] for request in completions.requests] == [
        4_096,
        4_096,
    ]
    assert caplog.text.count(
        "LLM response truncated due to token limit"
    ) == 2
    assert "LLM resume optimization cleaned JSON" not in caplog.text


def test_resume_optimization_completes_missing_rewrite_fields() -> None:
    content = """{
        "target_position": "Python Intern",
        "project_rewrites": [
            {
                "project": "AI Internship Hunter"
            }
        ],
        "missing_requirements": [],
        "warnings": []
    }"""
    completions = FakeCompletions(content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = LLMGateway(client=client).optimize_resume_for_job(
        target_position="Python Intern",
        job_description="Build APIs",
        candidate_profile="Python",
        candidate_projects="API project",
    )

    rewrite = result.project_rewrites[0]
    assert rewrite.project == "AI Internship Hunter"
    assert rewrite.original == ""
    assert rewrite.suggested == ""
    assert rewrite.reason == ""
    assert completions.calls == 1


def test_resume_optimization_adds_missing_project_rewrites_array() -> None:
    content = """{
        "target_position": "Python Intern",
        "priority_experiences": ["FastAPI project"],
        "keywords_to_emphasize": ["Python"]
    }"""
    completions = FakeCompletions(content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = LLMGateway(client=client).optimize_resume_for_job(
        target_position="Python Intern",
        job_description="Build APIs",
        candidate_profile="Python",
        candidate_projects="API project",
    )

    assert result.target_position == "Python Intern"
    assert result.priority_experiences == ["FastAPI project"]
    assert result.keywords_to_emphasize == ["Python"]
    assert result.project_rewrites == []
    assert completions.calls == 1


def test_resume_optimization_replaces_non_array_rewrites() -> None:
    content = """{
        "target_position": "Python Intern",
        "project_rewrites": {"project": "invalid container"}
    }"""
    completions = FakeCompletions(content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = LLMGateway(client=client).optimize_resume_for_job(
        target_position="Python Intern",
        job_description="Build APIs",
        candidate_profile="Python",
        candidate_projects="API project",
    )

    assert result.project_rewrites == []
    assert completions.calls == 1


def test_resume_optimization_accepts_json_in_markdown_code_block() -> None:
    expected = ResumeOptimizationResponse(
        target_position="Python Intern",
        missing_requirements=["Docker"],
        warnings=["Do not invent Docker experience"],
    )
    markdown_content = (
        '说明中的示例不是结果：{"project":"wrong"}\n```json\n'
        f"{expected.model_dump_json()}\n"
        "```\n请根据实际经历使用。"
    )
    completions = FakeCompletions(markdown_content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = LLMGateway(client=client).optimize_resume_for_job(
        target_position="Python Intern",
        job_description="Build APIs",
        candidate_profile="Python",
        candidate_projects="API project",
    )

    assert result == expected
    assert completions.calls == 1


def test_resume_optimization_rejects_invalid_json_and_logs_raw_response(
    caplog,
) -> None:
    invalid_content = "```json\n{not valid json}\n```"
    completions = FakeCompletions(invalid_content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    with caplog.at_level("DEBUG", logger="backend.ai.gateway"):
        with pytest.raises(LLMGatewayError) as error:
            LLMGateway(client=client).optimize_resume_for_job(
                target_position="Python Intern",
                job_description="Build APIs",
                candidate_profile="Python",
                candidate_projects="API project",
            )

    assert "invalid resume optimization JSON payload" in str(error.value)
    assert completions.calls == 1
    assert "LLM resume optimization raw response" in caplog.text
    assert "{not valid json}" in caplog.text
    assert f"content_length={len(invalid_content)}" in caplog.text
    assert "LLM resume optimization cleaned JSON" in caplog.text
    assert "LLM resume optimization validation failed" in caplog.text
    assert "validation_error=" in caplog.text


def test_gateway_generates_structured_interview_preparation() -> None:
    expected = InterviewPreparationResponse(
        target_position="Python Intern",
        focus_areas=[
            {
                "topic": "Python backend",
                "importance": "high",
                "reason": "Required by the JD",
            }
        ],
        likely_questions=[
            {
                "question": "How did you structure the API?",
                "category": "technical",
                "why_asked": "Checks backend design",
                "answer_points": ["Explain the service layers"],
            }
        ],
        project_questions=[],
        risk_questions=[],
        knowledge_gaps=[],
        questions_for_interviewer=["How is mentoring organized?"],
    )
    completions = FakeCompletions(expected.model_dump_json())
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = LLMGateway(client=client).prepare_interview_for_job(
        target_position="Python Intern",
        job_description="Build FastAPI services",
        candidate_profile="Python profile",
        candidate_projects="API project",
        match_analysis={
            "match_score": 80,
            "strengths": ["Python"],
            "weaknesses": ["Docker"],
            "suggestions": ["Review Docker"],
        },
    )

    assert result == expected
    request = completions.request
    assert request["max_tokens"] == 4_096
    prompt = request["messages"][0]["content"]
    assert "focus_areas 最多 5 项" in prompt
    assert "likely_questions 最多 8 题" in prompt
    assert "每个 answer_points 或 answer_strategy 最多 5 条" in prompt
    assert "严禁把未实现功能、未使用技术或竞赛项目写成生产环境经验" in prompt
    user_content = request["messages"][1]["content"]
    assert "Build FastAPI services" in user_content
    assert '"match_score": 80' in user_content
    assert completions.calls == 1


def test_interview_truncation_retries_once_and_succeeds(caplog) -> None:
    expected = InterviewPreparationResponse(
        target_position="Python Intern",
        focus_areas=[],
        likely_questions=[],
        project_questions=[],
        risk_questions=[],
        knowledge_gaps=[],
        questions_for_interviewer=[],
    )
    completions = SequenceCompletions(
        [
            ('{"target_position":"Python Intern","focus_areas":[', "length"),
            (expected.model_dump_json(), "stop"),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    with caplog.at_level("INFO", logger="backend.ai.gateway"):
        result = LLMGateway(client=client).prepare_interview_for_job(
            target_position="Python Intern",
            job_description="Build APIs",
            candidate_profile="Python",
            candidate_projects="API project",
            match_analysis={},
        )

    assert result == expected
    assert completions.calls == 2
    assert [request["max_tokens"] for request in completions.requests] == [
        4_096,
        4_096,
    ]
    assert "当前为截断后的精简重试" in completions.requests[1][
        "messages"
    ][0]["content"]
    assert "finish_reason=length" in caplog.text
    assert "LLM truncated response retry 1/1" in caplog.text


def test_interview_two_truncated_responses_fail() -> None:
    completions = SequenceCompletions(
        [
            ("{\"target_position\":\"cut", "length"),
            ("{\"target_position\":\"cut", "length"),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    with pytest.raises(LLMGatewayError) as error:
        LLMGateway(client=client).prepare_interview_for_job(
            target_position="Python Intern",
            job_description="Build APIs",
            candidate_profile="Python",
            candidate_projects="API project",
            match_analysis={},
        )

    assert "response was truncated" in str(error.value)
    assert completions.calls == 2
