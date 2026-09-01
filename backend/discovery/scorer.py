import re
from urllib.parse import parse_qsl, urlsplit

from backend.schemas.discovery import DiscoveredJob


class JobResultScorer:
    """Estimate whether a search result represents one real job opening."""

    MIN_AUTHENTICITY_SCORE = 35

    _ROLE_PATTERN = re.compile(
        r"(?:实习生?|工程师|分析师|设计师|经理|专员|顾问|开发|算法|"
        r"产品|运营|销售|财务|法务|研究员|"
        r"intern(?:ship)?|engineer|analyst|developer|manager|"
        r"specialist|consultant|scientist|designer)",
        re.IGNORECASE,
    )
    _HIRING_PATTERN = re.compile(
        r"(?:招聘|职位|岗位|校招|社招|job|career|hiring)",
        re.IGNORECASE,
    )
    _COMPANY_PATTERN = re.compile(
        r"(?:有限公司|有限责任公司|集团|银行|事务所|研究院|科技|"
        r"company|corporation|corp\.?|inc\.?)",
        re.IGNORECASE,
    )
    _GENERIC_PAGE_PATTERN = re.compile(
        r"(?:岗位大全|职位大全|招聘大全|岗位列表|职位列表|招聘列表|"
        r"招聘频道|职位频道|岗位频道|搜索结果|全部职位|全部岗位|"
        r"热门职位|最新职位|职位合集|岗位合集|招聘专场|"
        r"jobs?\s+in\b|job\s+search|linkedin\s+jobs)",
        re.IGNORECASE,
    )
    _NON_JOB_PATTERN = re.compile(
        r"(?:教程|课程|培训|学习指南|入门指南|百科|行业报告|"
        r"求职攻略|面试攻略|新闻|资讯|官网首页|公司官网|官网)$",
        re.IGNORECASE,
    )
    _COUNT_PATTERN = re.compile(
        r"(?:共有|共计|为您找到|本期新增|汇聚|精选)?\s*"
        r"\d[\d,]*\+?\s*(?:个|条|家|万)?\s*"
        r"(?:职位|岗位|招聘|jobs?)",
        re.IGNORECASE,
    )
    _DETAIL_PATH_PATTERN = re.compile(
        r"(?:/jobs?/view/|/job[_-]?detail/|/jobs?/[^/]+\d[^/]*$|"
        r"/positions?/[^/]+|\.shtml$)",
        re.IGNORECASE,
    )
    _LIST_PATH_PATTERN = re.compile(
        r"(?:/(?:search|job-search|jobs-search)(?:/|$)|"
        r"/(?:jobs?|positions?|vacancies?)/?$|"
        r"/(?:city|channel|category|list)(?:/|$)|"
        r"/jobs/(?:collections|recommendations)(?:/|$))",
        re.IGNORECASE,
    )
    _SEARCH_QUERY_KEYS = {
        "q",
        "query",
        "keyword",
        "keywords",
        "kw",
        "search",
        "location",
    }
    _DUTY_PATTERN = re.compile(
        r"(?:负责|参与|协助|岗位职责|职位描述|工作内容|主要职责)",
        re.IGNORECASE,
    )
    _REQUIREMENT_PATTERN = re.compile(
        r"(?:任职要求|岗位要求|职位要求|要求|熟悉|具备|优先)",
        re.IGNORECASE,
    )
    _ATTRIBUTE_PATTERN = re.compile(
        r"(?:工作地点|职位地点|学历|本科|大专|经验|薪资|薪酬|"
        r"待遇|招\d+人|每周\d+天|尽快入职|到岗|"
        r"\d+(?:-\d+)?[Kk]|元/天|元/月)",
        re.IGNORECASE,
    )
    _NAVIGATION_PATTERN = re.compile(
        r"(?:首页|网站导航|企业入口|关于我们|联系我们|隐私政策|"
        r"职位百科|校招频道|查看更多职位|热门城市)",
        re.IGNORECASE,
    )

    def score(self, job: DiscoveredJob, normalized_url: str) -> int:
        title = re.sub(r"\s+", " ", job.title).strip()
        snippet = re.sub(r"\s+", " ", job.snippet).strip()
        score = 0

        if self._ROLE_PATTERN.search(title):
            score += 30
        if self._HIRING_PATTERN.search(title):
            score += 18
        if self._COMPANY_PATTERN.search(title):
            score += 5
        if 5 <= len(title) <= 180:
            score += 5
        if self._DETAIL_PATH_PATTERN.search(
            urlsplit(normalized_url).path.rstrip("/")
        ):
            score += 22

        if self._DUTY_PATTERN.search(snippet):
            score += 12
        if self._REQUIREMENT_PATTERN.search(snippet):
            score += 12
        if self._ATTRIBUTE_PATTERN.search(snippet):
            score += 6

        if self._GENERIC_PAGE_PATTERN.search(title):
            score -= 70
        if self._NON_JOB_PATTERN.search(title):
            score -= 60
        if self._COUNT_PATTERN.search(f"{title} {snippet}"):
            score -= 45
        if self._NAVIGATION_PATTERN.search(snippet):
            score -= 30
        if self._is_list_url(normalized_url):
            score -= 50

        return max(0, min(100, score))

    def accepts(self, job: DiscoveredJob, normalized_url: str) -> bool:
        return (
            self.score(job, normalized_url)
            >= self.MIN_AUTHENTICITY_SCORE
        )

    @classmethod
    def _is_list_url(cls, url: str) -> bool:
        parsed = urlsplit(url)
        path = parsed.path.lower().rstrip("/") or "/"
        query_keys = {
            key.casefold() for key, _ in parse_qsl(parsed.query)
        }
        return bool(
            cls._LIST_PATH_PATTERN.search(path)
            or (
                query_keys & cls._SEARCH_QUERY_KEYS
                and not cls._DETAIL_PATH_PATTERN.search(path)
            )
        )
