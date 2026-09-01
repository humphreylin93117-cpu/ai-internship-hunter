from backend.discovery.filter import JobDiscoveryFilter
from backend.schemas.discovery import DiscoveredJob


def discovered_job(
    title: str,
    url: str,
    snippet: str,
) -> DiscoveredJob:
    return DiscoveredJob(
        title=title,
        url=url,
        snippet=snippet,
        source_domain="example.com",
        provider="tavily",
    )


def test_url_blacklist_filters_search_aggregate_and_channel_pages() -> None:
    result_filter = JobDiscoveryFilter(current_year=2026)
    blocked_urls = [
        "https://www.linkedin.com/jobs/search/?keywords=Data%20Analyst",
        "https://www.linkedin.com/jobs/collections/recommended/",
        "https://www.zhipin.com/web/geek/job?query=Python",
        "https://www.liepin.com/zhaopin/shujufenxi/",
        "https://sou.zhaopin.com/?kw=Python",
        "https://example.com/jobs",
        "https://example.com/city/guangzhou",
        "https://example.com/job-search/python",
    ]

    assert all(
        result_filter.is_blacklisted_url(url) for url in blocked_urls
    )
    assert not result_filter.is_blacklisted_url(
        "https://www.linkedin.com/jobs/view/123456/"
    )
    assert not result_filter.is_blacklisted_url(
        "https://www.zhaopin.com/jobdetail/abc123"
    )


def test_title_quality_rejects_counts_channels_and_job_collections() -> None:
    result_filter = JobDiscoveryFilter(current_year=2026)
    rejected_titles = [
        "20个广州Python岗位",
        "广州数据分析职位列表",
        "广州招聘频道",
        "【Python实习招聘网_2025年Python实习招聘信息】-猎聘",
        "21届实习-Python开发工程师（深圳）实习招聘",
        "1,000+ Data Analyst jobs in Guangzhou",
    ]

    assert all(
        result_filter.title_quality_score(title)
        < result_filter.MIN_TITLE_SCORE
        for title in rejected_titles
    )
    assert result_filter.title_quality_score(
        "数据分析实习生招聘_示例科技有限公司招聘-智联招聘"
    ) >= result_filter.MIN_TITLE_SCORE
    assert result_filter.title_quality_score(
        "Data Analyst - Example Company | LinkedIn"
    ) >= result_filter.MIN_TITLE_SCORE


def test_snippet_quality_rejects_aggregate_navigation_and_stale_text() -> None:
    result_filter = JobDiscoveryFilter(current_year=2026)
    rejected_snippets = [
        "Python实习招聘专场，本期新增2249个职位，覆盖全国多个城市。",
        "首页 找实习 找校招 职位列表 企业入口 关于我们 客户服务。",
        "2023-09-06刷新，首页校招实习僧TV职位百科企业入口。",
    ]

    assert all(
        result_filter.snippet_quality_score(snippet)
        < result_filter.MIN_SNIPPET_SCORE
        for snippet in rejected_snippets
    )
    assert result_filter.snippet_quality_score(
        "Python开发工程师，18-24K，广州白云区，负责后端接口开发，"
        "任职要求熟悉 Python 和 FastAPI。"
    ) >= result_filter.MIN_SNIPPET_SCORE


def test_filter_requires_url_title_and_snippet_to_all_pass() -> None:
    result_filter = JobDiscoveryFilter(current_year=2026)
    valid = discovered_job(
        "【广州 Python开发工程师招聘】-示例科技广州招聘信息-猎聘",
        "https://www.liepin.com/job/123456.shtml",
        "Python开发工程师，18-24K，广州，负责接口开发，"
        "要求熟悉 Python 和 SQL。",
    )
    aggregate_snippet = valid.model_copy(
        update={
            "snippet": "Python招聘专场，本期新增2249个职位，覆盖全国。"
        }
    )

    assert result_filter.accepts(valid, valid.url) is True
    assert result_filter.accepts(
        aggregate_snippet,
        aggregate_snippet.url,
    ) is False
