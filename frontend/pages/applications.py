from datetime import datetime
from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


STATUS_OPTIONS = [
    "saved",
    "planned",
    "applied",
    "written_test",
    "interview_1",
    "interview_2",
    "offer",
    "rejected",
    "abandoned",
]


def format_created_at(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value


def show_items(title: str, items: list[str]) -> None:
    st.subheader(title)
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.caption("暂无内容")


def job_label(job: dict[str, Any]) -> str:
    return f"{job['company']} · {job['position']} · {job['match_score']} 分"


st.title("岗位管理")
st.caption("筛选、查看岗位，并维护当前投递状态。")

client = BackendClient()

with st.container(border=True):
    status_column, company_column, score_column = st.columns(3)
    with status_column:
        selected_status = st.selectbox(
            "状态",
            options=["全部", *STATUS_OPTIONS],
        )
    with company_column:
        company_filter = st.text_input("公司", placeholder="输入公司名称")
    with score_column:
        minimum_score = st.number_input(
            "最低匹配分",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )

try:
    jobs = client.list_jobs(
        status=None if selected_status == "全部" else selected_status,
        company=company_filter,
        min_match_score=int(minimum_score) if minimum_score else None,
    )
except BackendClientError as exc:
    st.error(str(exc))
    st.info("请确认 FastAPI 后端正在 http://127.0.0.1:8000 运行。")
    st.stop()

st.subheader(f"岗位列表（{len(jobs)}）")
if not jobs:
    st.info("没有找到符合当前筛选条件的岗位。")
    st.stop()

table_rows = [
    {
        "公司": job["company"],
        "岗位": job["position"],
        "匹配分": job["match_score"],
        "当前状态": job["status"],
        "创建时间": format_created_at(job["created_at"]),
    }
    for job in jobs
]
st.dataframe(table_rows, use_container_width=True, hide_index=True)

jobs_by_id = {job["id"]: job for job in jobs}
selected_job_id = st.selectbox(
    "选择岗位查看详情",
    options=list(jobs_by_id),
    format_func=lambda job_id: job_label(jobs_by_id[job_id]),
)

try:
    selected_job = client.get_job(selected_job_id)
except BackendClientError as exc:
    st.error(f"岗位详情加载失败：{exc}")
    st.stop()

st.divider()
st.header(f"{selected_job['company']} · {selected_job['position']}")
st.caption(
    f"来源：{selected_job['source']}　|　"
    f"匹配分：{selected_job['match_score']}　|　"
    f"创建时间：{format_created_at(selected_job['created_at'])}"
)
if selected_job.get("job_url"):
    st.link_button("打开岗位链接", selected_job["job_url"])

status_column, action_column = st.columns([3, 1])
with status_column:
    new_status = st.selectbox(
        "投递状态",
        options=STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(selected_job["status"]),
        key=f"job_status_{selected_job_id}",
    )
with action_column:
    st.write("")
    st.write("")
    update_clicked = st.button(
        "更新状态",
        type="primary",
        use_container_width=True,
        disabled=new_status == selected_job["status"],
    )

if update_clicked:
    try:
        client.update_job_status(selected_job_id, new_status)
    except BackendClientError as exc:
        st.error(f"状态更新失败：{exc}")
    else:
        st.success("岗位状态已更新。")
        st.rerun()

st.subheader("完整 JD")
st.text_area(
    "岗位描述",
    value=selected_job["job_description"],
    height=260,
    disabled=True,
    label_visibility="collapsed",
)

strengths_column, weaknesses_column = st.columns(2)
with strengths_column:
    show_items("优势", selected_job["strengths"])
with weaknesses_column:
    show_items("待补足", selected_job["weaknesses"])
show_items("申请准备建议", selected_job["suggestions"])
