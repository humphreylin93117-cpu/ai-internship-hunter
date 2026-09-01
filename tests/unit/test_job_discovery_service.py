from backend.schemas.discovery import DiscoveredJob, JobDiscoveryRequest
from backend.services.job_discovery_service import JobDiscoveryService


def job(title: str, url: str, snippet: str = "") -> DiscoveredJob:
    return DiscoveredJob(
        title=title,
        url=url,
        snippet=snippet or (
            "负责业务数据分析与报表建设，任职要求熟悉 SQL，"
            "工作地点广州。"
        ),
        source_domain="example.com",
        provider="tavily",
    )


class FakeProvider:
    def __init__(self, responses=None, content="完整岗位正文") -> None:
        self.responses = responses or {}
        self.content = content
        self.search_calls = []
        self.extract_calls = []

    def search_jobs(self, query: str, max_results: int):
        self.search_calls.append((query, max_results))
        return self.responses.get(query, [])

    def extract(self, url: str):
        self.extract_calls.append(url)
        return self.content


def request(max_results: int = 20) -> JobDiscoveryRequest:
    return JobDiscoveryRequest(
        keywords=["数据分析", "Python", "AI Agent"],
        cities=["广州", "深圳"],
        max_results=max_results,
    )


def test_multiple_queries_are_limited_and_merged() -> None:
    queries = JobDiscoveryService.build_queries(
        cities=["广州", "深圳"],
        keywords=["数据分析", "Python", "AI Agent"],
    )
    provider = FakeProvider(
        {
            query: [
                job(
                    f"数据分析实习生招聘 {index}",
                    f"https://e.com/jobs/{index}",
                )
            ]
            for index, query in enumerate(queries)
        }
    )

    result = JobDiscoveryService(provider).discover(request())

    assert [call[0] for call in provider.search_calls] == queries
    assert all(call[1] == 10 for call in provider.search_calls)
    assert len(provider.search_calls) == JobDiscoveryService.MAX_QUERIES
    assert len(result.results) == JobDiscoveryService.MAX_QUERIES


def test_single_keyword_query_is_expanded_with_recruitment_intents() -> None:
    queries = JobDiscoveryService.build_queries(
        cities=["广州"],
        keywords=["数据分析"],
    )

    assert queries == [
        "广州 数据分析 实习 招聘",
        "广州 数据分析 实习生 职位",
        "广州 数据分析 校园招聘",
        "广州 数据分析 intern job",
        "广州 数据分析 招聘 职位描述",
        "广州 数据分析 招聘 任职要求",
        "广州 数据分析 实习 工作内容",
        "广州 数据分析 校招 岗位职责",
    ]


def test_normalized_url_removes_tracking_and_duplicates() -> None:
    provider = FakeProvider(
        {
            "广州 数据分析 实习 招聘": [
                job(
                    "数据分析实习招聘",
                    "https://Example.com/jobs/1/?utm_source=x&id=7",
                ),
                job(
                    "同一职位",
                    "https://example.com/jobs/1?id=7&ref=homepage",
                ),
            ]
        }
    )

    result = JobDiscoveryService(provider).discover(request())

    assert len(result.results) == 1
    assert result.results[0].url == "https://example.com/jobs/1?id=7"


def test_expanded_query_results_are_merged_and_deduplicated() -> None:
    first_query = "广州 数据分析 实习 招聘"
    second_query = "广州 数据分析 实习生 职位"
    provider = FakeProvider(
        {
            first_query: [
                job(
                    "数据分析实习生招聘",
                    "https://example.com/job-detail/1?utm_source=search",
                    "加入数据团队",
                )
            ],
            second_query: [
                job(
                    "数据分析实习生招聘",
                    "https://example.com/job-detail/1/",
                    "负责数据分析，要求熟悉 SQL。",
                ),
                job(
                    "商业分析实习生招聘",
                    "https://example.com/job-detail/2",
                    "参与业务分析，要求熟悉 Excel。",
                ),
            ],
        }
    )
    discovery_request = JobDiscoveryRequest(
        keywords=["数据分析"],
        cities=["广州"],
        max_results=20,
    )

    result = JobDiscoveryService(provider).discover(discovery_request)

    assert [item.url for item in result.results] == [
        "https://example.com/job-detail/1",
        "https://example.com/job-detail/2",
    ]


def test_non_recruitment_results_are_filtered() -> None:
    provider = FakeProvider(
        {
            "广州 数据分析 实习 招聘": [
                job("Python 入门教程", "https://example.com/tutorial"),
                job("示例科技官网", "https://example.com/intern"),
            ]
        }
    )

    result = JobDiscoveryService(provider).discover(request())

    assert result.results == []


