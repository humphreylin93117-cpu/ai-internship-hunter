import re
from urllib.parse import parse_qsl, urlsplit


class JobDetailUrlClassifier:
    """Classify whether a URL likely represents one job detail page."""

    _KNOWN_DETAIL_PATTERNS = {
        "zhipin.com": (
            re.compile(r"^/job_detail/[^/]+", re.IGNORECASE),
        ),
        "liepin.com": (
            re.compile(r"^/job/[^/]+\.shtml$", re.IGNORECASE),
        ),
        "zhaopin.com": (
            re.compile(r"^/jobdetail/[^/]+", re.IGNORECASE),
        ),
        "linkedin.com": (
            re.compile(r"^/jobs/view/[^/]+", re.IGNORECASE),
        ),
        "shixiseng.com": (
            re.compile(r"^/intern/[^/]+", re.IGNORECASE),
        ),
        "51job.com": (
            re.compile(r"^/job/[^/]+", re.IGNORECASE),
        ),
        "lagou.com": (
            re.compile(r"^/jobs/[^/]+\.html$", re.IGNORECASE),
        ),
    }
    _GENERIC_AGGREGATE_PATH = re.compile(
        r"(?:^|/)(?:search|job-search|jobs-search|zhaopin|sou|"
        r"city|cities|channel|channels|category|categories|list|"
        r"collections|recommendations)(?:/|$)",
        re.IGNORECASE,
    )
    _GENERIC_LIST_ROOT = re.compile(
        r"^/(?:jobs?|positions?|vacancies?|careers?)/?$",
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

    def is_detail_url(
        self,
        url: str,
        source_domain: str = "",
    ) -> bool:
        parsed = urlsplit(url.strip())
        host = (
            parsed.netloc.lower().split(":", 1)[0]
            or source_domain.lower().split(":", 1)[0]
        )
        path = parsed.path.rstrip("/") or "/"
        if not host:
            return False

        known_domain = self._known_domain(host)
        if known_domain:
            return any(
                pattern.search(path)
                for pattern in self._KNOWN_DETAIL_PATTERNS[known_domain]
            )

        if self._GENERIC_AGGREGATE_PATH.search(path):
            return False
        if self._GENERIC_LIST_ROOT.search(path):
            return False
        query_keys = {
            key.casefold() for key, _ in parse_qsl(parsed.query)
        }
        if query_keys & self._SEARCH_QUERY_KEYS:
            return False
        return True

    @classmethod
    def _known_domain(cls, host: str) -> str:
        for domain in cls._KNOWN_DETAIL_PATTERNS:
            if host == domain or host.endswith(f".{domain}"):
                return domain
        return ""
