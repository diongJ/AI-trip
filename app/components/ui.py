from __future__ import annotations

import html

import streamlit as st

from app.runtime import AppRuntime, QueryOutcome
from src.agent.models import Citation
from src.rag.models import GraphHit


TYPE_LABELS = {
    "Person": "人物",
    "Tomb": "墓葬",
    "TombChamber": "墓室",
    "Relic": "文物",
    "RelicCategory": "文物类别",
    "Material": "材质",
    "Dynasty": "朝代",
    "State": "政权",
    "HistoricalEvent": "历史事件",
    "Culture": "文化",
    "Pattern": "纹饰",
    "Exhibition": "展览",
}

RELATION_LABELS = {
    "BELONGS_TO_STATE": "属于政权",
    "BURIED_IN": "墓葬于",
    "CONTAINS": "包含",
    "EXCAVATED_FROM": "出土于",
    "MADE_OF": "材质为",
    "BELONGS_TO_CATEGORY": "属于类别",
    "CREATED_IN": "制作于",
    "RELATED_TO_PERSON": "关联人物",
    "REFLECTS_CULTURE": "反映文化",
    "HAS_PATTERN": "具有纹饰",
    "INVOLVES_PERSON": "涉及人物",
    "OCCURRED_IN": "发生于",
}


@st.cache_resource(show_spinner="正在加载知识库…")
def get_runtime() -> AppRuntime:
    return AppRuntime()


def configure_page(title: str, icon: str) -> None:
    st.set_page_config(
        page_title=f"{title}｜南越王智慧导览",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_STYLE, unsafe_allow_html=True)


def load_runtime_or_stop() -> AppRuntime:
    try:
        return get_runtime()
    except Exception as exc:
        st.error("知识库初始化失败，应用暂时无法提供可靠回答。")
        st.code(
            "python -m scripts.build_rag_index\n"
            "python -m scripts.build_graph_v1",
            language="powershell",
        )
        st.caption(f"错误类型：{type(exc).__name__}。请检查本地数据文件后重试。")
        st.stop()
        raise


def render_sidebar(runtime: AppRuntime) -> None:
    status = runtime.status
    with st.sidebar:
        st.markdown("### 南越王智慧导览")
        st.caption("可靠资料 · 可追溯证据 · 王墓展区")
        st.divider()
        st.markdown("#### 服务状态")
        _status_row("官方语料", status.corpus_ready, f"{status.document_count} 份")
        _status_row("RAG 索引", status.rag_ready, "已加载")
        _status_row(
            "本地图谱",
            status.graph_ready,
            f"{status.entity_count} 实体 / {status.relation_count} 关系",
        )
        _status_row(
            "DeepSeek",
            status.deepseek_configured,
            "智能生成" if status.deepseek_configured else "自动离线降级",
        )
        _status_row(
            "Neo4j Aura",
            status.neo4j_configured,
            "已配置（非启动依赖）" if status.neo4j_configured else "未配置（不影响演示）",
        )
        st.divider()
        st.info("资料仅覆盖南越王博物院王墓展区，不提供票务、客流、天气和路线导航。")


def render_outcome(outcome: QueryOutcome, *, show_answer: bool = True) -> None:
    response = outcome.response
    if outcome.warning:
        st.warning(outcome.warning)
    if response.insufficient_evidence:
        st.warning(response.answer)
    elif show_answer:
        st.markdown(response.answer)

    tools = "、".join(tool.value for tool in response.used_tools) or "未调用工具"
    with st.expander("回答过程", expanded=False):
        cols = st.columns(3)
        cols[0].metric("响应时间", f"{outcome.elapsed_ms:.1f} ms")
        cols[1].metric("生成模式", outcome.generation_mode)
        cols[2].metric("引用数量", len(response.citations))
        st.markdown(f"**使用工具：** {tools}")
        st.markdown(f"**路由原因：** {response.route_reason}")
    render_citations(response.citations)


