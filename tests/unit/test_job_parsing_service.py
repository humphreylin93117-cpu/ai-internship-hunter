from typing import Optional

from backend.ai.gateway import LLMGatewayError
from backend.schemas.job import JobIdentityExtraction
from backend.services.job_parsing_service import JobParsingService


class FakeIdentityGateway:
    def __init__(
        self,
        company: str = "",
        position: str = "",
        error: Optional[Exception] = None,
    ) -> None:
        self.result = JobIdentityExtraction(
            company=company,
            position=position,
        )
        self.error = error
        self.calls = []

    def extract_job_identity(self, job_description: str):
        self.calls.append(job_description)
        if self.error:
            raise self.error
        return self.result


def test_parse_explicit_job_fields_and_preserve_jd() -> None:
    service = JobParsingService()
    raw_text = (
        "公司名称：示例科技\n"
        "岗位名称：Python 后端实习生\n"
        "职责：使用 FastAPI 开发接口"
    )

    result = service.parse(
        raw_text,
        "https://www.zhipin.com/job_detail/123.html",
    )

    assert result.company == "示例科技"
    assert result.position == "Python 后端实习生"
    assert result.job_description == raw_text
    assert result.source == "BOSS"
    assert result.job_url == "https://www.zhipin.com/job_detail/123.html"
    assert result.parse_status == "success"
    assert result.parse_message == "已检测到有效招聘内容"


def test_parse_does_not_invent_missing_company() -> None:
    result = JobParsingService().parse(
        "岗位：数据分析实习生\n负责业务数据分析"
    )

    assert result.company == ""
    assert result.position == "数据分析实习生"


def test_parse_does_not_invent_missing_position() -> None:
    result = JobParsingService().parse(
        "公司：示例科技\n负责 Python 服务开发"
    )

    assert result.company == "示例科技"
    assert result.position == ""


def test_unknown_url_is_classified_as_official_site() -> None:
    result = JobParsingService().parse(
        "Company: Example Tech\nJob Title: Python Intern",
        "https://careers.example.com/jobs/1",
    )

    assert result.source == "官网"


def test_parse_liepin_page_title_and_remove_recommendations() -> None:
    raw_text = (
        "【广州 数据分析实习生招聘】-伟亿国际有限公司广州招聘信息-猎聘\n"
        "数据分析实习生 100-150元/天\n"
        "工作地点：广州海珠区\n"
        "岗位职责：负责经营数据整理、分析和可视化。\n"
        "任职要求：本科在读，熟悉 Excel 和 SQL。\n"
        "猜你喜欢\n"
        "广州医药数据分析师招聘\n"
        "猎聘温馨提示：谨防诈骗"
    )

    result = JobParsingService().parse(
        raw_text,
        "https://m.liepin.com/job/1975804533.shtml",
    )

    assert result.company == "伟亿国际有限公司"
    assert result.position == "数据分析实习生"
    assert result.source == "猎聘"
    assert "岗位职责" in result.job_description
    assert "猜你喜欢" not in result.job_description
    assert "猎聘温馨提示" not in result.job_description


def test_parse_boss_title_format() -> None:
    result = JobParsingService().parse(
        "「广州 数据分析实习生招聘」_示例科技有限公司招聘-BOSS直聘\n"
        "职位描述：协助完成数据分析。\n任职要求：熟悉 SQL。",
        "https://www.zhipin.com/job_detail/1.html",
    )

    assert result.company == "示例科技有限公司"
    assert result.position == "数据分析实习生"
    assert result.source == "BOSS"


def test_parse_shixiseng_title_format() -> None:
    result = JobParsingService().parse(
        "Python开发实习生招聘-示例网络科技-实习僧\n"
        "工作内容：参与后端服务开发。\n岗位要求：熟悉 Python。",
        "https://www.shixiseng.com/intern/abc",
    )

    assert result.company == "示例网络科技"
    assert result.position == "Python开发实习生"
    assert result.source == "实习僧"


def test_source_domain_mappings() -> None:
    service = JobParsingService()

    assert (
        service.parse(
            "职责：数据分析",
            "https://www.liepin.com/job/1",
        ).source
        == "猎聘"
    )
    assert (
        service.parse(
            "职责：数据分析",
            "https://zhaopin.com/job/1",
        ).source
        == "智联招聘"
    )
    assert (
        service.parse(
            "职责：数据分析",
            "https://www.51job.com/job/1",
        ).source
        == "前程无忧"
    )


