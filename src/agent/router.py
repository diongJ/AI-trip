from __future__ import annotations

import re
from typing import Protocol

from src.agent.models import QuestionType, RouteDecision, ToolName


class EntityResolver(Protocol):
    def resolve_entity_id(self, query: str) -> str | None: ...


OUT_OF_SCOPE_RE = re.compile(
    r"(今天|现在|实时|当前).*(游客|人数|客流|天气|交通|排队|开放|票价|门票|预约)|"
    r"(天气|路线导航|停车|餐厅|酒店|公交|地铁|打车|机场|实时价格|预测|"
    r"智能手机|恐龙|航空母舰|火星|月球|外星)"
)
RELATION_RE = re.compile(r"(关系|谁|属于|出土|材料|材质|纹饰|制作|反映|关联|葬)")
DESCRIPTION_RE = re.compile(r"(介绍|讲讲|特点|意义|价值|如何|为什么|背景|过程|展示|展区)")
HYBRID_RE = re.compile(
    r"(结合.*(?:文物|资料|证据)|文物证据|建立|创建|创立|开国|反映|观念)"
)


class RuleBasedRouter:
    def __init__(self, resolver: EntityResolver | None = None) -> None:
        self.resolver = resolver

    def route(self, question: str) -> RouteDecision:
        normalized = question.strip()
        if not normalized:
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题为空，无法检索可靠证据。",
                scope="out_of_scope",
            )
        if OUT_OF_SCOPE_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题涉及实时或项目范围外信息，当前资料无法可靠回答。",
                scope="out_of_scope",
            )

        entity_query = self._find_entity_query(normalized)
        if entity_query and HYBRID_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要结合结构化关系和文档证据，使用混合检索。",
                intent="hybrid_explanation",
                entities=[entity_query],
                subqueries=[normalized],
            )
        if entity_query and RELATION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.RELATION_EXPLORATION,
                tool=ToolName.SEARCH_KG,
                entity_query=entity_query,
                reason="问题包含图谱实体和明确关系词，优先查询 KG。",
                intent="relation_exploration",
                entities=[entity_query],
                subqueries=[normalized],
            )
        if entity_query and DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要实体关系和文档描述，使用混合检索。",
                entities=[entity_query],
                subqueries=[normalized],
            )
        if entity_query:
            return RouteDecision(
                question_type=QuestionType.ENTITY_FACT,
                tool=ToolName.SEARCH_KG,
                entity_query=entity_query,
                reason="问题命中图谱实体，优先查询结构化事实。",
                intent="entity_fact",
                entities=[entity_query],
                subqueries=[normalized],
            )
        if DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.SEARCH_DOCUMENTS,
                reason="问题偏描述性，使用文档检索获取原文片段。",
                subqueries=[normalized],
            )
        return RouteDecision(
            question_type=QuestionType.DESCRIPTION,
            tool=ToolName.SEARCH_DOCUMENTS,
            reason="未命中明确实体，使用文档检索作为保守默认策略。",
            subqueries=[normalized],
        )

    def _find_entity_query(self, question: str) -> str | None:
        if self.resolver is None:
            return None
        candidates = _entity_candidates(question)
        for candidate in candidates:
            if self.resolver.resolve_entity_id(candidate):
                return candidate
        return None


def _entity_candidates(question: str) -> list[str]:
    clean = re.sub(r"[？?，,。！!：:；;、]", " ", question)
    tokens = [token.strip() for token in clean.split() if token.strip()]
    candidates = sorted(tokens, key=len, reverse=True)
    if question.strip() not in candidates:
        candidates.append(question.strip())
    return candidates
