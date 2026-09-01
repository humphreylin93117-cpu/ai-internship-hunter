from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.discovery.providers.base import JobDiscoveryProvider
from backend.discovery.scorer import JobResultScorer
from backend.discovery.url_classifier import JobDetailUrlClassifier
from backend.parsers.text_cleaner import JobTextCleaner
from backend.schemas.discovery import (
    DiscoveredJob,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobExtractResponse,
)


class JobDiscoveryService:
    MAX_QUERIES = 8
    RESULTS_PER_QUERY = 10
    MAX_RESULTS = 20
    TRACKING_PARAMETERS = {
        "fbclid",
        "gclid",
        "spm",
        "from",
        "source",
        "ref",
        "referrer",
        "tracking",
        "campaign",
    }
    def __init__(
        self,
        provider: JobDiscoveryProvider,
        cleaner: Optional[JobTextCleaner] = None,
        result_scorer: Optional[JobResultScorer] = None,
        url_classifier: Optional[JobDetailUrlClassifier] = None,
    ) -> None:
        self._provider = provider
        self._cleaner = cleaner or JobTextCleaner()
        self._result_scorer = result_scorer or JobResultScorer()
        self._url_classifier = url_classifier or JobDetailUrlClassifier()

    def discover(
        self,
        request: JobDiscoveryRequest,
    ) -> JobDiscoveryResponse:
        queries = self.build_queries(request.cities, request.keywords)
        discovered = []
        seen_urls = set()
        rejected_urls = set()
        attempted_queries = []
        target_count = min(request.max_results, self.MAX_RESULTS)

        for query in queries:
            attempted_queries.append(query)
            results = self._provider.search_jobs(
                query=query,
                max_results=self.RESULTS_PER_QUERY,
            )
            for job in results:
                normalized_url = self.normalize_url(job.url)
                if (
                    not normalized_url
                    or normalized_url in seen_urls
                    or normalized_url in rejected_urls
                ):
                    continue
                if not self._url_classifier.is_detail_url(
                    normalized_url,
                    job.source_domain,
                ):
                    rejected_urls.add(normalized_url)
                    continue
                if not self._result_scorer.accepts(job, normalized_url):
                    continue
                seen_urls.add(normalized_url)
                discovered.append(job.model_copy(update={"url": normalized_url}))
                if len(discovered) >= target_count:
                    return JobDiscoveryResponse(
                        query=" | ".join(attempted_queries),
                        results=discovered,
                    )

        return JobDiscoveryResponse(
            query=" | ".join(attempted_queries),
            results=discovered,
        )

    def extract(self, url: str) -> JobExtractResponse:
        result = self._cleaner.inspect(self._provider.extract(url))
        return JobExtractResponse(
            url=url,
            content=result.text if result.is_single_job else "",
            is_complete=result.is_single_job,
            warning=result.reason,
        )

    @classmethod
    def build_queries(
        cls,
        cities: list[str],
        keywords: list[str],
    ) -> list[str]:
        queries = []
        base_pairs = [
            (city, keyword)
            for keyword in keywords
            for city in cities
        ]
        templates = (
            "{city} {keyword} 实习 招聘",
            "{city} {keyword} 实习生 职位",
            "{city} {keyword} 校园招聘",
            "{city} {keyword} intern job",
            "{city} {keyword} 招聘 职位描述",
            "{city} {keyword} 招聘 任职要求",
            "{city} {keyword} 实习 工作内容",
            "{city} {keyword} 校招 岗位职责",
        )
        for template in templates:
            for city, keyword in base_pairs:
                query = template.format(city=city, keyword=keyword)
                if query in queries:
                    continue
                queries.append(query)
                if len(queries) >= cls.MAX_QUERIES:
                    return queries
        return queries

    @classmethod
    def normalize_url(cls, url: str) -> str:
        normalized = url.strip()
        if not normalized:
            return ""
        parsed = urlsplit(normalized)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query_items = [
            (key, value)
            for key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if not key.lower().startswith("utm_")
            and key.lower() not in cls.TRACKING_PARAMETERS
        ]
        query = urlencode(sorted(query_items))
        return urlunsplit((scheme, netloc, path, query, ""))
