import re

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


DEFAULT_CITIES = ["广州", "深圳"]
SUGGESTED_KEYWORDS = ["数据分析", "AI Agent", "Python", "算法应用"]


def parse_custom_terms(value: str) -> list[str]:
    return [
        term.strip()
        for term in re.split(r"[,，;；\n]+", value)
        if term.strip()
    ]


def unique_terms(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


INCOMPLETE_JOB_MESSAGE = (
    "未获取到完整岗位详情，请打开原网页后复制完整 JD 手动导入"
)


def build_import_prefill(job: dict, extracted_content: str) -> str:
    return "\n\n".join(
        part
        for part in (
            str(job.get("title") or "").strip(),
            extracted_content.strip(),
        )
        if part
    )


def send_to_job_import(job: dict, content: str, notice: str) -> None:
    st.session_state["job_import_mode"] = "粘贴 JD 自动解析"
    st.session_state["import_prefill_text"] = content
    st.session_state["import_prefill_url"] = job["url"]
    st.session_state["import_notice"] = notice
    st.session_state["import_ready"] = False
    for key in (
        "import_analysis",
        "import_analyzed_form",
        "import_duplicates",
        "import_saved_job_id",
        "import_existing_job",
    ):
        st.session_state.pop(key, None)
    st.switch_page("pages/job_import.py")


st.title("岗位发现")
st.caption("通过 Tavily 搜索公开招聘页面；搜索不会调用 DeepSeek。")

client = BackendClient()

left, right = st.columns(2)
with left:
    selected_cities = st.multiselect(
        "目标城市",
        options=["广州", "深圳", "北京", "上海", "杭州", "成都"],
        default=DEFAULT_CITIES,
    )
    custom_cities = st.text_input(
        "其他城市（可选）",
        placeholder="多个城市用逗号分隔",
    )
with right:
    selected_keywords = st.multiselect(
        "岗位关键词",
        options=SUGGESTED_KEYWORDS,
        default=["数据分析", "Python"],
    )
    custom_keywords = st.text_input(
        "自定义关键词（可选）",
        placeholder="例如：后端开发、机器学习；可用逗号分隔",
    )

max_results = st.slider(
    "最多显示结果",
    min_value=1,
    max_value=20,
    value=10,
)

if st.button("搜索岗位", type="primary", use_container_width=True):
    cities = unique_terms(
        selected_cities + parse_custom_terms(custom_cities)
    )
    keywords = unique_terms(
        selected_keywords + parse_custom_terms(custom_keywords)
    )
    if not cities or not keywords:
        st.warning("请至少选择或填写一个城市和一个岗位关键词。")
    else:
        try:
            with st.spinner("正在搜索公开招聘岗位……"):
                response = client.discover_jobs(
                    keywords=keywords,
                    cities=cities,
                    max_results=max_results,
                )
        except BackendClientError as exc:
            st.error(f"岗位搜索失败：{exc}")
        else:
            st.session_state["discovery_response"] = response

response = st.session_state.get("discovery_response")
if response:
    results = response.get("results", [])
    st.divider()
    st.subheader(f"候选岗位（{len(results)}）")
    if not results:
        st.info("没有发现符合当前条件的招聘页面，请调整搜索条件。")

    for index, job in enumerate(results):
        with st.container(border=True):
            st.markdown(f"### {job['title'] or '未命名岗位页面'}")
            st.caption(
                f"来源：{job['source_domain'] or '未知域名'} · "
                f"Provider：{job['provider']}"
            )
            st.write(job["snippet"] or "暂无摘要")
            link_column, import_column = st.columns([1, 1])
            with link_column:
                st.link_button(
                    "打开原网页",
                    job["url"],
                    use_container_width=True,
                )
            with import_column:
                if st.button(
                    "导入岗位",
                    key=f"import_discovered_job_{index}",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("正在获取该岗位网页正文……"):
                            extracted = client.extract_job_content(job["url"])
                    except BackendClientError:
                        send_to_job_import(
                            job,
                            "",
                            INCOMPLETE_JOB_MESSAGE,
                        )
                    else:
                        if not extracted.get("is_complete", True):
                            send_to_job_import(
                                job,
                                "",
                                extracted.get("warning")
                                or INCOMPLETE_JOB_MESSAGE,
                            )
                        else:
                            send_to_job_import(
                                job,
                                build_import_prefill(
                                    job,
                                    extracted["content"],
                                ),
                                "已获取完整岗位正文。请点击“解析岗位”，并人工核对信息。",
                            )
