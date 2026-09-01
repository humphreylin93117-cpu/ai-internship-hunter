from datetime import datetime
from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


SOURCE_OPTIONS = [
    "",
    "BOSS",
    "猎聘",
    "实习僧",
    "智联招聘",
    "前程无忧",
    "拉勾",
    "官网",
    "LinkedIn",
    "其他",
]


def show_items(title: str, items: list[str]) -> None:
    st.subheader(title)
    if not items:
        st.caption("暂无内容")
        return
    for item in items:
        st.markdown(f"- {item}")


def current_form_data() -> dict[str, Any]:
    return {
        "company": st.session_state.get("import_company", "").strip(),
        "position": st.session_state.get("import_position", "").strip(),
        "source": st.session_state.get("import_source", "").strip(),
        "job_url": st.session_state.get("import_job_url", "").strip()
        or None,
        "job_description": st.session_state.get(
            "import_job_description", ""
        ).strip(),
    }


def build_job_payload(
    form_data: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    return {
        **form_data,
        "match_score": analysis["match_score"],
        "strengths": analysis["strengths"],
        "weaknesses": analysis["weaknesses"],
        "suggestions": analysis["suggestions"],
        "status": "saved",
    }


def save_job(
    client: BackendClient,
    form_data: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    try:
        saved = client.create_job(build_job_payload(form_data, analysis))
    except BackendClientError as exc:
        st.error(f"保存失败：{exc}")
        return
    st.session_state["import_saved_job_id"] = saved["id"]
    st.session_state.pop("import_duplicates", None)
    st.success(f"岗位已保存，ID：{saved['id']}")


st.title("岗位导入")
st.caption("粘贴真实岗位信息，确认后完成匹配分析与保存。")

if "import_prefill_text" in st.session_state:
    st.session_state["import_raw_text"] = st.session_state.pop(
        "import_prefill_text"
    )
if "import_prefill_url" in st.session_state:
    st.session_state["import_raw_url"] = st.session_state.pop(
        "import_prefill_url"
    )

import_notice = st.session_state.pop("import_notice", None)
if import_notice:
    st.info(import_notice)

client = BackendClient()
mode = st.radio(
    "录入方式",
    options=["粘贴 JD 自动解析", "结构化快速录入"],
    horizontal=True,
    key="job_import_mode",
)

if mode == "粘贴 JD 自动解析":
    raw_text = st.text_area(
        "岗位原始文本",
        height=260,
        placeholder="粘贴招聘页面中的完整岗位文本……",
        key="import_raw_text",
    )
    raw_url = st.text_input("岗位 URL（可选）", key="import_raw_url")
    if st.button("解析岗位", type="primary"):
        if not raw_text.strip():
            st.warning("请先粘贴岗位原始文本。")
        else:
            try:
                parsed = client.parse_job(raw_text, raw_url)
            except BackendClientError as exc:
                st.error(f"解析失败：{exc}。你仍可使用结构化快速录入。")
            else:
                if parsed.get("parse_status", "success") != "success":
                    st.error(
                        parsed.get("parse_message")
                        or "未检测到有效招聘 JD，请手动补充。"
                    )
                    st.session_state["import_ready"] = False
                    st.stop()
                st.session_state["import_company"] = parsed["company"]
                st.session_state["import_position"] = parsed["position"]
                parsed_source = parsed["source"]
                st.session_state["import_source"] = (
                    parsed_source
                    if parsed_source in SOURCE_OPTIONS
                    else "其他"
                )
                st.session_state["import_job_url"] = (
                    parsed.get("job_url") or ""
                )
                st.session_state["import_job_description"] = parsed[
                    "job_description"
                ]
                st.session_state["import_ready"] = True
                st.session_state.pop("import_analysis", None)
                st.session_state.pop("import_analyzed_form", None)
                st.session_state.pop("import_duplicates", None)
                st.session_state.pop("import_saved_job_id", None)
                st.rerun()
else:
    st.session_state["import_ready"] = True

if st.session_state.get("import_ready"):
    st.divider()
    st.subheader("确认岗位信息")
    left, right = st.columns(2)
    with left:
        st.text_input("公司名称", key="import_company")
        st.selectbox(
            "岗位来源",
            options=SOURCE_OPTIONS,
            key="import_source",
            format_func=lambda value: value or "请选择",
        )
    with right:
        st.text_input("岗位名称", key="import_position")
        st.text_input("岗位链接（可为空）", key="import_job_url")
    st.text_area(
        "完整 JD",
        height=320,
        key="import_job_description",
    )

    if st.button("分析匹配度", type="primary"):
        form_data = current_form_data()
        missing = [
            label
            for label, key in (
                ("公司名称", "company"),
                ("岗位名称", "position"),
                ("岗位来源", "source"),
                ("完整 JD", "job_description"),
            )
            if not form_data[key]
        ]
        if missing:
            st.warning("请补充：" + "、".join(missing))
        else:
            try:
                with st.spinner("正在分析岗位匹配度……"):
                    result = client.analyze_job(
                        form_data["job_description"]
                    )
            except BackendClientError as exc:
                st.error(f"分析失败：{exc}")
            else:
                st.session_state["import_analysis"] = result
                st.session_state["import_analyzed_form"] = form_data
                st.session_state.pop("import_duplicates", None)
                st.session_state.pop("import_saved_job_id", None)

analysis = st.session_state.get("import_analysis")
analyzed_form = st.session_state.get("import_analyzed_form")

if analysis and analyzed_form:
    st.divider()
    st.metric("综合匹配分", f"{analysis['match_score']} / 100")
    strengths_column, weaknesses_column = st.columns(2)
    with strengths_column:
        show_items("优势", analysis["strengths"])
    with weaknesses_column:
        show_items("待补足", analysis["weaknesses"])
    show_items("申请准备建议", analysis["suggestions"])

    if current_form_data() != analyzed_form:
        st.warning("岗位信息已修改，请重新分析后再保存。")
    elif st.session_state.get("import_saved_job_id"):
        st.success(
            f"岗位已保存，ID：{st.session_state['import_saved_job_id']}"
        )
    elif st.button("保存岗位", type="primary"):
        try:
            duplicate_result = client.check_job_duplicate(
                analyzed_form["company"],
                analyzed_form["position"],
                analyzed_form["job_description"],
                analyzed_form["job_url"],
            )
        except BackendClientError as exc:
            st.error(f"重复检测失败：{exc}")
        else:
            if duplicate_result["is_duplicate"]:
                st.session_state["import_duplicates"] = duplicate_result[
                    "jobs"
                ]
                st.rerun()
            else:
                save_job(client, analyzed_form, analysis)

duplicates = st.session_state.get("import_duplicates", [])
if duplicates and analysis and analyzed_form:
    st.warning("该岗位可能已经存在")
    table_rows = []
    for job in duplicates:
        created_at = job["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at).strftime(
                "%Y-%m-%d %H:%M"
            )
        except (TypeError, ValueError):
            pass
        table_rows.append(
            {
                "ID": job["id"],
                "公司": job["company"],
                "岗位": job["position"],
                "状态": job["status"],
                "创建时间": created_at,
            }
        )
    st.dataframe(table_rows, use_container_width=True, hide_index=True)
    view_column, save_column = st.columns(2)
    with view_column:
        if st.button("查看已有岗位", use_container_width=True):
            try:
                existing = client.get_job(duplicates[0]["id"])
            except BackendClientError as exc:
                st.error(f"读取已有岗位失败：{exc}")
            else:
                st.session_state["import_existing_job"] = existing
    with save_column:
        if st.button(
            "仍然保存",
            type="primary",
            use_container_width=True,
        ):
            save_job(client, analyzed_form, analysis)

existing_job = st.session_state.get("import_existing_job")
if existing_job:
    with st.expander("已有岗位详情", expanded=True):
        st.markdown(
            f"**{existing_job['company']} · {existing_job['position']}**"
        )
        st.caption(
            f"状态：{existing_job['status']} · "
            f"匹配分：{existing_job['match_score']}"
        )
        st.text(existing_job["job_description"])
