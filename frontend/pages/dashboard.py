from datetime import datetime

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError
from frontend.application_workbench import STATUS_LABELS


def format_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value or "-"


def open_application_workbench() -> None:
    st.switch_page("pages/application_queue.py")


st.title("Dashboard")
st.caption("岗位投递进度、准备状态和近期重点一览")

client = BackendClient()

try:
    summary = client.get_dashboard_summary()
except BackendClientError as exc:
    st.error(str(exc))
    st.info("请先启动 FastAPI 后端，然后刷新本页面。")
    st.stop()

metric_columns = st.columns(6)
metric_columns[0].metric(
    "已保存 / 计划投递",
    summary["saved_planned_count"],
)
metric_columns[1].metric(
    "待投递队列",
    summary["pending_queue_count"],
)
metric_columns[2].metric("已投递", summary["applied_count"])
metric_columns[3].metric(
    "笔试 / 面试中",
    summary["assessment_interview_count"],
)
metric_columns[4].metric("Offer", summary["offer_count"])
metric_columns[5].metric(
    "平均匹配分",
    f"{summary['average_match_score']:.1f}",
)

st.divider()
st.subheader("投递漏斗 / 阶段汇总")
stages = summary["stages"]
stage_items = [
    ("已保存 / 计划投递", stages["saved_planned"]),
    ("已投递", stages["applied"]),
    ("笔试 / 面试", stages["assessment_interview"]),
    ("Offer", stages["offer"]),
]
stage_maximum = max((count for _, count in stage_items), default=0) or 1
stage_columns = st.columns(4)
for column, (label, count) in zip(stage_columns, stage_items):
    with column:
        st.metric(label, count)
        st.progress(count / stage_maximum)

outcome_columns = st.columns(2)
outcome_columns[0].metric("未通过", stages["rejected"])
outcome_columns[1].metric("已放弃", stages["abandoned"])

st.divider()
priority_title, priority_action = st.columns([4, 1])
with priority_title:
    st.subheader("近期重点岗位")
    st.caption("尚未投递的 saved / planned 岗位，按匹配分从高到低。")
with priority_action:
    if st.button("去投递工作台", use_container_width=True):
        open_application_workbench()

priority_jobs = summary["priority_jobs"]
if not priority_jobs:
    st.info("当前没有尚未投递的重点岗位。")
else:
    priority_rows = [
        {
            "公司": job["company"],
            "岗位": job["position"],
            "匹配分": job["match_score"],
            "当前状态": STATUS_LABELS.get(job["status"], job["status"]),
        }
        for job in priority_jobs
    ]
    st.dataframe(
        priority_rows,
        use_container_width=True,
        hide_index=True,
    )

st.divider()
todo_title, todo_action = st.columns([4, 1])
with todo_title:
    st.subheader("待办事项")
with todo_action:
    if st.button(
        "查看工作台",
        key="dashboard_open_workbench_todos",
        use_container_width=True,
    ):
        open_application_workbench()

active_todos = [item for item in summary["todos"] if item["count"] > 0]
if not active_todos:
    st.success("当前没有待处理事项。")
else:
    todo_columns = st.columns(2)
    for index, item in enumerate(active_todos):
        with todo_columns[index % 2]:
            with st.container(border=True):
                st.metric(item["label"], item["count"])

st.divider()
st.subheader("最近岗位 / 最近变化")
recent_jobs = summary["recent_jobs"]
if not recent_jobs:
    st.info("还没有保存岗位，可以先前往“岗位导入”或“JD 分析”页面。")
else:
    recent_rows = [
        {
            "公司": job["company"],
            "岗位": job["position"],
            "匹配分": job["match_score"],
            "状态": STATUS_LABELS.get(job["status"], job["status"]),
            "最近变化": format_datetime(job["updated_at"]),
        }
        for job in recent_jobs
    ]
    st.dataframe(
        recent_rows,
        use_container_width=True,
        hide_index=True,
    )