def test_cleaned_official_html_is_sent_to_llm_for_missing_identity() -> None:
    gateway = FakeIdentityGateway(
        company="示例智能科技有限公司",
        position="数据策略实习生",
    )
    raw_html = """
    <html><body>
      <header>首页 产品 服务 招聘频道 登录</header>
      <main>
        <h1>数据策略实习生</h1>
        <p>薪资：150-200元/天</p>
        <p>工作地点：广州</p>
        <section><h2>公司简介</h2><p>示例智能科技提供数据服务。</p></section>
        <section><h2>职位描述</h2><p>协助建设业务指标体系。</p></section>
        <section><h2>任职要求</h2><p>熟悉 SQL、Excel 和 Python。</p></section>
      </main>
      <footer>隐私政策 联系我们 热门职位</footer>
    </body></html>
    """

    result = JobParsingService(gateway=gateway).parse(
        raw_html,
        "https://careers.example.com/jobs/data-intern",
    )

    assert result.company == "示例智能科技有限公司"
    assert result.position == "数据策略实习生"
    assert result.source == "官网"
    assert len(gateway.calls) == 1
    llm_input = gateway.calls[0]
    assert "职位描述" in llm_input
    assert "任职要求" in llm_input
    assert "公司简介" in llm_input
    assert "薪资：150-200元/天" in llm_input
    assert "工作地点：广州" in llm_input
    assert "招聘频道" not in llm_input
    assert "隐私政策" not in llm_input
    assert "<header>" not in llm_input


def test_llm_only_fills_missing_fields_and_keeps_rule_result() -> None:
    gateway = FakeIdentityGateway(
        company="错误公司",
        position="Python 后端实习生",
    )
    raw_text = (
        "公司：示例科技\n"
        "职位描述：参与后端接口开发和维护。\n"
        "任职要求：熟悉 Python、FastAPI 和 SQL。\n"
        "工作地点：深圳"
    )

    result = JobParsingService(gateway=gateway).parse(raw_text)

    assert result.company == "示例科技"
    assert result.position == "Python 后端实习生"
    assert len(gateway.calls) == 1


def test_llm_failure_falls_back_without_breaking_parse() -> None:
    gateway = FakeIdentityGateway(
        error=LLMGatewayError("provider unavailable")
    )
    raw_text = (
        "数据平台实习生\n"
        "职位描述：参与数据平台功能开发和维护。\n"
        "任职要求：熟悉 Python、SQL 和数据处理。\n"
        "工作地点：广州"
    )

    result = JobParsingService(gateway=gateway).parse(raw_text)

    assert result.company == ""
    assert result.position == ""
    assert "职位描述" in result.job_description


def test_navigation_page_is_rejected_before_identity_extraction() -> None:
    gateway = FakeIdentityGateway(
        company="不应调用的公司",
        position="不应调用的岗位",
    )
    raw_text = (
        "首页 职位分类 热门城市 热门公司 企业入口 关于我们 "
        "联系我们 隐私政策"
    )

    result = JobParsingService(gateway=gateway).parse(raw_text)

    assert result.parse_status == "invalid"
    assert "导航页" in result.parse_message
    assert result.job_description == ""
    assert result.company == ""
    assert result.position == ""
    assert gateway.calls == []


def test_login_page_is_rejected_before_identity_extraction() -> None:
    gateway = FakeIdentityGateway()
    raw_text = "账号登录\n手机号登录\n验证码登录\n登录后查看职位详情"

    result = JobParsingService(gateway=gateway).parse(raw_text)

    assert result.parse_status == "invalid"
    assert "登录页" in result.parse_message
    assert result.job_description == ""
    assert gateway.calls == []


def test_search_page_is_rejected_before_identity_extraction() -> None:
    gateway = FakeIdentityGateway()
    raw_text = (
        "数据分析职位列表\n为您找到 80 个职位\n"
        "广州数据分析实习生招聘\n深圳Python实习生招聘"
    )

    result = JobParsingService(gateway=gateway).parse(raw_text)

    assert result.parse_status == "invalid"
    assert "搜索或列表页" in result.parse_message
    assert result.job_description == ""
    assert gateway.calls == []