def render_citations(citations: list[Citation]) -> None:
    if not citations:
        return
    st.markdown("#### 可追溯来源")
    for index, citation in enumerate(citations, start=1):
        with st.expander(f"来源 {index}｜{citation.doc_id}｜{citation.title}"):
            st.markdown(f"**来源机构：** {citation.source_name}")
            st.markdown(f"**原始链接：** [{citation.source_url}]({citation.source_url})")
            st.markdown("**证据片段：**")
            st.info(citation.evidence)


def render_relation_card(center_name: str, hit: GraphHit) -> None:
    source = html.escape(hit.source_entity.name)
    target = html.escape(hit.target_entity.name)
    relation = html.escape(RELATION_LABELS.get(hit.relation, hit.relation))
    center = html.escape(center_name)
    active_source = " active-node" if hit.source_entity.name == center_name else ""
    active_target = " active-node" if hit.target_entity.name == center_name else ""
    st.markdown(
        f"""
        <div class="relation-row" aria-label="{center} 的关系">
          <span class="entity-node{active_source}">{source}</span>
          <span class="relation-arrow">— {relation} →</span>
          <span class="entity-node{active_target}">{target}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def relation_table_rows(hits: list[GraphHit]) -> list[dict[str, str]]:
    return [
        {
            "起点": hit.source_entity.name,
            "关系": RELATION_LABELS.get(hit.relation, hit.relation),
            "终点": hit.target_entity.name,
            "相对中心方向": "从中心指出" if hit.direction == "outgoing" else "指向中心",
            "文档编号": hit.document_id,
            "后端": hit.backend,
        }
        for hit in hits
    ]


def _status_row(label: str, ready: bool, detail: str) -> None:
    icon = "🟢" if ready else "🟡"
    st.markdown(f"{icon} **{label}**")
    st.caption(detail)


_STYLE = """
<style>
  :root { --museum-red: #7d2e2e; --museum-gold: #b88746; --ink: #2f2925; }
  .stApp { background: linear-gradient(180deg, #fbf7f0 0%, #fffdf9 36%, #ffffff 100%); }
  h1, h2, h3 { color: var(--ink); letter-spacing: .01em; }
  [data-testid="stMetric"] { background: #fffaf1; border: 1px solid #eadbc5; border-radius: 14px; padding: 12px; }
  .hero { padding: 2rem 2.2rem; border-radius: 22px; color: white; background: linear-gradient(125deg, #612424, #8d3a32 58%, #bd8544); box-shadow: 0 15px 40px rgba(77,36,27,.16); margin-bottom: 1.4rem; }
  .hero h1 { color: white; margin: 0 0 .5rem 0; font-size: clamp(2rem, 5vw, 3.7rem); }
  .hero p { max-width: 760px; font-size: 1.08rem; opacity: .94; margin: 0; }
  .eyebrow { text-transform: uppercase; letter-spacing: .16em; color: #ffe5b9; font-size: .75rem; margin-bottom: .7rem; }
  .scope-note { border-left: 5px solid var(--museum-gold); padding: 1rem 1.2rem; background: #fff8ea; border-radius: 8px; }
  .relation-row { display: grid; grid-template-columns: minmax(110px,1fr) minmax(120px,auto) minmax(110px,1fr); align-items: center; gap: .7rem; margin: .55rem 0; padding: .7rem; border: 1px solid #eadbc5; border-radius: 12px; background: white; text-align: center; }
  .entity-node { padding: .45rem .7rem; border-radius: 999px; background: #f3e9db; color: #4b3027; font-weight: 650; }
  .active-node { background: #7d2e2e; color: white; }
  .relation-arrow { color: #805c35; font-size: .9rem; }
  @media (max-width: 600px) {
    .hero { padding: 1.35rem; border-radius: 16px; }
    .relation-row { grid-template-columns: 1fr; }
    .relation-arrow { transform: rotate(90deg); padding: .25rem; }
  }
</style>
"""
