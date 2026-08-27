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
    configure_page,
    load_runtime_or_stop,
    render_outcome,
    render_sidebar,
)
from src.agent.models import AnswerMode, ConversationTurn


EXAMPLES = [
    "文帝行玺是什么材料？",
    "丝缕玉衣反映了什么丧葬观念？",
    "赵眜是谁？请结合文物证据。",
]

configure_page("智能问答", "💬")
runtime = load_runtime_or_stop()
render_sidebar(runtime)

st.title("💬 智能问答")
st.caption(
    "系统优先使用本地 KG/RAG 可信证据；专题内无证据时可进行 DeepSeek 联网搜索，"
    "联网内容会单独标识并提醒甄别。"
)
answer_mode = {
    "自动": AnswerMode.AUTO,
    "简洁": AnswerMode.BRIEF,
    "深入": AnswerMode.DEEP,
}[st.selectbox("回答风格", ["自动", "简洁", "深入"], help="深入模式会综合多条证据并逐条核验。")]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

head_cols = st.columns([5, 1])
with head_cols[0]:
    st.markdown('<p class="section-eyebrow">示例问题 · 点击即问</p>', unsafe_allow_html=True)
with head_cols[1]:
    if st.button("清空会话", width="stretch"):
        st.session_state.chat_history = []
        st.rerun()

st.markdown(
    '<div class="hint-strip">👇 先点一个示例问题体验，或在页面底部输入框直接提问'
    "（包含真实实体名如「赵眜」「丝缕玉衣」命中率更高）</div>",
    unsafe_allow_html=True,
)
with st.container(border=True):
    example_cols = st.columns(3)
    selected_question = None
    for index, question in enumerate(EXAMPLES):
        if example_cols[index].button(
            question, key=f"example_{index}", width="stretch", type="secondary"
        ):
            selected_question = question

for item in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(item["question"])
    with st.chat_message("assistant", avatar="🏺"):
        render_outcome(item["outcome"])

typed_question = st.chat_input("询问王墓展区的人物、墓葬、文物或历史……")
question = typed_question or selected_question
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="🏺"):
        with st.spinner("正在检索可靠证据并组织回答……"):
            history = [
                ConversationTurn(
                    question=item["question"], answer=item["outcome"].response.answer
                )
                for item in st.session_state.chat_history[-4:]
            ]
            outcome = runtime.ask(question, history=history, answer_mode=answer_mode)
        render_outcome(outcome)
    st.session_state.chat_history.append({"question": question, "outcome": outcome})
