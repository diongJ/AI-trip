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
    RELATION_LABELS,
    TYPE_LABELS,
    configure_page,
    load_runtime_or_stop,
    relation_table_rows,
    render_relation_card,
    render_sidebar,
)


configure_page("图谱探索", "🕸️")
runtime = load_runtime_or_stop()
render_sidebar(runtime)

pending_center = st.session_state.pop("graph_pending_center", None)
if pending_center is not None:
    st.session_state.graph_center_id = pending_center
    st.session_state.graph_type_filter = None

st.title("🕸️ 图谱探索")
st.caption("按名称或别名定位实体，查看一跳关系并沿相邻节点继续探索。")

filter_cols = st.columns([2, 1])
query = filter_cols[0].text_input("搜索实体名称或别名", placeholder="例如：南越文帝、文帝行玺")
type_options = [None, *TYPE_LABELS.keys()]
entity_type = filter_cols[1].selectbox(
    "实体类型",
    options=type_options,
    format_func=lambda value: "全部类型" if value is None else TYPE_LABELS[value],
    key="graph_type_filter",
)
matches = runtime.list_entities(query, entity_type=entity_type, limit=100)

if not matches:
    st.warning("没有找到匹配实体，请尝试缩短关键词或切换类型。")
    st.stop()

match_ids = [entity.id for entity in matches]
current_id = st.session_state.get("graph_center_id", "person:赵眜")
default_index = match_ids.index(current_id) if current_id in match_ids else 0
selected = st.selectbox(
    f"匹配实体（{len(matches)}）",
    options=matches,
    index=default_index,
    format_func=lambda entity: f"{entity.name} · {TYPE_LABELS.get(entity.type, entity.type)}",
)

if selected.id != st.session_state.get("graph_center_id"):
    st.session_state.graph_center_id = selected.id
    path = st.session_state.setdefault("graph_path", [])
    if not path or path[-1][0] != selected.id:
        path.append((selected.id, selected.name))

path = st.session_state.setdefault("graph_path", [(selected.id, selected.name)])
st.caption("探索路径：" + " → ".join(name for _, name in path[-6:]))

st.markdown(f"## {selected.name}")
detail_cols = st.columns(3)
detail_cols[0].metric("实体类型", TYPE_LABELS.get(selected.type, selected.type))
detail_cols[1].metric("别名数量", len(selected.aliases))
detail_cols[2].metric("查询后端", "本地只读图谱")
if selected.aliases:
    st.write("**别名：** " + "、".join(selected.aliases))

hits = runtime.neighbors(selected.name)
if not hits:
    st.info("当前实体没有可展示的一跳关系。")
    st.stop()

st.markdown(f"### 一跳关系（{len(hits)}）")
for hit in hits:
    render_relation_card(selected.name, hit)

neighbors = {}
for hit in hits:
    for entity in (hit.source_entity, hit.target_entity):
        if entity.id != selected.id:
            neighbors[entity.id] = entity

st.markdown("#### 沿相邻节点继续探索")
button_cols = st.columns(3)
for index, neighbor in enumerate(neighbors.values()):
    if button_cols[index % 3].button(
        f"{neighbor.name} · {TYPE_LABELS.get(neighbor.type, neighbor.type)}",
        key=f"neighbor_{selected.id}_{neighbor.id}",
        width="stretch",
    ):
        st.session_state.graph_pending_center = neighbor.id
        st.session_state.graph_path.append((neighbor.id, neighbor.name))
        st.rerun()

st.markdown("### 关系表格")
st.dataframe(relation_table_rows(hits), width="stretch", hide_index=True)

st.markdown("### 关系证据")
for index, hit in enumerate(hits, start=1):
    label = RELATION_LABELS.get(hit.relation, hit.relation)
    with st.expander(
        f"{index}. {hit.source_entity.name} — {label} → {hit.target_entity.name}"
    ):
        relative_direction = "从中心实体指出" if hit.direction == "outgoing" else "指向中心实体"
        st.markdown(
            f"**方向：** {hit.source_entity.name} → {hit.target_entity.name}（{relative_direction}）"
        )
        st.markdown(f"**关系类型：** `{hit.relation}`")
        st.markdown(f"**文档编号：** {hit.document_id}")
        st.info(hit.evidence)
        citation = runtime.citation_for_graph_hit(hit)
        if citation:
            st.markdown(f"**来源：** [{citation.title}]({citation.source_url}) · {citation.source_name}")
