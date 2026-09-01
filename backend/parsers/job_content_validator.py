import re
from dataclasses import dataclass


@dataclass(frozen=True)
class JobContentValidationResult:
    is_valid: bool
    message: str


class JobContentValidator:
    """Reject non-job web pages before identity extraction or LLM use."""

    SUCCESS_MESSAGE = "已检测到有效招聘内容"
    _SEARCH_PAGE_PATTERN = re.compile(
        r"(?:搜索结果|职位列表|岗位列表|职位大全|岗位大全|招聘大全|"
        r"招聘频道|职位频道|岗位频道|全部职位|全部岗位|筛选职位|"
        r"为您找到\s*\d+|共(?:有|计)?\s*\d+\s*(?:个|条)?"
        r"(?:职位|岗位)|job\s+search|search\s+jobs)",
        re.IGNORECASE,
    )
    _LOGIN_PAGE_PATTERN = re.compile(
        r"(?:请先登录|登录后(?:查看|继续)|账号登录|密码登录|"
        r"手机号登录|验证码登录|扫码登录|登录\s*/\s*注册|"
        r"sign\s+in\s+to\s+(?:continue|view)|log\s+in\s+to\s+view)",
        re.IGNORECASE,
    )
    _NAVIGATION_TERMS = (
        "首页",
        "网站导航",
        "职位分类",
        "热门城市",
        "热门公司",
        "企业入口",
        "关于我们",
        "联系我们",
        "隐私政策",
        "用户协议",
        "下载APP",
    )
    _COMPANY_PATTERN = re.compile(
        r"^\s*(?:公司(?:名称)?|company)\s*[：:]",
        re.IGNORECASE | re.MULTILINE,
    )
    _POSITION_PATTERN = re.compile(
        r"^\s*(?:岗位(?:名称)?|招聘岗位|职位(?:名称)?|招聘职位|"
        r"position|job\s+title)\s*[：:]",
        re.IGNORECASE | re.MULTILINE,
    )
    _RESPONSIBILITY_PATTERN = re.compile(
        r"(?:岗位职责|职位职责|职位描述|岗位描述|工作内容|职责\s*[：:]|"
        r"负责|参与|协助)",
        re.IGNORECASE,
    )
    _REQUIREMENT_PATTERN = re.compile(
        r"(?:任职要求|岗位要求|职位要求|技能要求|资格要求|"
        r"要求\s*[：:]|熟悉|具备|优先)",
        re.IGNORECASE,
    )
    _ROLE_PATTERN = re.compile(
        r"(?:实习生?|工程师|分析师|设计师|经理|专员|顾问|开发|算法|"
        r"产品|运营|销售|研究员|intern(?:ship)?|engineer|analyst|"
        r"developer|manager|specialist|scientist)",
        re.IGNORECASE,
    )

    def validate(
        self,
        raw_text: str,
        cleaned_text: str,
        cleaner_identified_single_job: bool,
    ) -> JobContentValidationResult:
        raw = self._normalize(raw_text)
        cleaned = self._normalize(cleaned_text)

        content_for_page_type = cleaned or raw
        if self._SEARCH_PAGE_PATTERN.search(content_for_page_type):
            return JobContentValidationResult(
                is_valid=False,
                message="网页内容是岗位搜索或列表页，请打开具体岗位详情页后重试",
            )
        if self._LOGIN_PAGE_PATTERN.search(raw):
            return JobContentValidationResult(
                is_valid=False,
                message="网页内容是登录页，未获取到公开招聘详情",
            )
        if cleaner_identified_single_job:
            return JobContentValidationResult(
                is_valid=True,
                message=self.SUCCESS_MESSAGE,
            )

        has_company = bool(self._COMPANY_PATTERN.search(cleaned))
        has_position = bool(self._POSITION_PATTERN.search(cleaned))
        has_responsibility = bool(
            self._RESPONSIBILITY_PATTERN.search(cleaned)
        )
        has_requirement = bool(self._REQUIREMENT_PATTERN.search(cleaned))
        has_role = bool(self._ROLE_PATTERN.search(cleaned))
        has_job_fragment = (
            (has_company and has_position)
            or (has_position and has_responsibility)
            or (has_company and has_responsibility)
            or (has_responsibility and has_requirement)
            or (has_role and (has_responsibility or has_requirement))
        )
        if has_job_fragment:
            return JobContentValidationResult(
                is_valid=True,
                message=self.SUCCESS_MESSAGE,
            )

        navigation_count = sum(
            term.casefold() in raw.casefold()
            for term in self._NAVIGATION_TERMS
        )
        if navigation_count >= 3:
            return JobContentValidationResult(
                is_valid=False,
                message="网页内容是导航页，未发现具体岗位招聘信息",
            )
        return JobContentValidationResult(
            is_valid=False,
            message="未检测到有效招聘 JD，请补充具体岗位职责和任职要求",
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