def test_max_results_stops_result_collection() -> None:
    provider = FakeProvider(
        {
            "广州 数据分析 实习 招聘": [
                job(
                    f"数据分析实习生招聘 {index}",
                    f"https://e.com/jobs/{index}",
                )
                for index in range(5)
            ]
        }
    )

    result = JobDiscoveryService(provider).discover(request(max_results=2))

    assert len(result.results) == 2
    assert len(provider.search_calls) == 1


def test_multiple_search_rounds_continue_until_final_limit() -> None:
    queries = JobDiscoveryService.build_queries(
        cities=["广州"],
        keywords=["数据分析"],
    )
    provider = FakeProvider(
        {
            queries[0]: [
                job(
                    "广州数据分析职位列表",
                    "https://www.zhipin.com/zhaopin/shujufenxi/",
                )
            ],
            queries[1]: [
                job(
                    "数据分析实习生招聘",
                    "https://www.zhipin.com/job_detail/boss1.html",
                )
            ],
            queries[2]: [
                job(
                    "Data Analyst jobs in Guangzhou",
                    "https://www.linkedin.com/jobs/search/?keywords=analyst",
                )
            ],
            queries[3]: [
                job(
                    "数据分析实习生招聘",
                    "https://www.liepin.com/job/1001.shtml",
                )
            ],
            queries[4]: [
                job(
                    "重复岗位",
                    "https://www.zhipin.com/job_detail/boss1.html?utm_source=x",
                )
            ],
            queries[5]: [
                job(
                    "商业分析实习生招聘",
                    "https://www.zhaopin.com/jobdetail/zl1002",
                )
            ],
            queries[6]: [
                job(
                    "Data Analyst Intern",
                    "https://www.linkedin.com/jobs/view/1003/",
                )
            ],
        }
    )
    discovery_request = JobDiscoveryRequest(
        keywords=["数据分析"],
        cities=["广州"],
        max_results=4,
    )

    result = JobDiscoveryService(provider).discover(discovery_request)

    assert len(result.results) == 4
    assert len(provider.search_calls) == 7
    assert [item.url for item in result.results] == [
        "https://www.zhipin.com/job_detail/boss1.html",
        "https://www.liepin.com/job/1001.shtml",
        "https://www.zhaopin.com/jobdetail/zl1002",
        "https://www.linkedin.com/jobs/view/1003",
    ]


def test_extract_delegates_only_selected_url() -> None:
    provider = FakeProvider(
        content=(
            "公司：示例科技\n岗位：Python 实习生\n"
            "岗位职责：负责 Python 接口开发和单元测试。\n"
            "任职要求：熟悉 FastAPI，具备良好沟通能力。"
        )
    )

    result = JobDiscoveryService(provider).extract(
        "https://example.com/jobs/1"
    )

    assert result.content.startswith("公司：示例科技")
    assert result.is_complete is True
    assert provider.extract_calls == ["https://example.com/jobs/1"]


def test_extract_rejects_list_page_instead_of_returning_snippet() -> None:
    provider = FakeProvider(
        content=(
            "数据分析职位列表\n为您找到 80 个职位\n"
            "广州数据分析实习生招聘\n深圳数据分析实习生招聘\n"
            "北京数据分析实习生招聘\n上海数据分析实习生招聘\n"
            "杭州数据分析实习生招聘"
        )
    )

    result = JobDiscoveryService(provider).extract(
        "https://example.com/jobs/search"
    )

    assert result.content == ""
    assert result.is_complete is False
    assert "未获取到完整岗位详情" in result.warning


def test_discover_removes_obvious_non_job_pages() -> None:
    provider = FakeProvider(
        {
            "广州 数据分析 实习 招聘": [
                job(
                    "数据分析实习生招聘_示例科技有限公司招聘-智联招聘",
                    "https://www.zhaopin.com/jobdetail/abc123",
                ),
                job(
                    "广州数据分析职位列表",
                    "https://www.zhaopin.com/sou/?kw=数据分析",
                ),
                job(
                    "1,000+ Data Analyst jobs in Guangzhou",
                    "https://www.linkedin.com/jobs/search/?keywords=analyst",
                ),
                job(
                    "广州招聘频道",
                    "https://example.com/city/guangzhou",
                ),
            ]
        }
    )

    result = JobDiscoveryService(provider).discover(request())

    assert [item.title for item in result.results] == [
        "数据分析实习生招聘_示例科技有限公司招聘-智联招聘"
    ]
