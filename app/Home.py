from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import require_project_environment

require_project_environment(st)

from app.components.ui import configure_page, load_runtime_or_stop, render_sidebar


configure_page("首页", "🏺")
runtime = load_runtime_or_stop()
render_sidebar(runtime)

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">NANYUE KING MUSEUM · GROUNDED AI GUIDE</div>
      <h1>让每一次讲解<br>都有证据可循</h1>
      <p>以南越王博物院、南越国历史、考古与文物专题的可靠资料为基础，连接知识图谱、文档检索与智能体，提供可追溯的问答、讲解和关系探索。</p>
    </section>
    """,
    unsafe_allow_html=True,
)

status = runtime.status
metric_cols = st.columns(3)
metric_cols[0].metric("可靠资料", f"{status.document_count} 份", "官方与博物馆来源")
metric_cols[1].metric("知识实体", f"{status.entity_count} 个", "名称与别名统一")
metric_cols[2].metric("可溯源关系", f"{status.relation_count} 条", "保留原文证据")

st.markdown("## 从哪里开始")
entry_cols = st.columns(3)
with entry_cols[0]:
    st.markdown("### 💬 智能问答")
    st.write("询问人物、墓葬、文物与历史背景，查看工具路由和逐条引用。")
    st.page_link("pages/1_智能问答.py", label="进入智能问答", icon="💬")
with entry_cols[1]:
    st.markdown("### 🎧 AI 深度讲解")
    st.write("选择人物、墓葬或代表文物，生成不同受众风格的有据讲解稿。")
    st.page_link("pages/2_AI深度讲解.py", label="生成深度讲解", icon="🎧")
with entry_cols[2]:
    st.markdown("### 🕸️ 图谱探索")
    st.write("通过名称、别名和类型定位实体，沿一跳关系继续探索证据。")
    st.page_link("pages/3_图谱探索.py", label="探索知识图谱", icon="🕸️")

st.markdown("## 可靠性原则")
principle_cols = st.columns(3)
principle_cols[0].success("**证据先行**\n\n回答来自 KG 关系或 RAG 原文片段。")
principle_cols[1].success("**来源可查**\n\n每条有效回答均展示文档编号和来源链接。")
principle_cols[2].success("**边界明确**\n\n证据不足或超出范围时主动拒答，不补造事实。")

st.markdown(
    """
    <div class="scope-note">
      <strong>资料范围提示</strong><br>
      当前知识库覆盖南越王博物院、南越国历史、考古发现、文物工艺与文化交流；不包含实时客流、天气、餐饮或路线导航。
    </div>
    """,
    unsafe_allow_html=True,
)
