"""Job discovery providers, filtering, and shared interfaces."""

from backend.discovery.filter import JobDiscoveryFilter
from backend.discovery.scorer import JobResultScorer
from backend.discovery.url_classifier import JobDetailUrlClassifier


__all__ = [
    "JobDetailUrlClassifier",
    "JobDiscoveryFilter",
    "JobResultScorer",
]
