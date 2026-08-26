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
cta_cols = st.columns([2, 1, 2])
with cta_cols[1]:
    st.page_link(
        "pages/1_智能问答.py",
        label="👉 直接向导览助手提问",
        icon=None,
        width="stretch",
    )
st.markdown('<p class="section-eyebrow">可信数据规模 · 实时读取自本地知识库</p>', unsafe_allow_html=True)
metric_cols = st.columns(4)
metric_cols[0].metric("分层可信资料", f"{status.document_count} 份", "核心馆方 + 扩展可信 + 参观攻略")
metric_cols[1].metric("知识实体", f"{status.entity_count} 个", "名称与别名统一")
metric_cols[2].metric("可溯源关系", f"{status.relation_count} 条", "保留原文证据")
metric_cols[3].metric(
    "回答生成",
    "智能生成" if status.deepseek_configured else "离线摘录",
    "DeepSeek 可用" if status.deepseek_configured else "自动降级，引用不受影响",
)
st.caption("口径说明：核心图谱证据基线为 78 个实体、87 条关系；RAG 检索语料已扩展为分层可信资料，两者相互印证。")

st.markdown('<p class="section-eyebrow">从哪里开始</p>', unsafe_allow_html=True)
st.markdown("## 三个入口")
entry_cols = st.columns(3)
with entry_cols[0]:
    st.markdown(
        '<div class="entry-panel"><h3>💬 智能问答</h3>'
        "<p>询问人物、墓葬、文物与历史背景，查看工具路由和逐条引用。</p></div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_智能问答.py", label="进入智能问答", icon="💬")
with entry_cols[1]:
    st.markdown(
        '<div class="entry-panel"><h3>🎧 AI 深度讲解</h3>'
        "<p>选择人物、墓葬或代表文物，生成不同受众风格的有据讲解稿。</p></div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_AI深度讲解.py", label="生成深度讲解", icon="🎧")
with entry_cols[2]:
    st.markdown(
        '<div class="entry-panel"><h3>🕸️ 图谱探索</h3>'
        "<p>通过名称、别名和类型定位实体，沿一跳关系继续探索证据。</p></div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_图谱探索.py", label="探索知识图谱", icon="🕸️")

st.markdown('<p class="section-eyebrow">可靠性原则</p>', unsafe_allow_html=True)
st.markdown("## 证据先行，边界明确")
principle_cols = st.columns(3)
principles = [
    ("证据先行", "回答来自 KG 关系或 RAG 原文片段，不依赖模型记忆。"),
    ("来源可查", "每条有效回答均展示文档编号、来源层级和原始链接。"),
    ("边界明确", "证据不足或超出范围时主动拒答；DeepSeek 通用兜底会明确标注。"),
]
for col, (title, desc) in zip(principle_cols, principles):
    col.markdown(
        f'<div class="principle-card"><strong>{title}</strong><br><span>{desc}</span></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="scope-note">
      <strong>资料范围提示</strong><br>
      当前知识库覆盖南越王博物院、南越国历史、考古发现、文物工艺、文化交流与王墓展区参观攻略；不包含实时客流、当天余票、天气、停车空位或路线导航。
    </div>
    """,
    unsafe_allow_html=True,
)
