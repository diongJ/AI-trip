from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import require_project_environment

require_project_environment(st)

from app.components.ui import (
    TYPE_LABELS,
    configure_page,
    load_runtime_or_stop,
    render_outcome,
    render_sidebar,
)
from app.runtime import (
    EXPLANATION_STYLES,
    build_explanation_prompt,
    explanation_markdown,
    safe_download_name,
)


configure_page("AI 深度讲解", "🎧")
runtime = load_runtime_or_stop()
render_sidebar(runtime)

st.title("🎧 AI 深度讲解")
st.caption("从知识图谱选定对象，以 Hybrid 检索生成带来源的个性化讲解。")

st.markdown('<p class="section-eyebrow">讲解控制面板</p>', unsafe_allow_html=True)
with st.container(border=True):
    control_cols = st.columns([1, 2, 1])
    entity_type = control_cols[0].selectbox(
        "讲解对象类型",
        options=["Person", "Tomb", "Relic"],
        format_func=lambda value: TYPE_LABELS[value],
    )
    entities = runtime.list_entities(entity_type=entity_type, limit=100)
    entity = control_cols[1].selectbox(
        "选择人物、墓葬或代表文物",
        options=entities,
        format_func=lambda item: item.name,
    )
    style = control_cols[2].selectbox("讲解风格", options=list(EXPLANATION_STYLES))

if entity and entity.aliases:
    st.caption(f"别名：{'、'.join(entity.aliases)}")

if st.button("生成有据讲解", type="primary", width="stretch", disabled=entity is None):
    prompt = build_explanation_prompt(entity.name, style)
    with st.spinner("正在结合图谱关系与原文证据生成讲解……"):
        outcome = runtime.ask(prompt)
    st.session_state.explanation_result = {
        "entity_name": entity.name,
        "style": style,
        "outcome": outcome,
    }

result = st.session_state.get("explanation_result")
if result:
    st.markdown('<p class="section-eyebrow">导览稿 · 可复制下载</p>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader(f"{result['entity_name']}｜{result['style']}")
        render_outcome(result["outcome"])
    markdown = explanation_markdown(
        result["entity_name"],
        result["style"],
        result["outcome"],
    )
    st.download_button(
        "下载 Markdown 讲解稿",
        data=markdown.encode("utf-8"),
        file_name=safe_download_name(result["entity_name"], result["style"]),
        mime="text/markdown",
        width="stretch",
    )
else:
    st.info("选择对象和讲解风格后生成讲解；证据不足时系统不会编造内容。")
