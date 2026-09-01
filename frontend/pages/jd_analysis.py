from typing import Any

import streamlit as st

from frontend.api.backend_client import BackendClient, BackendClientError


def show_items(title: str, items: list[str]) -> None:
    st.subheader(title)
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.caption("暂无内容")


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


st.title("JD 分析")
st.caption("结合候选人资料评估岗位匹配度，确认后再保存岗位。")

client = BackendClient()

with st.form("job_analysis_form"):
    left, right = st.columns(2)
    with left:
        company = st.text_input("公司名称", placeholder="例如：示例科技")
        source = st.selectbox(
            "岗位来源",
            options=["BOSS", "官网", "LinkedIn", "其他"],
        )
    with right:
        position = st.text_input("岗位名称", placeholder="例如：Python 实习生")
        job_url = st.text_input("岗位链接（可为空）")

    job_description = st.text_area(
        "完整 JD",
        height=320,
        placeholder="粘贴完整岗位描述……",
    )
    analyze_submitted = st.form_submit_button(
        "开始分析",
        type="primary",
        use_container_width=True,
    )

if analyze_submitted:
    missing_fields = []
    if not company.strip():
        missing_fields.append("公司名称")
    if not position.strip():
        missing_fields.append("岗位名称")
    if not job_description.strip():
        missing_fields.append("完整 JD")

    if missing_fields:
        st.warning("请填写：" + "、".join(missing_fields))
    else:
        form_data: dict[str, Any] = {
            "company": company.strip(),
            "position": position.strip(),
            "source": source,
            "job_url": job_url.strip() or None,
            "job_description": job_description.strip(),
        }
        try:
            with st.spinner("正在分析岗位匹配度……"):
                analysis = client.analyze_job(form_data["job_description"])
        except BackendClientError as exc:
            st.session_state.pop("job_analysis_result", None)
            st.session_state.pop("job_analysis_form_data", None)
            st.error(f"分析失败：{exc}")
        else:
            st.session_state["job_analysis_result"] = analysis
            st.session_state["job_analysis_form_data"] = form_data
            st.session_state.pop("saved_job_id", None)

analysis = st.session_state.get("job_analysis_result")
form_data = st.session_state.get("job_analysis_form_data")

if analysis and form_data:
    st.divider()
    st.metric("综合匹配分", f"{analysis['match_score']} / 100")

    strengths_column, weaknesses_column = st.columns(2)
    with strengths_column:
        show_items("优势", analysis["strengths"])
    with weaknesses_column:
        show_items("待补足", analysis["weaknesses"])
    show_items("申请准备建议", analysis["suggestions"])

    saved_job_id = st.session_state.get("saved_job_id")
    if saved_job_id:
        st.success(f"岗位已保存，ID：{saved_job_id}")
    elif st.button("保存岗位", type="primary"):
        try:
            saved_job = client.create_job(
                build_job_payload(form_data, analysis)
            )
        except BackendClientError as exc:
            st.error(f"保存失败：{exc}")
        else:
            st.session_state["saved_job_id"] = saved_job["id"]
            st.success(f"岗位已保存，ID：{saved_job['id']}")
