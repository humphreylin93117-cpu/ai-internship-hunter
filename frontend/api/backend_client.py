import os
from typing import Any, Optional

import httpx


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 60.0
RESUME_OPTIMIZATION_TIMEOUT = httpx.Timeout(180.0, connect=5.0)
INTERVIEW_PREPARATION_TIMEOUT = httpx.Timeout(180.0, connect=5.0)


class BackendClientError(RuntimeError):
    """Base error raised when the backend cannot fulfill a request."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendConnectionError(BackendClientError):
    """Raised when the FastAPI backend cannot be reached."""


class BackendTimeoutError(BackendClientError):
    """Raised when the backend does not respond before the timeout."""


class BackendClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: Optional[httpx.Client] = None,
    ) -> None:
        configured_url = base_url or os.getenv(
            "BACKEND_URL",
            DEFAULT_BACKEND_URL,
        )
        self.base_url = configured_url.rstrip("/")
        self._default_timeout = httpx.Timeout(timeout)
        self._client = client or httpx.Client(
            timeout=self._default_timeout
        )

    def _request(
        self,
        method: str,
        path: str,
        request_timeout: Optional[httpx.Timeout] = None,
        timeout_message: str = "后端请求超时，请稍后重试。",
        **kwargs: Any,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                timeout=request_timeout or self._default_timeout,
                **kwargs,
            )
        except httpx.ConnectError as exc:
            raise BackendConnectionError(
                "无法连接 FastAPI 后端，请确认后端已启动。"
            ) from exc
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError(timeout_message) from exc
        except httpx.RequestError as exc:
            raise BackendClientError(f"后端请求失败：{exc}") from exc

        if response.is_error:
            detail = self._extract_error_detail(response)
            raise BackendClientError(detail, status_code=response.status_code)

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise BackendClientError("后端返回了无法解析的数据。") from exc

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"后端请求失败（HTTP {response.status_code}）。"

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if detail is not None:
                return str(detail)
        return f"后端请求失败（HTTP {response.status_code}）。"

    def analyze_job(self, job_description: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/jobs/analyze",
            json={"job_description": job_description},
        )

    def parse_job(
        self,
        raw_text: str,
        job_url: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/jobs/parse",
            json={"raw_text": raw_text, "job_url": job_url or None},
        )

    def check_job_duplicate(
        self,
        company: str,
        position: str,
        job_description: str,
        job_url: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/jobs/check-duplicate",
            json={
                "company": company,
                "position": position,
                "job_description": job_description,
                "job_url": job_url or None,
            },
        )

    def discover_jobs(
        self,
        keywords: list[str],
        cities: list[str],
        max_results: int = 10,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/discovery/jobs",
            json={
                "keywords": keywords,
                "cities": cities,
                "max_results": max_results,
            },
        )

    def extract_job_content(self, url: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/discovery/extract",
            json={"url": url},
        )

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/jobs", json=job)

    def get_dashboard_summary(self) -> dict[str, Any]:
        return self._request("GET", "/dashboard/summary")

    def list_jobs(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if company and company.strip():
            params["company"] = company.strip()
        if min_match_score is not None:
            params["min_match_score"] = min_match_score
        return self._request("GET", "/jobs", params=params)

    def get_job(self, job_id: int) -> dict[str, Any]:
        return self._request("GET", f"/jobs/{job_id}")

    def update_job_status(
        self,
        job_id: int,
        status: str,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/jobs/{job_id}/status",
            json={"status": status},
        )

    def list_application_queue(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"sort_order": sort_order}
        if status:
            params["status"] = status
        if company and company.strip():
            params["company"] = company.strip()
        if min_match_score is not None:
            params["min_match_score"] = min_match_score
        return self._request("GET", "/applications/queue", params=params)

    def add_to_application_queue(self, job_id: int) -> dict[str, Any]:
        return self._request("POST", f"/applications/queue/{job_id}")

    def remove_from_application_queue(self, job_id: int) -> None:
        self._request("DELETE", f"/applications/queue/{job_id}")

    def mark_application_applied(self, job_id: int) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/applications/queue/{job_id}/apply",
        )

    def optimize_resume(
        self,
        job_id: int,
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"job_id": job_id}
        if force_regenerate:
            payload["force_regenerate"] = True
        try:
            return self._request(
                "POST",
                "/resumes/optimize",
                request_timeout=RESUME_OPTIMIZATION_TIMEOUT,
                timeout_message="简历优化请求超时，请稍后重试。",
                json=payload,
            )
        except BackendClientError as exc:
            if exc.status_code == 502:
                raise BackendClientError(
                    "LLM简历优化失败",
                    status_code=502,
                ) from exc
            raise

    def get_cached_resume_optimization(
        self,
        job_id: int,
    ) -> Optional[dict[str, Any]]:
        return self._request("GET", f"/resumes/optimizations/{job_id}")

    def prepare_interview(
        self,
        job_id: int,
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"job_id": job_id}
        if force_regenerate:
            payload["force_regenerate"] = True
        try:
            return self._request(
                "POST",
                "/interviews/prepare",
                request_timeout=INTERVIEW_PREPARATION_TIMEOUT,
                timeout_message="面试准备请求超时，请稍后重试。",
                json=payload,
            )
        except BackendClientError as exc:
            if exc.status_code == 502:
                raise BackendClientError(
                    "LLM面试准备失败",
                    status_code=502,
                ) from exc
            raise

    def get_cached_interview_preparation(
        self,
        job_id: int,
    ) -> Optional[dict[str, Any]]:
        return self._request("GET", f"/interviews/preparations/{job_id}")

    def close(self) -> None:
        self._client.close()
