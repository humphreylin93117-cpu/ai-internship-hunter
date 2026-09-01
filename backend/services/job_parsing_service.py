import logging
import re
from typing import Optional
from urllib.parse import urlparse

from backend.ai.gateway import (
    LLMConfigurationError,
    LLMGateway,
    LLMGatewayError,
)
from backend.parsers.text_cleaner import JobTextCleaner
from backend.parsers.job_content_validator import JobContentValidator
from backend.schemas.job import JobParseResponse


logger = logging.getLogger(__name__)


class JobParsingService:
    _COMPANY_PATTERN = re.compile(
        r"^\s*(?:公司(?:名称)?|company)\s*[：:]\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _POSITION_PATTERN = re.compile(
        r"^\s*(?:岗位(?:名称)?|招聘岗位|职位(?:名称)?|招聘职位|position|job\s+title)"
        r"\s*[：:]\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    _LIEPIN_TITLE_PATTERN = re.compile(
        r"^【(?P<location>[^】\s]+)\s+(?P<position>.+?)招聘】\s*[-–—]\s*"
        r"(?P<company>.+?)(?P=location)招聘信息\s*[-–—]\s*猎聘\s*$",
        re.IGNORECASE,
    )
    _BOSS_TITLE_PATTERN = re.compile(
        r"^[「【]?(?P<position>.+?)招聘[」】]?\s*[_-]\s*"
        r"(?P<company>.+?)招聘\s*[-_]\s*BOSS直聘\s*$",
        re.IGNORECASE,
    )
    _SHIXISENG_TITLE_PATTERN = re.compile(
        r"^(?P<position>.+?)(?:招聘)?\s*[-–—_]\s*"
        r"(?P<company>.+?)\s*[-–—_]\s*实习僧\s*$",
        re.IGNORECASE,
    )
    _LEADING_LOCATION_PATTERN = re.compile(
        r"^(?:北京|上海|广州|深圳|杭州|成都|南京|武汉|西安|苏州|"
        r"天津|重庆|长沙|厦门|东莞|佛山|珠海)\s*[-· ]?\s*"
    )
    _SOURCE_DOMAINS = (
        ("liepin.com", "猎聘"),
        ("zhipin.com", "BOSS"),
        ("shixiseng.com", "实习僧"),
        ("zhaopin.com", "智联招聘"),
        ("51job.com", "前程无忧"),
        ("lagou.com", "拉勾"),
        ("linkedin.com", "LinkedIn"),
    )

    def __init__(
        self,
        cleaner: Optional[JobTextCleaner] = None,
        validator: Optional[JobContentValidator] = None,
        gateway: Optional[LLMGateway] = None,
    ) -> None:
        self._cleaner = cleaner or JobTextCleaner()
        self._validator = validator or JobContentValidator()
        self._gateway = gateway or LLMGateway()

    def parse(
        self,
        raw_text: str,
        job_url: Optional[str] = None,
    ) -> JobParseResponse:
        clean_result = self._cleaner.inspect(raw_text)
        job_description = clean_result.text
        validation = self._validator.validate(
            raw_text=raw_text,
            cleaned_text=job_description,
            cleaner_identified_single_job=clean_result.is_single_job,
        )
        source = self._infer_source(job_url, job_description)
        if not validation.is_valid:
            return JobParseResponse(
                company="",
                position="",
                job_description="",
                source=source,
                job_url=job_url,
                parse_status="invalid",
                parse_message=validation.message,
            )

        company = self._extract(job_description, self._COMPANY_PATTERN)
        position = self._extract(job_description, self._POSITION_PATTERN)
        title_company, title_position = self._extract_title_fields(raw_text)
        company = company or title_company
        position = position or title_position
        if clean_result.is_single_job and (not company or not position):
            company, position = self._fill_identity_with_llm(
                job_description,
                company,
                position,
            )
        return JobParseResponse(
            company=company,
            position=position,
            job_description=job_description,
            source=source,
            job_url=job_url,
            parse_status="success",
            parse_message=validation.message,
        )

    def _fill_identity_with_llm(
        self,
        job_description: str,
        company: str,
        position: str,
    ) -> tuple[str, str]:
        try:
            extracted = self._gateway.extract_job_identity(job_description)
        except LLMConfigurationError:
            logger.debug(
                "LLM job identity extraction skipped: API not configured"
            )
            return company, position
        except LLMGatewayError as exc:
            logger.warning(
                "LLM job identity extraction failed; using rule fallback: %s",
                exc,
            )
            return company, position
        return company or extracted.company, position or extracted.position

    @staticmethod
    def _extract(text: str, pattern: re.Pattern[str]) -> str:
        for line in text.splitlines():
            match = pattern.match(line)
            if match:
                return match.group(1).strip()
        return ""

    @classmethod
    def _extract_title_fields(cls, text: str) -> tuple[str, str]:
        candidates = [
            cls._clean_title_line(line)
            for line in text.splitlines()[:20]
            if line.strip()
        ]
        for candidate in candidates:
            for pattern in (
                cls._LIEPIN_TITLE_PATTERN,
                cls._BOSS_TITLE_PATTERN,
                cls._SHIXISENG_TITLE_PATTERN,
            ):
                match = pattern.match(candidate)
                if not match:
                    continue
                company = match.group("company").strip(" -–—_｜|")
                position = match.group("position").strip(" -–—_｜|")
                position = cls._LEADING_LOCATION_PATTERN.sub("", position)
                return company, position
        return "", ""

    @staticmethod
    def _clean_title_line(line: str) -> str:
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line.strip())
        markdown_link = re.fullmatch(r"\[([^\]]+)\]\([^\)]+\)", line)
        return markdown_link.group(1).strip() if markdown_link else line

    @staticmethod
    def _infer_source(job_url: Optional[str], raw_text: str) -> str:
        if job_url:
            host = urlparse(job_url).netloc.lower().split(":", 1)[0]
            for domain, source in JobParsingService._SOURCE_DOMAINS:
                if host == domain or host.endswith(f".{domain}"):
                    return source
            if host:
                return "官网"

        lowered = raw_text.lower()
        if "boss直聘" in lowered or "boss 直聘" in lowered:
            return "BOSS"
        if "linkedin" in lowered:
            return "LinkedIn"
        if "猎聘" in raw_text:
            return "猎聘"
        if "实习僧" in raw_text:
            return "实习僧"
        if "官网" in raw_text:
            return "官网"
        return ""
