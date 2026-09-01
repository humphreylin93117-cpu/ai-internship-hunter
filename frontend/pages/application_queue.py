from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError
from frontend.application_workbench import (
    NEXT_STATUS_OPTIONS,
    PENDING_STATUSES,
    STATUS_LABELS,
    STATUS_OPTIONS,
    split_queue_items,
)


def job_label(job: dict[str, Any]) -> str:
    return (
        f"{job['company']} · {job['position']} · "
        f"{job['match_score']} 分"
    )


def readiness_label(value: bool) -> str:
    return "已生成" if value else "未生成"


def open_job_page(job_id: int, target: str) -> None:
    st.session_state[f"workbench_{target}_job_id"] = job_id
    page = (
        "pages/resume_optimization.py"
        if target == "resume"
        else "pages/interview_preparation.py"
    )
    st.switch_page(page)


def show_readiness_actions(item: dict[str, Any]) -> None:
    resume_column, interview_column = st.columns(2)
    with resume_column:
        resume_ready = item["has_resume_optimization"]
        if st.button(
            (
                "查看简历优化（已生成）"
                if resume_ready
                else "生成简历优化（未生成）"
            ),
            key=f"resume_queue_{item['job_id']}",
            use_container_width=True,
        ):
            open_job_page(item["job_id"], "resume")
    with interview_column:
        interview_ready = item["has_interview_preparation"]
        if st.button(
            (
                "查看面试准备（已生成）"
                if interview_ready
                else "生成面试准备（未生成）"
            ),
            key=f"interview_queue_{item['job_id']}",
            use_container_width=True,
        ):
            open_job_page(item["job_id"], "interview")


def remove_from_queue(client: BackendClient, job_id: int) -> None:
    try:
        client.remove_from_application_queue(job_id)
    except BackendClientError as exc:
        st.error(f"移出队列失败：{exc}")
    else:
        st.success("岗位已移出投递工作台。")
        st.rerun()


st.title("投递工作台")
st.caption("集中准备待投递岗位，并在投递后持续跟进笔试、面试和结果。")

client = BackendClient()

