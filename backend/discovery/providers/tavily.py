from typing import Any, Optional
from urllib.parse import urlparse

from tavily import TavilyClient

from backend.discovery.providers.base import (
    JobDiscoveryConfigurationError,
    JobDiscoveryProvider,
    JobDiscoveryProviderError,
)
from backend.schemas.discovery import DiscoveredJob


class TavilyJobDiscoveryProvider(JobDiscoveryProvider):
    def __init__(
        self,
        api_key: Optional[str],
        client: Optional[Any] = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._client = client
        if self._client is None and self._api_key:
            self._client = TavilyClient(api_key=self._api_key)

    def search_jobs(
        self,
        query: str,
        max_results: int,
    ) -> list[DiscoveredJob]:
        client = self._configured_client()
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                include_images=False,
            )
        except Exception as exc:
            raise JobDiscoveryProviderError(
                "Tavily search request failed"
            ) from exc

        results = response.get("results", [])
        if not isinstance(results, list):
            raise JobDiscoveryProviderError(
                "Tavily search returned an invalid response"
            )

        discovered = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            discovered.append(
                DiscoveredJob(
                    title=str(item.get("title") or "").strip(),
                    url=url,
                    snippet=str(item.get("content") or "").strip(),
                    source_domain=self._source_domain(url),
                    provider="tavily",
                )
            )
        return discovered

    def extract(self, url: str) -> str:
        client = self._configured_client()
        try:
            response = client.extract(
                urls=url,
                extract_depth="basic",
                format="markdown",
            )
        except Exception as exc:
            raise JobDiscoveryProviderError(
                "Tavily extract request failed"
            ) from exc

        results = response.get("results", [])
        if not isinstance(results, list) or not results:
            raise JobDiscoveryProviderError(
                "Tavily extract returned no content"
            )
        first = results[0]
        if not isinstance(first, dict):
            raise JobDiscoveryProviderError(
                "Tavily extract returned an invalid response"
            )
        content = str(
            first.get("raw_content") or first.get("content") or ""
        ).strip()
        if not content:
            raise JobDiscoveryProviderError(
                "Tavily extract returned no content"
            )
        return content

    def _configured_client(self) -> Any:
        if not self._api_key or self._client is None:
            raise JobDiscoveryConfigurationError(
                "Tavily API key is not configured"
            )
        return self._client

    @staticmethod
    def _source_domain(url: str) -> str:
        domain = urlparse(url).netloc.lower().split(":", 1)[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
