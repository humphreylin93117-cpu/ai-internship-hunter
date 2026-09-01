import re
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, urlsplit

from backend.schemas.discovery import DiscoveredJob


class JobDiscoveryFilter:
    """Score discovery candidates and keep likely single-job detail pages."""

    MIN_TITLE_SCORE = 3
    MIN_SNIPPET_SCORE = 2

    _JOB_TITLE_PATTERN = re.compile(
        r"(?:实习生?|工程师|分析师|设计师|经理|专员|顾问|开发|算法|"
        r"产品|运营|销售|财务|法务|研究员|"
        r"intern(?:ship)?|engineer|analyst|developer|manager|"
        r"specialist|consultant|scientist|designer)",
        re.IGNORECASE,
    )
    _RECRUITMENT_TITLE_PATTERN = re.compile(
        r"(?:招聘|职位|岗位|job|career)",
        re.IGNORECASE,
    )
    _COMPANY_TITLE_PATTERN = re.compile(
        r"(?:有限公司|有限责任公司|集团|银行|事务所|研究院|科技|"
        r"company|corporation|corp\.?|inc\.?)",
        re.IGNORECASE,
    )
    _DETAIL_TITLE_FORMAT_PATTERN = re.compile(
        r"(?:【[^】]+】|「[^」]+」|[_|｜]|\s[-–—]\s)"
    )
    _GENERIC_TITLE_PATTERN = re.compile(
        r"(?:搜索结果|职位列表|岗位列表|职位大全|招聘大全|城市频道|"
        r"招聘频道|职位频道|热门职位|最新职位|全部职位|找工作|"
        r"jobs?\s+in\b|job\s+search|linkedin\s+jobs)",
        re.IGNORECASE,
    )
    _AGGREGATE_TITLE_PATTERN = re.compile(
        r"(?:招聘网[_-]?20\d{2}年|20\d{2}年.*招聘信息|"
        r"\d+\s*(?:个|条|家|万)\s*[^，。|]{0,24}(?:职位|岗位|招聘)|"
        r"招聘专场|职位合集|岗位合集)",
        re.IGNORECASE,
    )
    _WEAK_AGGREGATE_TITLE_PATTERN = re.compile(
        r"(?:招聘信息|招聘网|职位信息|人才网|求职网)",
        re.IGNORECASE,
    )
    _GENERIC_ONLY_TITLE_PATTERN = re.compile(
        r"^(?:招聘|实习)?\s*(?:职位|岗位)\s*\d*$",
        re.IGNORECASE,
    )
    _COUNT_AGGREGATE_PATTERN = re.compile(
        r"(?:本期新增|共有|共计|汇聚|精选|提供)?\s*"
        r"\d+\s*(?:个|条|家|万)\s*[^，。；;]{0,24}"
        r"(?:职位|岗位|招聘|公司)",
        re.IGNORECASE,
    )
    _SNIPPET_NAVIGATION_PATTERN = re.compile(
        r"(?:首页|职位列表|岗位列表|招聘频道|职位频道|城市招聘|"
        r"找工作|找实习|企业入口|网站导航|关于我们|联系我们|"
        r"客户服务|隐私政策|职位百科|校招频道)",
        re.IGNORECASE,
    )
    _SNIPPET_DUTY_PATTERN = re.compile(
        r"(?:负责|参与|协助|岗位职责|职位描述|工作内容|主要职责)"
    )
    _SNIPPET_REQUIREMENT_PATTERN = re.compile(
        r"(?:任职要求|岗位要求|职位要求|要求|熟悉|具备|优先)"
    )
    _SNIPPET_COMPENSATION_PATTERN = re.compile(
        r"(?:薪资|薪酬|待遇|\d+(?:-\d+)?[Kk]|元/天|元/月)"
    )
    _SNIPPET_ATTRIBUTE_PATTERN = re.compile(
        r"(?:工作地点|职位地点|学历|本科|大专|经验|招\d+人|"
        r"广州|深圳|北京|上海|杭州|成都)"
    )
    _SNIPPET_INTERNSHIP_PATTERN = re.compile(
        r"(?:实习时间|实习期|每周\d+天|尽快入职|到岗)"
    )
    _BLACKLIST_PATH_PATTERNS = (
        re.compile(r"/(?:search|job-search|jobs-search)(?:/|$)"),
        re.compile(r"/(?:jobs?|positions?|vacancies?)/?$"),
        re.compile(
            r"/(?:city|cities|channel|channels|category|categories|"
            r"list)(?:/|$)"
        ),
        re.compile(r"/jobs/(?:collections|recommendations)(?:/|$)"),
    )
    _DETAIL_PATH_PATTERN = re.compile(
        r"(?:/jobs?/view/|/job[_-]?detail/|/jobs?/\d+|"
        r"/positions?/\d+|\.shtml$)",
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

    def __init__(self, current_year: Optional[int] = None) -> None:
        self._current_year = current_year or datetime.now().year

    def accepts(self, job: DiscoveredJob, normalized_url: str) -> bool:
        return (
            not self.is_blacklisted_url(normalized_url)
            and self.title_quality_score(job.title) >= self.MIN_TITLE_SCORE
            and self.snippet_quality_score(job.snippet)
            >= self.MIN_SNIPPET_SCORE
        )

    def is_blacklisted_url(self, url: str) -> bool:
        parsed = urlsplit(url.strip())
        host = parsed.netloc.lower().split(":", 1)[0]
        path = parsed.path.lower().rstrip("/") or "/"
        query_keys = {
            key.casefold() for key, _ in parse_qsl(parsed.query)
        }

        if not host:
            return True
        if host == "linkedin.com" or host.endswith(".linkedin.com"):
            if "/jobs" in path and "/jobs/view/" not in f"{path}/":
                return True
        if host == "zhipin.com" or host.endswith(".zhipin.com"):
            if path.startswith("/web/geek/job"):
                return True
        if host == "liepin.com" or host.endswith(".liepin.com"):
            if path.startswith("/zhaopin") or path.startswith("/city-"):
                return True
        if host == "zhaopin.com" or host.endswith(".zhaopin.com"):
            if path.startswith("/sou") or "searchresult" in path:
                return True
        if host == "51job.com" or host.endswith(".51job.com"):
            if path.startswith("/search") or path.startswith("/list"):
                return True

        if any(pattern.search(path) for pattern in self._BLACKLIST_PATH_PATTERNS):
            return True
        return bool(
            query_keys & self._SEARCH_QUERY_KEYS
            and not self._DETAIL_PATH_PATTERN.search(path)
        )

    def title_quality_score(self, title: str) -> int:
        normalized = re.sub(r"\s+", " ", title).strip()
        if not normalized:
            return -10

        score = 0
        if self._JOB_TITLE_PATTERN.search(normalized):
            score += 3
        if self._RECRUITMENT_TITLE_PATTERN.search(normalized):
            score += 1
        if self._COMPANY_TITLE_PATTERN.search(normalized):
            score += 1
        if self._DETAIL_TITLE_FORMAT_PATTERN.search(normalized):
            score += 1
        if 5 <= len(normalized) <= 160:
            score += 1
        if self._WEAK_AGGREGATE_TITLE_PATTERN.search(normalized):
            score -= 3
        if self._GENERIC_TITLE_PATTERN.search(normalized):
            score -= 6
        if self._AGGREGATE_TITLE_PATTERN.search(normalized):
            score -= 7
        if self._GENERIC_ONLY_TITLE_PATTERN.match(normalized):
            score -= 6
        if self._contains_stale_year(normalized) or (
            self._contains_stale_cohort(normalized)
        ):
            score -= 5
        return score

    def snippet_quality_score(self, snippet: str) -> int:
        normalized = re.sub(r"\s+", " ", snippet).strip()
        if not normalized:
            return -10

        score = 1 if 20 <= len(normalized) <= 1_000 else 0
        if self._SNIPPET_DUTY_PATTERN.search(normalized):
            score += 2
        if self._SNIPPET_REQUIREMENT_PATTERN.search(normalized):
            score += 2
        if self._SNIPPET_COMPENSATION_PATTERN.search(normalized):
            score += 1
        if self._SNIPPET_ATTRIBUTE_PATTERN.search(normalized):
            score += 1
        if self._SNIPPET_INTERNSHIP_PATTERN.search(normalized):
            score += 2
        if self._COUNT_AGGREGATE_PATTERN.search(normalized):
            score -= 8
        if self._SNIPPET_NAVIGATION_PATTERN.search(normalized):
            score -= 5
        if self._contains_stale_year(normalized):
            score -= 5
        return score

    def _contains_stale_year(self, text: str) -> bool:
        years = [int(value) for value in re.findall(r"\b20\d{2}\b", text)]
        return bool(years and max(years) < self._current_year)

    def _contains_stale_cohort(self, text: str) -> bool:
        cohorts = [int(value) for value in re.findall(r"(?<!\d)(\d{2})届", text)]
        return bool(
            cohorts
            and max(cohorts) < self._current_year % 100
        )
