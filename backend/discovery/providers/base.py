from abc import ABC, abstractmethod

from backend.schemas.discovery import DiscoveredJob


class JobDiscoveryConfigurationError(RuntimeError):
    """Raised when the selected discovery provider is not configured."""


class JobDiscoveryProviderError(RuntimeError):
    """Raised when a discovery provider request cannot be completed."""


class JobDiscoveryProvider(ABC):
    @abstractmethod
    def search_jobs(
        self,
        query: str,
        max_results: int,
    ) -> list[DiscoveredJob]:
        """Search public web pages for possible job listings."""

    @abstractmethod
    def extract(self, url: str) -> str:
        """Extract public page content for one user-selected URL."""
