import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st


st.set_page_config(
    page_title="AI Internship Hunter",
    page_icon="🎯",
    layout="wide",
)

navigation = st.navigation(
    [
        st.Page(
            "pages/dashboard.py",
            title="Dashboard",
            icon="📊",
            default=True,
        ),
        st.Page(
            "pages/jd_analysis.py",
            title="JD 分析",
            icon="🔍",
        ),
        st.Page(
            "pages/job_import.py",
            title="岗位导入",
            icon="📥",
        ),
        st.Page(
            "pages/job_discovery.py",
            title="岗位发现",
            icon="🔎",
        ),
        st.Page(
            "pages/applications.py",
            title="岗位管理",
            icon="📋",
        ),
        st.Page(
            "pages/application_queue.py",
            title="投递工作台",
            icon="✅",
        ),
        st.Page(
            "pages/resume_optimization.py",
            title="简历优化",
            icon="📝",
        ),
        st.Page(
            "pages/interview_preparation.py",
            title="面试准备",
            icon="🎯",
        ),
    ]
)
navigation.run()
