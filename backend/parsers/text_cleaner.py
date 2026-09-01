import re
from dataclasses import dataclass
from html.parser import HTMLParser


class _VisibleHTMLTextParser(HTMLParser):
    _SKIP_TAGS = {
        "script",
        "style",
        "head",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
        "select",
        "option",
        "svg",
        "canvas",
        "template",
    }
    _BLOCK_TAGS = {
        "address",
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        lowered = tag.lower()
        if lowered in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if not self._skip_depth and lowered in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if not self._skip_depth and lowered in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


INCOMPLETE_JOB_MESSAGE = (
    "未获取到完整岗位详情，请打开原网页后粘贴完整 JD 或手动补充"
)


@dataclass(frozen=True)
class JobTextCleanResult:
    text: str
    is_single_job: bool
    reason: str = ""


class JobTextCleaner:
    """Remove common recruitment-page chrome and assess JD completeness."""

    _HARD_STOP_PATTERN = re.compile(
        r"^(?:猜你喜欢|你可能感兴趣|相关推荐|相关推荐职位|相似职位|"
        r"相关职位|相关岗位|相关招聘|推荐职位|推荐岗位|职位推荐|"
        r"岗位推荐|热门职位|热门招聘|"
        r"热门推荐|你可能还喜欢|看过该职位的人还看了|"
        r"其他招聘|更多招聘信息|更多职位|更多岗位|查看更多职位|"
        r"查看更多岗位|城市招聘|"
        r"猎聘温馨提示|安全提示|求职安全提示|防骗提示|"
        r"关于我们|网站地图|友情链接)(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _NAVIGATION_PATTERN = re.compile(
        r"^(?:首页|职位|公司|找工作|找人才|校园招聘|社会招聘|"
        r"应届生求职|登录|注册|企业登录|发布职位|搜索职位|"
        r"下载APP|隐私政策|用户协议|联系我们|帮助中心|意见反馈|"
        r"热门城市|热门公司|职位分类|频道分类|招聘频道|"
        r"求职攻略|职场资讯|全部频道)$",
        re.IGNORECASE,
    )
    _COMMON_NOISE_PATTERN = re.compile(
        r"^(?:扫码|扫描二维码|打开APP|下载客户端|切换城市|"
        r"求职者服务|企业服务|招聘服务|网站导航|返回顶部|"
        r"已有账号|立即注册|免费发布职位)(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _DETAIL_PATTERNS = (
        re.compile(r"(?:岗位|职位|工作)(?:职责|描述|内容)"),
        re.compile(r"(?:任职|岗位|职位|能力|技能)(?:要求|资格|条件)"),
        re.compile(r"(?:薪资|薪酬|待遇|元/天|元/月|K(?:/月)?)", re.IGNORECASE),
        re.compile(r"(?:工作地点|工作地址|职位地点|城市)"),
        re.compile(r"(?:学历|经验|专业|实习时间|到岗)"),
    )
    _EXPLICIT_COMPANY = re.compile(
        r"^\s*(?:公司(?:名称)?|company)\s*[：:]",
        re.I | re.M,
    )
    _EXPLICIT_POSITION = re.compile(
        r"^\s*(?:岗位(?:名称)?|招聘岗位|职位(?:名称)?|招聘职位|position|job\s+title)\s*[：:]",
        re.I | re.M,
    )
    _LIST_PAGE_PATTERN = re.compile(
        r"(?:职位列表|岗位列表|搜索结果|共\s*\d+\s*个职位|"
        r"为您找到\s*\d+|筛选职位|全部职位)"
    )
    _MARKDOWN_LINK = re.compile(
        r"\[(?P<label>[^\]]*)\]\("
        r"(?P<target>[^()\s]*(?:\([^()]*\)[^()\s]*)*)"
        r"\)"
    )
    _LIEPIN_PAGE_PATTERN = re.compile(
        r"(?:招聘信息\s*[-–—]\s*猎聘|liepin\.com)",
        re.IGNORECASE,
    )
    _LIEPIN_START_PATTERN = re.compile(
        r"^职位介绍(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _LIEPIN_METADATA_PATTERN = re.compile(
        r"(?:薪资|薪酬|待遇|\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?"
        r"(?:元/天|元/月|[Kk](?:/月)?)|工作地点|工作地址|职位地点|"
        r"(?:北京|上海|广州|深圳|杭州|成都|南京|武汉|西安|苏州|"
        r"天津|重庆|长沙|厦门|东莞|佛山|珠海)[-·]\S+)"
    )
    _LIEPIN_NOISE_PATTERN = re.compile(
        r"(?:联系人|招聘主管|招聘顾问|公司主页|公司链接|查看公司|"
        r"聊一聊|收藏|立即沟通|在线沟通)"
    )
    _HTML_PATTERN = re.compile(
        r"<\s*(?:!doctype|html|body|main|article|section|div|p|"
        r"script|style|nav|header|footer)\b",
        re.IGNORECASE,
    )
    _JOB_BODY_START_PATTERN = re.compile(
        r"^(?:职位描述|岗位描述|岗位职责|职位职责|工作职责|"
        r"工作内容|职位介绍|岗位介绍)(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _COMPANY_SECTION_PATTERN = re.compile(
        r"^(?:公司简介|公司介绍|企业简介|企业介绍|关于公司)"
        r"(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _SECTION_HEADING_PATTERN = re.compile(
        r"^(?:职位描述|岗位描述|岗位职责|职位职责|工作职责|工作内容|"
        r"职位介绍|岗位介绍|任职要求|职位要求|岗位要求|技能要求|"
        r"资格要求|薪资福利|福利待遇|公司简介|公司介绍|企业简介|"
        r"企业介绍|关于公司)(?:\s|$|[：:])",
        re.IGNORECASE,
    )
    _GENERIC_METADATA_PATTERN = re.compile(
        r"^(?:(?:公司|岗位|职位)(?:名称)?\s*[：:]|"
        r"(?:薪资|薪酬|待遇|工作地点|工作地址|职位地点|学历|经验|"
        r"专业|实习时间|到岗)(?:\s|$|[：:])|"
        r".*\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?"
        r"(?:元/天|元/月|[Kk](?:/月)?)(?:\s|$))"
    )
    _JOB_TITLE_HINT_PATTERN = re.compile(
        r"(?:实习生|工程师|分析师|设计师|经理|专员|顾问|"
        r"开发|算法|产品|运营|销售|财务|法务|招聘)$"
    )

    def clean(self, raw_text: str) -> str:
        return self.inspect(raw_text).text

    def inspect(self, raw_text: str) -> JobTextCleanResult:
        visible_text = self._extract_visible_html(raw_text)
        normalized = self._normalize(visible_text)
        original_link_count = len(self._MARKDOWN_LINK.findall(normalized))
        kept_lines: list[str] = []
        is_liepin = bool(self._LIEPIN_PAGE_PATTERN.search(normalized))
        lines = normalized.splitlines()
        if is_liepin:
            lines = self._slice_liepin_content(lines)
        else:
            lines = self._slice_generic_job_content(lines)

        for raw_line in lines:
            line = self._clean_markdown_links(raw_line.strip())
            marker = self._plain_line(line)
            if marker and self._HARD_STOP_PATTERN.match(marker):
                break
            if self._should_skip_line(line, marker, is_liepin=is_liepin):
                continue
            if not line:
                if kept_lines and kept_lines[-1]:
                    kept_lines.append("")
                continue
            if self._SECTION_HEADING_PATTERN.match(marker):
                if kept_lines and kept_lines[-1]:
                    kept_lines.append("")
            kept_lines.append(line)

        text = "\n".join(kept_lines).strip()
        detail_score = sum(
            bool(pattern.search(text)) for pattern in self._DETAIL_PATTERNS
        )
        explicit_identity = bool(
            self._EXPLICIT_COMPANY.search(text)
            and self._EXPLICIT_POSITION.search(text)
        )
        list_evidence = bool(self._LIST_PAGE_PATTERN.search(normalized))
        list_evidence = list_evidence or original_link_count >= 8
        listing_titles = re.findall(
            r"招聘[\]】]?\s*$",
            normalized,
            re.MULTILINE,
        )
        list_evidence = list_evidence or len(listing_titles) >= 5

        has_explicit_short_jd = (
            explicit_identity and detail_score >= 1 and len(text) >= 40
        )
        has_substantial_jd = (
            (detail_score >= 3 and len(text) >= 50)
            or (detail_score >= 2 and len(text) >= 80)
            or (detail_score >= 1 and len(text) >= 180)
        )
        is_single_job = (
            not (list_evidence and detail_score < 2)
            and (has_explicit_short_jd or has_substantial_jd)
        )
        return JobTextCleanResult(
            text=text,
            is_single_job=is_single_job,
            reason="" if is_single_job else INCOMPLETE_JOB_MESSAGE,
        )

    @staticmethod
    def _normalize(raw_text: str) -> str:
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u200b", "").replace("\ufeff", "")
        return re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE).strip()

    @classmethod
    def _should_skip_line(
        cls,
        line: str,
        marker: str,
        is_liepin: bool = False,
    ) -> bool:
        if not line:
            return False
        if is_liepin and cls._LIEPIN_NOISE_PATTERN.search(marker):
            return True
        if cls._COMMON_NOISE_PATTERN.match(marker):
            return True
        if cls._NAVIGATION_PATTERN.match(marker):
            return True
        if re.fullmatch(r"https?://\S+", line, re.IGNORECASE):
            return True
        if line.startswith("!["):
            return True
        return len(cls._MARKDOWN_LINK.findall(line)) >= 3

    @classmethod
    def _slice_generic_job_content(cls, lines: list[str]) -> list[str]:
        plain_lines = [
            cls._plain_line(cls._clean_markdown_links(line.strip()))
            for line in lines
        ]
        start_index = next(
            (
                index
                for index, line in enumerate(plain_lines)
                if cls._JOB_BODY_START_PATTERN.match(line)
            ),
            None,
        )
        if start_index is None:
            return lines

        metadata_indexes = {
            index
            for index in range(start_index)
            if cls._GENERIC_METADATA_PATTERN.search(plain_lines[index])
        }
        title_index = next(
            (
                index
                for index in range(start_index)
                if cls._JOB_TITLE_HINT_PATTERN.search(plain_lines[index])
            ),
            None,
        )
        if title_index is not None:
            metadata_indexes.add(title_index)
        metadata = [lines[index] for index in sorted(metadata_indexes)]
        company_section = cls._company_section_before(
            lines,
            plain_lines,
            start_index,
        )
        body = []
        for index in range(start_index, len(lines)):
            marker = plain_lines[index]
            if marker and cls._HARD_STOP_PATTERN.match(marker):
                break
            body.append(lines[index])

        selected = metadata + body
        if company_section:
            selected.extend(("", *company_section))
        return selected

    @classmethod
    def _company_section_before(
        cls,
        lines: list[str],
        plain_lines: list[str],
        body_start: int,
    ) -> list[str]:
        company_start = next(
            (
                index
                for index in range(body_start)
                if cls._COMPANY_SECTION_PATTERN.match(plain_lines[index])
            ),
            None,
        )
        if company_start is None:
            return []

        company_lines = []
        for index in range(company_start, body_start):
            marker = plain_lines[index]
            if (
                index > company_start
                and cls._SECTION_HEADING_PATTERN.match(marker)
            ):
                break
            company_lines.append(lines[index])
        return company_lines

    @classmethod
    def _slice_liepin_content(cls, lines: list[str]) -> list[str]:
        for index, raw_line in enumerate(lines):
            line = cls._clean_markdown_links(raw_line.strip())
            marker = cls._plain_line(line)
            if not cls._LIEPIN_START_PATTERN.match(marker):
                continue
            metadata = []
            for candidate in lines[:index]:
                cleaned = cls._clean_markdown_links(candidate.strip())
                plain = cls._plain_line(cleaned)
                if (
                    plain
                    and cls._LIEPIN_METADATA_PATTERN.search(plain)
                    and not cls._LIEPIN_NOISE_PATTERN.search(plain)
                ):
                    metadata.append(cleaned)
            return metadata + lines[index:]
        return lines

    @classmethod
    def _clean_markdown_links(cls, line: str) -> str:
        if cls._MARKDOWN_LINK.fullmatch(line):
            return ""

        def replace_link(match: re.Match[str]) -> str:
            target = match.group("target").strip().lower()
            if target.startswith("javascript:") or target.startswith(
                "javascript;"
            ):
                return ""
            return match.group("label").strip()

        return cls._MARKDOWN_LINK.sub(replace_link, line).strip()

    @classmethod
    def _extract_visible_html(cls, raw_text: str) -> str:
        if not cls._HTML_PATTERN.search(raw_text):
            return raw_text
        parser = _VisibleHTMLTextParser()
        parser.feed(raw_text)
        parser.close()
        return parser.text()

    @staticmethod
    def _plain_line(line: str) -> str:
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^[*+\-]>?\s*", "", line)
        return line.strip()
