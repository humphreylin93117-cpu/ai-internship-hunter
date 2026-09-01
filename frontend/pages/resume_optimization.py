from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


def job_label(job: dict[str, Any]) -> str:
    return f"{job['company']} · {job['position']} · {job['match_score']} 分"


def show_items(title: str, items: list[str], empty_text: str = "暂无") -> None:
    st.subheader(title)
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.caption(empty_text)


st.title("简历优化")
st.caption("基于已保存岗位和候选人真实资料生成针对性的简历调整建议。")

client = BackendClient()

try:
    jobs = client.list_jobs()
except BackendClientError as exc:
    st.error(str(exc))
    st.info("请先启动 FastAPI 后端，然后刷新本页面。")
    st.stop()

if not jobs:
    st.info("还没有已保存岗位，请先在“JD 分析”页面分析并保存岗位。")
    st.stop()

jobs_by_id = {job["id"]: job for job in jobs}
preferred_job_id = st.session_state.pop("workbench_resume_job_id", None)
job_ids = list(jobs_by_id)
selected_job_id = st.selectbox(
    "选择目标岗位",
    options=job_ids,
    index=(
        job_ids.index(preferred_job_id)
        if preferred_job_id in jobs_by_id
        else 0
    ),
    format_func=lambda job_id: job_label(jobs_by_id[job_id]),
)
selected_job = jobs_by_id[selected_job_id]

company_column, position_column, score_column, status_column = st.columns(4)
company_column.metric("公司", selected_job["company"])
position_column.metric("岗位", selected_job["position"])
score_column.metric("匹配分", selected_job["match_score"])
status_column.metric("当前状态", selected_job["status"])

try:
    cached = client.get_cached_resume_optimization(selected_job_id)
except BackendClientError as exc:
    st.warning(f"缓存状态读取失败：{exc}")
    cached = None

if cached:
    st.session_state["resume_optimization_result"] = cached["result"]
    st.session_state["resume_optimization_job_id"] = selected_job_id
    st.session_state["resume_optimization_metadata"] = {
        "model": cached["model"],
        "updated_at": cached["updated_at"],
    }
elif st.session_state.get("resume_optimization_job_id") == selected_job_id:
    st.session_state.pop("resume_optimization_result", None)
    st.session_state.pop("resume_optimization_job_id", None)
    st.session_state.pop("resume_optimization_metadata", None)

generate_column, regenerate_column = st.columns(2)
with generate_column:
    generate_clicked = st.button(
        "生成/查看简历优化建议",
        type="primary",
        use_container_width=True,
    )
with regenerate_column:
    regenerate_clicked = st.button(
        "重新生成",
        use_container_width=True,
    )

if generate_clicked or regenerate_clicked:
    try:
        spinner_text = (
            "正在重新生成简历优化建议……"
            if regenerate_clicked
            else "正在获取简历优化建议……"
        )
        with st.spinner(spinner_text):
            result = client.optimize_resume(
                selected_job_id,
                force_regenerate=regenerate_clicked,
            )
    except BackendClientError as exc:
        st.error(f"简历优化失败：{exc}")
    else:
        st.session_state["resume_optimization_result"] = result
        st.session_state["resume_optimization_job_id"] = selected_job_id
        try:
            refreshed_cache = client.get_cached_resume_optimization(
                selected_job_id
            )
        except BackendClientError as exc:
            st.warning(f"生成成功，但缓存信息读取失败：{exc}")
        else:
            if refreshed_cache:
                st.session_state["resume_optimization_metadata"] = {
                    "model": refreshed_cache["model"],
                    "updated_at": refreshed_cache["updated_at"],
                }

result = st.session_state.get("resume_optimization_result")
result_job_id = st.session_state.get("resume_optimization_job_id")
metadata = st.session_state.get("resume_optimization_metadata")

if result and result_job_id == selected_job_id:
    st.divider()
    st.header(f"目标岗位：{result['target_position']}")
    if metadata:
        st.caption(
            f"上次生成时间：{metadata['updated_at']}　|　"
            f"模型：{metadata['model']}"
        )

    priority_column, keyword_column = st.columns(2)
    with priority_column:
        show_items("优先突出经历", result["priority_experiences"])
    with keyword_column:
        show_items("建议强调的关键词", result["keywords_to_emphasize"])

    show_items("建议弱化内容", result["content_to_deemphasize"])

    st.subheader("项目改写建议")
    if not result["project_rewrites"]:
        st.caption("暂无项目改写建议")
    for rewrite in result["project_rewrites"]:
        with st.container(border=True):
            st.markdown(f"**{rewrite['project']}**")
            st.markdown(f"**原始事实/表述：** {rewrite['original']}")
            st.markdown(f"**建议改写：** {rewrite['suggested']}")
            st.caption(f"原因：{rewrite['reason']}")

    skill_column, missing_column = st.columns(2)
    with skill_column:
        show_items("技能栏调整", result["skill_section_suggestions"])
    with missing_column:
        show_items(
            "缺失要求",
            result["missing_requirements"],
            empty_text="未发现需要明确标记的缺失要求",
        )

    with st.container(border=True):
        show_items(
            "风险与真实性提醒",
            result["warnings"],
            empty_text="暂无额外提醒",
        )
