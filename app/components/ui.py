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
        st.caption("可靠资料 · 可追溯证据 · 南越专题")
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
        st.info("资料覆盖南越王博物院、南越国历史、考古与文物专题；不提供实时客流、天气、餐饮和路线导航。")


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
        if response.source_tiers:
            labels = {"core": "核心馆方资料", "extended": "扩展可信资料"}
            st.markdown("**证据层级：** " + "、".join(labels.get(tier, tier) for tier in response.source_tiers))
        if response.refusal_reason:
            st.markdown(f"**拒答原因：** {response.refusal_reason}")
    render_citations(response.citations)


def render_citations(citations: list[Citation]) -> None:
    if not citations:
        return
    st.markdown("#### 可追溯来源")
    for index, citation in enumerate(citations, start=1):
        with st.expander(f"来源 {index}｜{citation.doc_id}｜{citation.title}"):
            tier_label = "核心馆方资料" if citation.source_tier == "core" else "扩展可信资料"
            st.markdown(f"**来源层级：** {tier_label}")
            st.markdown(f"**来源机构：** {citation.source_name}")
            st.markdown(f"**原始链接：** [{citation.source_url}]({citation.source_url})")
            st.markdown("**证据片段：**")
            st.info(citation.evidence)
            if citation.retrieved_at:
                st.caption(f"资料采集日期：{citation.retrieved_at}")


