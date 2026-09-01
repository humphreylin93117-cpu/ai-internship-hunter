from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


def job_label(job: dict[str, Any]) -> str:
    return f"{job['company']} · {job['position']} · {job['match_score']} 分"


def show_points(points: list[str]) -> None:
    if not points:
        st.caption("暂无")
    for point in points:
        st.markdown(f"- {point}")


st.title("🎯 面试准备")
st.caption("根据目标岗位、候选人资料和岗位匹配结果生成面试准备材料。")

client = BackendClient()

try:
    jobs = client.list_jobs()
except BackendClientError as exc:
    st.error(str(exc))
    st.info("请先启动 FastAPI 后端，然后刷新本页面。")
    st.stop()

if not jobs:
    st.info("还没有已保存岗位，请先分析并保存岗位。")
    st.stop()

jobs_by_id = {job["id"]: job for job in jobs}
preferred_job_id = st.session_state.pop("workbench_interview_job_id", None)
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

columns = st.columns(4)
columns[0].metric("公司", selected_job["company"])
columns[1].metric("岗位", selected_job["position"])
columns[2].metric("匹配分", selected_job["match_score"])
columns[3].metric("当前状态", selected_job["status"])

try:
    cached = client.get_cached_interview_preparation(selected_job_id)
except BackendClientError as exc:
    st.warning(f"缓存状态读取失败：{exc}")
    cached = None

if cached:
    st.session_state["interview_preparation_result"] = cached["result"]
    st.session_state["interview_preparation_job_id"] = selected_job_id
    st.session_state["interview_preparation_metadata"] = {
        "model": cached["model"],
        "updated_at": cached["updated_at"],
    }
elif st.session_state.get("interview_preparation_job_id") == selected_job_id:
    st.session_state.pop("interview_preparation_result", None)
    st.session_state.pop("interview_preparation_job_id", None)
    st.session_state.pop("interview_preparation_metadata", None)

generate_column, regenerate_column = st.columns(2)
with generate_column:
    generate_clicked = st.button(
        "生成/查看面试准备",
        type="primary",
        use_container_width=True,
    )
with regenerate_column:
    regenerate_clicked = st.button("重新生成", use_container_width=True)

if generate_clicked or regenerate_clicked:
    try:
        with st.spinner("正在生成面试准备材料……"):
            result = client.prepare_interview(
                selected_job_id,
                force_regenerate=regenerate_clicked,
            )
    except BackendClientError as exc:
        st.error(f"面试准备生成失败：{exc}")
    else:
        st.session_state["interview_preparation_result"] = result
        st.session_state["interview_preparation_job_id"] = selected_job_id
        try:
            refreshed = client.get_cached_interview_preparation(
                selected_job_id
            )
        except BackendClientError as exc:
            st.warning(f"生成成功，但缓存信息读取失败：{exc}")
        else:
            if refreshed:
                st.session_state["interview_preparation_metadata"] = {
                    "model": refreshed["model"],
                    "updated_at": refreshed["updated_at"],
                }

result = st.session_state.get("interview_preparation_result")
result_job_id = st.session_state.get("interview_preparation_job_id")
metadata = st.session_state.get("interview_preparation_metadata")

if result and result_job_id == selected_job_id:
    st.divider()
    st.header(f"目标岗位：{result['target_position']}")
    if metadata:
        st.caption(
            f"上次生成时间：{metadata['updated_at']}　|　"
            f"模型：{metadata['model']}"
        )

    st.subheader("核心考察方向")
    for area in result["focus_areas"]:
        with st.container(border=True):
            st.markdown(f"**{area['topic']} · {area['importance']}**")
            st.write(area["reason"])

    st.subheader("高概率问题")
    for item in result["likely_questions"]:
        with st.expander(f"[{item['category']}] {item['question']}"):
            st.caption(f"提问原因：{item['why_asked']}")
            show_points(item["answer_points"])

    st.subheader("项目深挖问题")
    for item in result["project_questions"]:
        with st.expander(f"{item['project']}：{item['question']}"):
            show_points(item["answer_points"])

    st.subheader("风险问题")
    for item in result["risk_questions"]:
        with st.expander(item["question"]):
            show_points(item["answer_strategy"])

    st.subheader("待补知识")
    for gap in result["knowledge_gaps"]:
        with st.container(border=True):
            st.markdown(f"**{gap['topic']} · {gap['priority']}**")
            st.write(gap["preparation"])

    st.subheader("反问面试官")
    show_points(result["questions_for_interviewer"])
