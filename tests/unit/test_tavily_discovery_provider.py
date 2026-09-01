import pytest

from backend.discovery.providers.base import (
    JobDiscoveryConfigurationError,
    JobDiscoveryProviderError,
)
from backend.discovery.providers.tavily import TavilyJobDiscoveryProvider


class FakeTavilyClient:
    def __init__(self) -> None:
        self.search_kwargs = None
        self.extract_kwargs = None

    def search(self, **kwargs):
        self.search_kwargs = kwargs
        return {
            "results": [
                {
                    "title": "Python Intern 招聘",
                    "url": "https://www.example.com/jobs/1",
                    "content": "深圳 Python 实习岗位",
                }
            ]
        }

    def extract(self, **kwargs):
        self.extract_kwargs = kwargs
        return {
            "results": [
                {
                    "url": kwargs["urls"],
                    "raw_content": "公司：示例科技\n岗位：Python 实习生",
                }
            ]
        }


def test_search_uses_basic_tavily_parameters() -> None:
    client = FakeTavilyClient()
    provider = TavilyJobDiscoveryProvider("test-key", client=client)

    results = provider.search_jobs("深圳 Python 实习 招聘", 5)

    assert client.search_kwargs == {
        "query": "深圳 Python 实习 招聘",
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    assert results[0].provider == "tavily"
    assert results[0].source_domain == "example.com"


def test_extract_uses_basic_depth_for_one_url() -> None:
    client = FakeTavilyClient()
    provider = TavilyJobDiscoveryProvider("test-key", client=client)

    content = provider.extract("https://example.com/jobs/1")

    assert content == "公司：示例科技\n岗位：Python 实习生"
    assert client.extract_kwargs == {
        "urls": "https://example.com/jobs/1",
        "extract_depth": "basic",
        "format": "markdown",
    }


def test_missing_key_is_configuration_error() -> None:
    provider = TavilyJobDiscoveryProvider(None)

    with pytest.raises(JobDiscoveryConfigurationError):
        provider.search_jobs("Python 实习", 5)


def test_tavily_exception_is_provider_error() -> None:
    class FailingClient:
        def search(self, **kwargs):
            raise RuntimeError("temporary failure")

    provider = TavilyJobDiscoveryProvider(
        "test-key",
        client=FailingClient(),
    )

    with pytest.raises(JobDiscoveryProviderError):
        provider.search_jobs("Python 实习", 5)


def test_extract_without_content_is_provider_error() -> None:
    class EmptyClient:
        def extract(self, **kwargs):
            return {"results": [], "failed_results": [kwargs["urls"]]}

    provider = TavilyJobDiscoveryProvider(
        "test-key",
        client=EmptyClient(),
    )

    with pytest.raises(JobDiscoveryProviderError):
        provider.extract("https://example.com/jobs/1")