def render_relation_card(center_name: str, hit: GraphHit) -> None:
    source = html.escape(hit.source_entity.name)
    target = html.escape(hit.target_entity.name)
    relation = html.escape(RELATION_LABELS.get(hit.relation, hit.relation))
    center = html.escape(center_name)
    source_cls = f"node-{hit.source_entity.type}"
    target_cls = f"node-{hit.target_entity.type}"
    active_source = " active-node" if hit.source_entity.name == center_name else ""
    active_target = " active-node" if hit.target_entity.name == center_name else ""
    st.markdown(
        f"""
        <div class="relation-row" aria-label="{center} 的关系">
          <span class="entity-node {source_cls}{active_source}">{source}</span>
          <span class="relation-arrow">— {relation} →</span>
          <span class="entity-node {target_cls}{active_target}">{target}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_graph_legend() -> None:
    """图谱页实体类型图例（纯展示，不含按钮，不影响交互顺序）。"""
    chips = "".join(
        f'<span class="legend-chip"><span class="entity-node node-{key}" '
        f'style="padding:.1rem .5rem;font-size:.74rem;">{label}</span></span>'
        for key, label in TYPE_LABELS.items()
    )
    st.markdown(f'<div class="graph-legend">{chips}</div>', unsafe_allow_html=True)


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
  /* ── 设计变量：博物馆色系（象牙纸面 / 墨色 / 陶土红 / 青铜绿 / 玉石青 / 旧金） ── */
  :root {
    --paper: #f7f3ea;
    --paper-warm: #fbf7ef;
    --card: #fffdf8;
    --ink: #2f2a24;
    --ink-soft: #6b6154;
    --museum-red: #7d2e2e;
    --museum-red-deep: #5f2121;
    --museum-gold: #b88746;
    --bronze-green: #4d6b5a;
    --jade: #3f7364;
    --line: #e6dcc8;
    --line-strong: #d9cbae;
  }

  .stApp { background: linear-gradient(180deg, var(--paper) 0%, #fffdf9 40%, #ffffff 100%); }
  h1, h2, h3 { color: var(--ink); letter-spacing: .01em; }
  a { color: var(--museum-red); }

  /* ── 按钮与 query chip（Uiverse 微交互节奏，博物馆配色） ── */
  .stButton > button, .stLinkButton > a, [data-testid="stPageLink"] a {
    border-radius: 10px;
    border: 1px solid var(--line-strong);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  }
  .stButton > button:hover, .stLinkButton > a:hover, [data-testid="stPageLink"] a:hover {
    transform: translateY(-1px);
    border-color: var(--museum-red);
    box-shadow: 0 6px 16px -8px rgba(95, 33, 33, .35);
  }
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--museum-red), var(--museum-red-deep));
    border-color: var(--museum-red-deep);
  }

  /* ── Metric / 信息面板（Origin UI stats 风格） ── */
  [data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 3px solid var(--museum-gold);
    border-radius: 10px;
    padding: 14px 16px;
  }
  [data-testid="stMetricLabel"] { color: var(--ink-soft); }
  [data-testid="stMetricValue"] { color: var(--museum-red-deep); font-weight: 700; }

  /* ── Expander / 引用卡片 ── */
  [data-testid="stExpander"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
  }
  [data-testid="stExpander"] summary:hover { color: var(--museum-red); }

  /* ── 对话消息 ── */
  [data-testid="stChatMessage"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: .4rem .8rem;
  }

  /* ── 侧边栏 ── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f3ecdd 0%, var(--paper-warm) 100%);
    border-right: 1px solid var(--line);
  }

  /* ── 数据表 ── */
  [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }

  /* ── Hero：数字展厅（Aceternity 式细网格 + 证据节点，克制不炫技） ── */
  .hero {
    position: relative;
    padding: 2.4rem 2.4rem 2.2rem;
    border-radius: 20px;
    color: #fdf8ef;
    background:
      radial-gradient(ellipse 55% 60% at 78% 12%, rgba(184,135,70,.28), transparent 65%),
      linear-gradient(125deg, #4a1d1d 0%, #7d2e2e 55%, #a9713d 100%);
    box-shadow: 0 18px 44px rgba(74, 29, 29, .20);
    margin-bottom: 1.4rem;
    overflow: hidden;
  }
  .hero::before {
    content: "";
    position: absolute; inset: 0;
    background-image:
      linear-gradient(rgba(253,248,239,.07) 1px, transparent 1px),
      linear-gradient(90deg, rgba(253,248,239,.07) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
  }
  .hero::after {
    /* 证据节点：图谱隐喻的少量锚点 */
    content: "";
    position: absolute; inset: 0;
    background-image: radial-gradient(rgba(255,229,185,.55) 2px, transparent 2.6px);
    background-size: 120px 120px;
    background-position: 24px 18px;
    opacity: .35;
    pointer-events: none;
  }
  .hero h1 { color: #fff; margin: 0 0 .6rem 0; font-size: clamp(1.9rem, 4.6vw, 3.4rem); position: relative; }
  .hero p { max-width: 760px; font-size: 1.05rem; opacity: .94; margin: 0; position: relative; }
  .eyebrow {
    text-transform: uppercase; letter-spacing: .18em; color: #ffe5b9;
    font-size: .72rem; margin-bottom: .8rem; position: relative;
  }

  /* ── 功能入口 / 原则面板 ── */
  .entry-panel {
    height: 100%;
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 4px solid var(--museum-red);
    border-radius: 10px;
    padding: 1rem 1.1rem .4rem;
    transition: transform .18s ease, box-shadow .18s ease;
  }
  .entry-panel:hover { transform: translateY(-2px); box-shadow: 0 10px 24px -14px rgba(47,42,36,.35); }
  .entry-panel h3 { margin: 0 0 .35rem; font-size: 1.05rem; }
  .entry-panel p { color: var(--ink-soft); font-size: .88rem; line-height: 1.6; margin: 0 0 .5rem; }

  .principle-card {
    background: var(--paper-warm);
    border: 1px solid var(--line);
    border-top: 3px solid var(--bronze-green);
    border-radius: 10px;
    padding: .9rem 1rem;
    height: 100%;
  }
  .principle-card strong { color: var(--ink); }
  .principle-card span { color: var(--ink-soft); font-size: .85rem; line-height: 1.6; }

  .scope-note {
    border-left: 5px solid var(--museum-gold);
    padding: 1rem 1.2rem;
    background: #fff8ea;
    border-radius: 8px;
    margin-top: 1.2rem;
  }

  .section-eyebrow {
    text-transform: uppercase; letter-spacing: .16em;
    color: var(--museum-red); font-size: .72rem; font-weight: 600;
    margin: 1.6rem 0 .2rem;
  }

  /* ── 图谱关系行：节点按实体类型着色 ── */
  .relation-row {
    display: grid;
    grid-template-columns: minmax(110px,1fr) minmax(120px,auto) minmax(110px,1fr);
    align-items: center; gap: .7rem;
    margin: .55rem 0; padding: .7rem;
    border: 1px solid var(--line); border-radius: 12px;
    background: var(--card); text-align: center;
    transition: border-color .18s ease, box-shadow .18s ease;
  }
  .relation-row:hover { border-color: var(--line-strong); box-shadow: 0 8px 20px -14px rgba(47,42,36,.4); }
  .entity-node {
    padding: .45rem .7rem; border-radius: 999px;
    background: #f3e9db; color: #4b3027; font-weight: 650;
    border: 1px solid transparent;
  }
  .node-Person { background: #f3e0dc; color: #7d2e2e; }
  .node-Tomb, .node-TombChamber { background: #e9e4da; color: #3d362c; }
  .node-Relic, .node-RelicCategory { background: #e2ece6; color: #33523f; }
  .node-Material, .node-Pattern { background: #e6eeea; color: #3f7364; }
  .node-State, .node-Dynasty { background: #f0e8d3; color: #7a5a1e; }
  .node-Location, .node-HistoricalEvent, .node-Culture, .node-Exhibition { background: #ece7f0; color: #54486b; }
  .active-node {
    background: var(--museum-red) !important; color: #fff !important;
    box-shadow: 0 0 0 3px rgba(125,46,46,.18);
  }
  .relation-arrow { color: #805c35; font-size: .9rem; }

  .graph-legend { display: flex; flex-wrap: wrap; gap: .5rem; margin: .3rem 0 .8rem; }
  .legend-chip {
    font-size: .74rem; padding: .2rem .6rem; border-radius: 999px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink-soft);
  }

  /* ── 引导条 ── */
  .hint-strip {
    background: #fff8ea;
    border: 1px dashed var(--museum-gold);
    border-radius: 10px;
    color: #7a5a1e;
    font-size: .85rem;
    padding: .55rem .9rem;
    margin: .2rem 0 .6rem;
  }
  .hero-cta { margin: -.4rem 0 1rem; }

  @media (max-width: 600px) {
    .hero { padding: 1.4rem 1.2rem; border-radius: 14px; }
    .hero h1 { font-size: 1.7rem; }
    .relation-row { grid-template-columns: 1fr; }
    .relation-arrow { transform: rotate(90deg); padding: .25rem; }
    [data-testid="stMetric"] { padding: 10px 12px; }
  }
</style>
"""
