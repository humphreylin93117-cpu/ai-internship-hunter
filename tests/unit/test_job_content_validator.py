from backend.parsers.job_content_validator import JobContentValidator


def test_valid_job_description_is_accepted() -> None:
    validator = JobContentValidator()
    content = (
        "岗位：数据分析实习生\n"
        "岗位职责：负责业务数据分析。\n"
        "任职要求：熟悉 SQL 和 Python。"
    )

    result = validator.validate(content, content, False)

    assert result.is_valid is True
    assert result.message == "已检测到有效招聘内容"


def test_search_page_returns_specific_message() -> None:
    validator = JobContentValidator()
    content = "职位列表\n为您找到 120 个职位\n数据分析实习生\nPython实习生"

    result = validator.validate(content, content, False)

    assert result.is_valid is False
    assert "搜索或列表页" in result.message


def test_login_page_returns_specific_message() -> None:
    validator = JobContentValidator()
    content = "账号登录\n手机号登录\n验证码登录\n登录后查看职位详情"

    result = validator.validate(content, content, False)

    assert result.is_valid is False
    assert "登录页" in result.message


def test_navigation_page_returns_specific_message() -> None:
    validator = JobContentValidator()
    content = "首页 职位分类 热门城市 热门公司 企业入口 关于我们"

    result = validator.validate(content, content, False)

    assert result.is_valid is False
    assert "导航页" in result.message


def test_cleaner_confirmed_single_job_takes_priority_over_page_chrome() -> None:
    validator = JobContentValidator()
    raw = "首页 登录 招聘频道\n职位描述：负责开发\n任职要求：熟悉 Python"
    cleaned = "职位描述：负责开发\n任职要求：熟悉 Python"

    result = validator.validate(raw, cleaned, True)

    assert result.is_valid is True


def test_explicit_search_page_is_rejected_even_with_job_fragments() -> None:
    validator = JobContentValidator()
    content = (
        "职位列表 为您找到 20 个职位\n"
        "岗位职责：负责数据分析。任职要求：熟悉 SQL。"
    )

    result = validator.validate(content, content, True)

    assert result.is_valid is False
    assert "搜索或列表页" in result.message
