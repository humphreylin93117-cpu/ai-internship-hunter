import pytest

from backend.discovery.url_classifier import JobDetailUrlClassifier


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.zhipin.com/zhaopin/shuju-fenxi/", False),
        ("https://www.zhipin.com/job_detail/abc123.html", True),
        ("https://www.liepin.com/job/1975804533.shtml", True),
        ("https://www.zhaopin.com/jobdetail/CC123.htm", True),
        (
            "https://www.linkedin.com/jobs/search/?keywords=analyst",
            False,
        ),
        ("https://www.linkedin.com/jobs/view/123456789/", True),
    ],
)
def test_known_recruitment_domains_use_detail_allowlists(
    url: str,
    expected: bool,
) -> None:
    classifier = JobDetailUrlClassifier()

    assert classifier.is_detail_url(url) is expected


def test_unknown_domain_rejects_obvious_city_and_search_pages() -> None:
    classifier = JobDetailUrlClassifier()

    assert classifier.is_detail_url(
        "https://careers.example.com/city/guangzhou"
    ) is False
    assert classifier.is_detail_url(
        "https://careers.example.com/jobs?keyword=Python"
    ) is False
    assert classifier.is_detail_url(
        "https://careers.example.com/openings/python-intern"
    ) is True
