from backend.parsers.text_cleaner import (
    INCOMPLETE_JOB_MESSAGE,
    JobTextCleaner,
)


def test_cleaner_keeps_job_details_and_cuts_page_tail() -> None:
    raw_text = (
        "# 数据分析实习生\n"
        "公司：示例科技\n薪资：150元/天\n工作地点：广州\n"
        "岗位职责：整理业务数据并制作分析报告。\n"
        "任职要求：熟悉 SQL、Excel，有良好的沟通能力。\n"
        "相关推荐\n"
        "[广州数据分析师招聘](https://example.com/2)\n"
        "猎聘温馨提示\n请勿向招聘方转账"
    )

    result = JobTextCleaner().inspect(raw_text)

    assert result.is_single_job is True
    assert "薪资：150元/天" in result.text
    assert "任职要求" in result.text
    assert "相关推荐" not in result.text
    assert "温馨提示" not in result.text


def test_cleaner_rejects_search_or_list_page() -> None:
    links = "\n".join(
        f"[广州数据分析师招聘{i}](https://example.com/jobs/{i})"
        for i in range(10)
    )
    result = JobTextCleaner().inspect(
        "广州数据分析职位列表\n为您找到 128 个职位\n" + links
    )

    assert result.is_single_job is False
    assert result.reason == INCOMPLETE_JOB_MESSAGE


def test_cleaner_rejects_short_search_snippet() -> None:
    result = JobTextCleaner().inspect(
        "广州 Python 实习生招聘\n多个热门岗位正在招聘，点击查看详情。"
    )

    assert result.is_single_job is False


def test_cleaner_extracts_liepin_job_body_and_removes_page_noise() -> None:
    raw_text = (
        "【广州 数据分析实习生招聘】-伟亿国际有限公司广州招聘信息-猎聘\n"
        "数据分析实习生 100-150元/天\n"
        "广州-海珠区\n"
        "[收藏](javascript:void(0);)\n"
        "[聊一聊](javascript;)\n"
        "联系人：李女士\n"
        "招聘主管：王经理\n"
        "[伟亿国际有限公司](https://www.liepin.com/company/123)\n"
        "公司链接：https://www.liepin.com/company/123\n"
        "职位介绍\n"
        "岗位职责：负责业务数据整理、分析及可视化报告。\n"
        "任职要求：本科在读，熟悉 SQL 和 Excel。\n"
        "技能要求：数据分析、SQL、Python。\n"
        "[岗位相关说明](https://example.com/guide) 请以实际沟通为准。\n"
        "查看更多职位\n"
        "[广州商业分析实习生](https://www.liepin.com/job/2)\n"
        "相似职位\n"
        "其他推荐岗位"
    )

    result = JobTextCleaner().inspect(raw_text)

    assert result.is_single_job is True
    assert result.text.startswith("数据分析实习生 100-150元/天")
    assert "广州-海珠区" in result.text
    assert "职位介绍" in result.text
    assert "岗位职责" in result.text
    assert "任职要求" in result.text
    assert "技能要求" in result.text
    assert "岗位相关说明 请以实际沟通为准。" in result.text
    assert "[" not in result.text
    assert "](" not in result.text
    assert "javascript" not in result.text
    assert "收藏" not in result.text
    assert "聊一聊" not in result.text
    assert "联系人" not in result.text
    assert "招聘主管" not in result.text
    assert "伟亿国际有限公司" not in result.text
    assert "公司链接" not in result.text
    assert "查看更多职位" not in result.text
    assert "商业分析实习生" not in result.text
    assert "相似职位" not in result.text


def test_markdown_link_cleanup_does_not_change_other_site_boundaries() -> None:
    raw_text = (
        "公司：示例科技\n"
        "岗位：Python 实习生\n"
        "岗位职责：[阅读接口文档](https://docs.example.com)并开发功能。\n"
        "任职要求：熟悉 Python 和 FastAPI。"
    )

    result = JobTextCleaner().inspect(raw_text)

    assert result.is_single_job is True
    assert result.text.startswith("公司：示例科技")
    assert "岗位职责：阅读接口文档并开发功能。" in result.text
    assert "https://" not in result.text


def test_generic_cleaner_locates_job_body_and_keeps_company_section() -> None:
    raw_text = (
        "首页\n找工作\n职位分类\nIT互联网\n校园招聘\n"
        "薪资：8-10K/月\n工作地点：广州\n学历：本科\n"
        "公司简介\n示例科技专注于企业数据服务。\n"
        "职位描述\n负责业务数据分析、指标建设和可视化。\n"
        "岗位职责\n1. 整理业务数据并输出分析报告。\n"
        "任职要求\n1. 熟悉 SQL、Excel 和 Python。\n"
        "热门推荐\n数据产品经理\n数据开发工程师"
    )

    result = JobTextCleaner().inspect(raw_text)

    assert result.is_single_job is True
    assert "薪资：8-10K/月" in result.text
    assert "工作地点：广州" in result.text
    assert "职位描述" in result.text
    assert "岗位职责" in result.text
    assert "任职要求" in result.text
    assert "公司简介\n示例科技专注于企业数据服务。" in result.text
    assert result.text.index("公司简介") > result.text.index("任职要求")
    assert "首页" not in result.text
    assert "职位分类" not in result.text
    assert "热门推荐" not in result.text
    assert "数据产品经理" not in result.text


def test_html_cleaner_removes_non_content_elements_before_jd_detection() -> None:
    raw_html = """
    <html>
      <head><style>.hidden { display: none; }</style></head>
      <body>
        <header>首页 登录 注册</header>
        <nav>职位频道 公司频道 校园招聘</nav>
        <script>window.tracking = 'recommended jobs';</script>
        <main>
          <p>薪资：150元/天</p>
          <p>工作地点：深圳</p>
          <section><h2>职位描述</h2><p>协助建设数据报表。</p></section>
          <section><h2>任职要求</h2><p>熟悉 SQL 和 Excel。</p></section>
          <section><h2>公司简介</h2><p>示例科技提供数据服务。</p></section>
        </main>
        <aside>推荐岗位：商业分析师</aside>
        <footer>隐私政策 联系我们</footer>
      </body>
    </html>
    """

    result = JobTextCleaner().inspect(raw_html)

    assert result.is_single_job is True
    assert "薪资：150元/天" in result.text
    assert "工作地点：深圳" in result.text
    assert "职位描述" in result.text
    assert "任职要求" in result.text
    assert "公司简介" in result.text
    assert "示例科技提供数据服务。" in result.text
    assert result.text.index("公司简介") > result.text.index("任职要求")
    assert "window.tracking" not in result.text
    assert "职位频道" not in result.text
    assert "推荐岗位" not in result.text
    assert "隐私政策" not in result.text