with st.container(border=True):
    status_column, company_column, score_column, sort_column = st.columns(4)
    with status_column:
        selected_status = st.selectbox(
            "状态",
            options=["全部", *STATUS_OPTIONS],
            format_func=lambda value: (
                value if value == "全部" else STATUS_LABELS[value]
            ),
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
    with sort_column:
        sort_label = st.selectbox(
            "匹配分排序",
            options=["从高到低", "从低到高"],
        )

status_filter = None if selected_status == "全部" else selected_status
minimum_score_filter = int(minimum_score) if minimum_score else None
sort_order = "desc" if sort_label == "从高到低" else "asc"

try:
    queue = client.list_application_queue(
        status=status_filter,
        company=company_filter,
        min_match_score=minimum_score_filter,
        sort_order=sort_order,
    )
    jobs = client.list_jobs(
        status=status_filter,
        company=company_filter,
        min_match_score=minimum_score_filter,
    )
except BackendClientError as exc:
    st.error(str(exc))
    st.info("请确认 FastAPI 后端正在 http://127.0.0.1:8000 运行。")
    st.stop()

pending_queue, follow_up_queue = split_queue_items(queue)
queued_job_ids = {item["job_id"] for item in queue}
available_jobs = [
    job
    for job in jobs
    if job["status"] in PENDING_STATUSES and job["id"] not in queued_job_ids
]
available_jobs.sort(
    key=lambda job: job["match_score"],
    reverse=sort_order == "desc",
)

st.subheader("加入投递工作台")
if not available_jobs:
    st.info("当前筛选条件下没有可加入的未投递岗位。")
else:
    jobs_by_id = {job["id"]: job for job in available_jobs}
    selection_column, action_column = st.columns([4, 1])
    with selection_column:
        selected_job_id = st.selectbox(
            "选择已保存岗位",
            options=list(jobs_by_id),
            format_func=lambda job_id: job_label(jobs_by_id[job_id]),
            label_visibility="collapsed",
        )
    with action_column:
        add_clicked = st.button(
            "加入队列",
            type="primary",
            use_container_width=True,
        )
    if add_clicked:
        try:
            client.add_to_application_queue(selected_job_id)
        except BackendClientError as exc:
            st.error(f"加入队列失败：{exc}")
        else:
            st.success("岗位已加入待投递区。")
            st.rerun()

st.divider()
st.subheader(f"待投递（{len(pending_queue)}）")
st.caption("这里只显示已保存或计划投递的岗位；标记已投递后会自动移至跟进区。")
if not pending_queue:
    st.info("当前筛选条件下没有待投递岗位。")

for item in pending_queue:
    with st.container(border=True):
        info_column, status_column = st.columns([4, 1])
        with info_column:
            st.markdown(f"**{item['company']} · {item['position']}**")
            st.caption(
                f"匹配分：{item['match_score']}　|　"
                f"简历优化：{readiness_label(item['has_resume_optimization'])}　|　"
                f"面试准备：{readiness_label(item['has_interview_preparation'])}"
            )
            if item.get("job_url"):
                st.link_button("打开岗位链接", item["job_url"])
        with status_column:
            st.metric("当前状态", STATUS_LABELS[item["status"]])

        show_readiness_actions(item)
        apply_column, remove_column = st.columns(2)
        with apply_column:
            apply_clicked = st.button(
                "标记已投递",
                key=f"apply_queue_{item['job_id']}",
                type="primary",
                use_container_width=True,
            )
        with remove_column:
            remove_clicked = st.button(
                "移出队列",
                key=f"remove_pending_{item['job_id']}",
                use_container_width=True,
            )

        if apply_clicked:
            try:
                client.mark_application_applied(item["job_id"])
            except BackendClientError as exc:
                st.error(f"状态更新失败：{exc}")
            else:
                st.success("已标记为已投递，岗位已移至跟进区。")
                st.rerun()
        if remove_clicked:
            remove_from_queue(client, item["job_id"])

st.divider()
st.subheader(f"已投递 / 跟进（{len(follow_up_queue)}）")
st.caption("跟进已投递岗位，并快速更新笔试、面试和最终结果。")
if not follow_up_queue:
    st.info("当前筛选条件下没有需要跟进的岗位。")

for item in follow_up_queue:
    with st.container(border=True):
        info_column, status_column = st.columns([4, 1])
        with info_column:
            st.markdown(f"**{item['company']} · {item['position']}**")
            st.caption(
                f"匹配分：{item['match_score']}　|　"
                f"简历优化：{readiness_label(item['has_resume_optimization'])}　|　"
                f"面试准备：{readiness_label(item['has_interview_preparation'])}"
            )
            if item.get("job_url"):
                st.link_button("打开岗位链接", item["job_url"])
        with status_column:
            st.metric("当前状态", STATUS_LABELS[item["status"]])

        show_readiness_actions(item)
        next_statuses = NEXT_STATUS_OPTIONS[item["status"]]
        transition_column, update_column, remove_column = st.columns([3, 1, 1])
        with transition_column:
            if next_statuses:
                next_status = st.selectbox(
                    "下一阶段",
                    options=next_statuses,
                    format_func=lambda value: STATUS_LABELS[value],
                    key=f"next_status_{item['job_id']}_{item['status']}",
                )
            else:
                next_status = None
                st.caption("该岗位已处于终态，无可用的下一阶段。")
        with update_column:
            st.write("")
            update_clicked = st.button(
                "更新状态",
                key=f"update_followup_{item['job_id']}",
                type="primary",
                disabled=next_status is None,
                use_container_width=True,
            )
        with remove_column:
            st.write("")
            remove_clicked = st.button(
                "移出队列",
                key=f"remove_followup_{item['job_id']}",
                use_container_width=True,
            )

        if update_clicked and next_status is not None:
            try:
                client.update_job_status(item["job_id"], next_status)
            except BackendClientError as exc:
                st.error(f"状态更新失败：{exc}")
            else:
                st.success(f"状态已更新为：{STATUS_LABELS[next_status]}。")
                st.rerun()
        if remove_clicked:
            remove_from_queue(client, item["job_id"])
