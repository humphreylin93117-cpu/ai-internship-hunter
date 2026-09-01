from backend.discovery.scorer import JobResultScorer
from backend.schemas.discovery import DiscoveredJob


def job(title: str, snippet: str = "") -> DiscoveredJob:
    return DiscoveredJob(
        title=title,
        url="https://example.com/job-detail/123",
        snippet=snippet,
        source_domain="example.com",
        provider="tavily",
    )


def test_real_recruitment_title_is_kept_without_detailed_snippet() -> None:
    scorer = JobResultScorer()
    candidate = job("数据分析实习生招聘", "加入我们的数据团队")

    assert scorer.score(candidate, candidate.url) >= (
        scorer.MIN_AUTHENTICITY_SCORE
    )
    assert scorer.accepts(candidate, candidate.url) is True


def test_generic_collection_and_channel_titles_are_filtered() -> None:
    scorer = JobResultScorer()
    snippet = (
        "负责数据分析与报表建设，任职要求熟悉 SQL，"
        "工作地点广州。"
    )
    blocked_titles = ["Python岗位大全", "数据分析职位列表", "广州招聘频道"]

    assert all(
        scorer.accepts(job(title, snippet), job(title, snippet).url) is False
        for title in blocked_titles
    )


def test_authenticity_score_rewards_job_detail_evidence() -> None:
    scorer = JobResultScorer()
    authentic = job(
        "Python开发实习生 - 示例科技",
        "岗位职责：负责接口开发。任职要求：熟悉 Python，学历本科。",
    )
    generic = job("示例科技官网", "欢迎了解我们的产品与服务")

    assert scorer.score(authentic, authentic.url) > scorer.score(
        generic,
        generic.url,
    )
    assert scorer.accepts(authentic, authentic.url) is True
    assert scorer.accepts(generic, generic.url) is False


def test_search_or_list_url_reduces_authenticity_score() -> None:
    scorer = JobResultScorer()
    candidate = job(
        "数据分析实习生招聘",
        "负责业务分析，要求熟悉 SQL。",
    )
    detail_url = "https://example.com/job-detail/123"
    list_url = "https://example.com/jobs/search?keyword=数据分析"

    assert scorer.score(candidate, detail_url) > scorer.score(
        candidate,
        list_url,
    )
